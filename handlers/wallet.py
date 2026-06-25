

import time
import logging
from datetime import datetime, timedelta

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import monobank
from handlers.config import MONO_TOKEN, MONO_ACCOUNT, MONO_CARD, MONO_JAR_LINK, MONO_JAR_CARD
from handlers.config import ADMIN_ID
from db import (
    get_balance,
    add_pending_payment,
    get_pending_payments,
    remove_pending_payment,
    add_to_balance,
    mark_tx_used,
    is_tx_used,
    add_payment_log,
    mark_referral_paid,
    update_daily_net,
)

import asyncio

# user_id -> asyncio.Lock. Паралельні натискання "Перевірити" від одного
# користувача виконуються послідовно, а не одночасно.
_payment_locks: dict[int, asyncio.Lock] = {}
router = Router(name="wallet")

MIN_SUM = 200

class WalletStates(StatesGroup):
    enter_amount = State()


# ==================== МЕНЮ ГАМАНЦЯ ====================
@router.message(F.text.in_({"💰 Гаманець", "Гаманець"}))
async def wallet_menu(message: Message):
    balance = await get_balance(message.from_user.id)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"Баланс: {balance} грн", callback_data="wallet_balance"
                )
            ],
            [
                InlineKeyboardButton(
                    text="Поповнити баланс", callback_data="wallet_topup"
                )
            ],
        ]
    )
    await message.answer(f"💰 Ваш гаманець\nБаланс: {balance} грн", reply_markup=kb)


# ==================== ПОПОВНЕННЯ ====================
@router.callback_query(F.data == "wallet_topup")
async def start_topup(callback: CallbackQuery, state: FSMContext):
    cancel_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❌ Скасувати", callback_data="wallet_cancel")]
        ]
    )
    await callback.message.answer(
        f"Введіть суму поповнення в гривнях (від {MIN_SUM} грн):",
        reply_markup=cancel_kb,
    )
    await state.set_state(WalletStates.enter_amount)
    await callback.answer()


@router.callback_query(F.data == "wallet_cancel")
async def cancel_topup(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Поповнення скасовано.")
    await callback.answer()



@router.message(WalletStates.enter_amount)
async def process_amount(message: Message, state: FSMContext):
    cancel_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❌ Скасувати", callback_data="wallet_cancel")]
        ]
    )
    try:
        amount_grn = int(message.text)
        if amount_grn < MIN_SUM:
            await message.answer(f"❌ Мінімум {MIN_SUM} грн", reply_markup=cancel_kb)
            return
    except Exception:
        await message.answer("Введи суму поповнення або скасуй платіж", reply_markup=cancel_kb)
        return

    amount_kop = amount_grn * 100

    payment_id = f"PAYMENT:{int(time.time())}:{message.from_user.id}:{int(time.time() * 1000) % 10000}"

    await add_pending_payment(message.from_user.id, amount_kop, payment_id)

    logging.info(
        f"📤 НОВИЙ ПЛАТІЖ СТВОРЕНИЙ | user_id={message.from_user.id} | "
        f"sum={amount_grn} грн | payment_id='{payment_id}'"
    )


    text = (
        f"💰 Поповнення на <b>{amount_grn} грн</b>\n\n"
        f"Перекажіть <b>точно</b> цю суму на БАНКУ Monobank:\n\n"
        f"За посиланням: {MONO_JAR_LINK}\n\n"
        f"Чи на карту : <code>{MONO_JAR_CARD}</code>\n\n"
        f"❗Після оплати натисни кнопку «Перевірити платіж»"
    )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Перевірити платіж", callback_data="wallet_check"
                )
            ]
        ]
    )

    await message.answer(text, reply_markup=kb, parse_mode="HTML")
    await state.clear()


@router.callback_query(F.data == "wallet_check")
@router.message(Command("check"))
async def check_payment(event: Message | CallbackQuery):
    if isinstance(event, CallbackQuery):
        message = event.message
        user_id = event.from_user.id
        await event.answer()
    else:
        message = event
        user_id = event.from_user.id

    # ── Один лок на user_id ──────────────────────────────────────
    if user_id not in _payment_locks:
        _payment_locks[user_id] = asyncio.Lock()
    lock = _payment_locks[user_id]

    if lock.locked():
        await message.answer("⏳ Платіж вже перевіряється, зачекай...")
        return

    async with lock:
        # ── Перевіряємо pending ──────────────────────────────────────
        pending = await get_pending_payments()
        user_pending = [p for p in pending if p["user_id"] == user_id]
        if not user_pending:
            await message.answer(
                "❌ Немає активних платежів. Почни з кнопки 'Поповнити баланс'"
            )
            return

        p = user_pending[0]
        target_amount_kop = p["amount_kop"]
        target_amount_grn = target_amount_kop // 100
        payment_id = p["comment"]

        try:
            parts = payment_id.split(":")
            payment_timestamp = int(parts[1])
        except Exception:
            payment_timestamp = int(time.time())

        logging.info(
            f"🔍 ПЕРЕВІРКА | user_id={user_id} | "
            f"payment_id='{payment_id}' | {target_amount_grn} грн"
        )

        await message.answer("🔍 Перевіряю платіж...")

        try:
            client = monobank.Client(token=MONO_TOKEN)
            from_date = datetime.now() - timedelta(days=7)
            statements = client.get_statements(MONO_ACCOUNT, from_date, datetime.now())
            logging.info(f"📥 Отримано {len(statements)} транзакцій")

            time_window = 600
            best_match = None
            best_match_diff = float("inf")

            for tx in statements:
                tx_amount = tx.get("amount", 0)
                tx_time   = tx.get("time", 0)
                tx_id     = tx.get("id", "")
                time_diff = abs(tx_time - payment_timestamp)

                if await is_tx_used(tx_id):
                    continue

                if tx_amount == target_amount_kop and time_diff <= time_window and tx_amount > 0:
                    if time_diff < best_match_diff:
                        best_match = tx
                        best_match_diff = time_diff

            if not best_match:
                kb = InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="🔄 Перевірити платіж", callback_data="wallet_check")
                ]])
                await message.answer(
                    f"❌ Платіж ще не знайдено.\n\n"
                    f"✓ Відправив точно <b>{target_amount_grn} грн</b>\n"
                    f"✓ На правильну картку: <b>{MONO_JAR_CARD}</b>\n\n"
                    f"Почекай 1–2 хвилини і спробуй знову.",
                    parse_mode="HTML", reply_markup=kb,
                )
                return

            tx    = best_match
            tx_id = tx.get("id", "")

            # ── АТОМАРНА РЕЗЕРВАЦІЯ — якщо повернула False, хтось встиг раніше ──
            reserved = await mark_tx_used(tx_id, user_id, target_amount_kop, payment_id)
            if not reserved:
                await message.answer("⚠️ Ця транзакція вже зарахована. Перевір баланс.")
                return

            # ── Зараховуємо ─────────────────────────────────────────────
            await add_to_balance(user_id, target_amount_grn)
            await update_daily_net(user_id, target_amount_grn)
            await remove_pending_payment(user_id)
            await add_payment_log(
                user_id=user_id,
                username=event.from_user.username or event.from_user.full_name,
                amount=target_amount_grn,
                comment=payment_id,
            )

            user_name = (
                f"@{event.from_user.username}"
                if event.from_user.username
                else event.from_user.full_name
            )
            await message.bot.send_message(
                ADMIN_ID,
                f"💰 Поповнення балансу\n\n"
                f"👤 {user_name}\n"
                f"💵 <b>{target_amount_grn} грн</b>\n"
                f"💳 Баланс: <b>{await get_balance(user_id)} грн</b>",
                parse_mode="HTML",
            )

            play_kb = ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="🎮 Грати")]],
                resize_keyboard=True,
            )
            await message.answer(
                f"✅ Платіж зараховано!\n\n"
                f"💰 {target_amount_grn} грн\n"
                f"💳 Баланс: {await get_balance(user_id)} грн",
                reply_markup=play_kb,
            )
            logging.info(
                f"✅ ЗАРАХОВАНО | user_id={user_id} | {target_amount_grn} грн | "
                f"tx_id='{tx_id}' | diff={best_match_diff}s"
            )

            referrer_id = await mark_referral_paid(user_id)
            if referrer_id:
                await add_to_balance(referrer_id, 50)
                await update_daily_net(referrer_id, 50)
                await message.bot.send_message(
                    referrer_id,
                    f"🎉 Реферал поповнив баланс!\n💰 Вам нараховано <b>50 грн</b>",
                    parse_mode="HTML",
                )
                await add_to_balance(user_id, 50)
                await update_daily_net(referrer_id, 50)
                await message.bot.send_message(
                    user_id,
                    f"🎁 Бонус <b>50 грн</b> за запрошення!\n"
                    f"💳 Баланс: <b>{await get_balance(user_id)} грн</b>",
                    parse_mode="HTML",
                )

        except monobank.TooManyRequests:
            logging.warning(f"⚠️ Ліміт Monobank для user_id={user_id}")
            await message.answer("⏳ Ліміт запитів Monobank. Зачекай 60 секунд.")
        except Exception as e:
            logging.error(f"❌ ПОМИЛКА | user_id={user_id}: {e}", exc_info=True)
            await message.answer("❌ Помилка перевірки. Спробуй пізніше.")