

# import time
# import logging
# from datetime import datetime, timedelta

# from aiogram import Router, F
# from aiogram.filters import Command
# from aiogram.types import (
#     Message,
#     InlineKeyboardMarkup,
#     InlineKeyboardButton,
#     CallbackQuery,
#     ReplyKeyboardMarkup,
#     KeyboardButton,
# )
# from aiogram.fsm.context import FSMContext
# from aiogram.fsm.state import State, StatesGroup
# import monobank
# from handlers.config import MONO_TOKEN, MONO_ACCOUNT, MONO_CARD, MONO_JAR_LINK, MONO_JAR_CARD
# from handlers.config import ADMIN_ID
# from db import (
#     get_balance,
#     add_pending_payment,
#     get_pending_payments,
#     remove_pending_payment,
#     add_to_balance,
#     mark_tx_used,
#     is_tx_used,
#     add_payment_log,
#     mark_referral_paid,
#     update_daily_net,
#     get_cards,
# )

# import asyncio

# # user_id -> asyncio.Lock. Паралельні натискання "Перевірити" від одного
# # користувача виконуються послідовно, а не одночасно.
# _payment_locks: dict[int, asyncio.Lock] = {}
# router = Router(name="wallet")

# MIN_SUM = 200
# REFERRAL_BONUS = 50

# CASHIER_URL = "https://t.me/KaSSa_4444"
# KYIV_OFFSET = timedelta(hours=3)
# AUTO_TOPUP_START_HOUR = 0
# AUTO_TOPUP_END_HOUR = 9


# def is_auto_topup_time() -> bool:
#     """Автоплата через бота доступна лише з 00:00 до 09:00 (Київ)."""
#     now_kyiv = datetime.utcnow() + KYIV_OFFSET
#     return AUTO_TOPUP_START_HOUR <= now_kyiv.hour < AUTO_TOPUP_END_HOUR


# async def send_manual_topup_info(message: Message):
#     cards = await get_cards()
#     cards_text = "\n\n".join([f"🏦 {bank}: <code>{num}</code>" for bank, num in cards]) or "—"

#     kb = InlineKeyboardMarkup(
#         inline_keyboard=[
#             [InlineKeyboardButton(text="👨‍💼 Касир", url=CASHIER_URL)]
#         ]
#     )

#     await message.answer(
#         f"⏰ Автоматичне поповнення доступне лише з "
#         f"{AUTO_TOPUP_START_HOUR:02d}:00 до {AUTO_TOPUP_END_HOUR:02d}:00.\n\n"
#         f"💸 Зараз поповнення через касира:\n\n"
#         f"{cards_text}\n\n"
#         f"‼️Після оплати напишіть касиру скрін для зарахування коштів‼️",
#         reply_markup=kb,
#         parse_mode="HTML",
#     )


# class WalletStates(StatesGroup):
#     enter_amount = State()


# # ==================== МЕНЮ ГАМАНЦЯ ====================
# @router.message(F.text.in_({"💰 Гаманець", "Гаманець"}))
# async def wallet_menu(message: Message):
#     balance = await get_balance(message.from_user.id)
#     kb = InlineKeyboardMarkup(
#         inline_keyboard=[
#             [
#                 InlineKeyboardButton(
#                     text=f"Баланс: {balance} грн", callback_data="wallet_balance"
#                 )
#             ],
#             [
#                 InlineKeyboardButton(
#                     text="Поповнити баланс", callback_data="wallet_topup"
#                 )
#             ],
#         ]
#     )
#     await message.answer(f"💰 Ваш гаманець\nБаланс: {balance} грн", reply_markup=kb)


# # ==================== ПОПОВНЕННЯ ====================
# @router.callback_query(F.data == "wallet_topup")
# async def start_topup(callback: CallbackQuery, state: FSMContext):
#     if not is_auto_topup_time():
#         await send_manual_topup_info(callback.message)
#         await callback.answer()
#         return

#     cancel_kb = InlineKeyboardMarkup(
#         inline_keyboard=[
#             [InlineKeyboardButton(text="❌ Скасувати", callback_data="wallet_cancel")]
#         ]
#     )
#     await callback.message.answer(
#         f"Введіть суму поповнення в гривнях (від {MIN_SUM} грн):",
#         reply_markup=cancel_kb,
#     )
#     await state.set_state(WalletStates.enter_amount)
#     await callback.answer()


# @router.callback_query(F.data == "wallet_cancel")
# async def cancel_topup(callback: CallbackQuery, state: FSMContext):
#     await state.clear()
#     await callback.message.edit_text("❌ Поповнення скасовано.")
#     await callback.answer()



# @router.message(WalletStates.enter_amount)
# async def process_amount(message: Message, state: FSMContext):
#     if not is_auto_topup_time():
#         await state.clear()
#         await send_manual_topup_info(message)
#         return

#     cancel_kb = InlineKeyboardMarkup(
#         inline_keyboard=[
#             [InlineKeyboardButton(text="❌ Скасувати", callback_data="wallet_cancel")]
#         ]
#     )
#     try:
#         amount_grn = int(message.text)
#         if amount_grn < MIN_SUM:
#             await message.answer(f"❌ Мінімум {MIN_SUM} грн", reply_markup=cancel_kb)
#             return
#     except Exception:
#         await message.answer("Введи суму поповнення або скасуй платіж", reply_markup=cancel_kb)
#         return

#     amount_kop = amount_grn * 100

#     payment_id = f"PAYMENT:{int(time.time())}:{message.from_user.id}:{int(time.time() * 1000) % 10000}"

#     await add_pending_payment(message.from_user.id, amount_kop, payment_id)

#     logging.info(
#         f"📤 НОВИЙ ПЛАТІЖ СТВОРЕНИЙ | user_id={message.from_user.id} | "
#         f"sum={amount_grn} грн | payment_id='{payment_id}'"
#     )


#     text = (
#         f"💰 Поповнення на <b>{amount_grn} грн</b>\n\n"
#         f"Перекажіть <b>точно</b> цю суму на БАНКУ Monobank:\n\n"
#         f"За посиланням: {MONO_JAR_LINK}\n\n"
#         f"Чи на карту : <code>{MONO_JAR_CARD}</code>\n\n"
#         f"❗Після оплати натисни кнопку «Перевірити платіж»"
#     )

#     kb = InlineKeyboardMarkup(
#         inline_keyboard=[
#             [
#                 InlineKeyboardButton(
#                     text="Перевірити платіж", callback_data="wallet_check"
#                 )
#             ]
#         ]
#     )

#     await message.answer(text, reply_markup=kb, parse_mode="HTML")
#     await state.clear()



# @router.callback_query(F.data == "wallet_check")
# @router.message(Command("check"))
# async def check_payment(event: Message | CallbackQuery):
#     if isinstance(event, CallbackQuery):
#         message = event.message
#         user_id = event.from_user.id
#         await event.answer()
#     else:
#         message = event
#         user_id = event.from_user.id

#     if user_id not in _payment_locks:
#         _payment_locks[user_id] = asyncio.Lock()
#     lock = _payment_locks[user_id]

#     if lock.locked():
#         await message.answer("⏳ Платіж вже перевіряється, зачекай...")
#         return

#     async with lock:
#         pending = await get_pending_payments()
#         user_pending = [p for p in pending if p["user_id"] == user_id]
#         if not user_pending:
#             await message.answer("❌ Немає активних платежів.")
#             return

#         p = user_pending[0]
#         target_amount_kop = p["amount_kop"]
#         target_amount_grn = target_amount_kop // 100
#         payment_id = p["comment"]

#         await message.answer("🔍 Перевіряю платіж...")

#         try:
#             client = monobank.Client(token=MONO_TOKEN)
#             from_date = datetime.now() - timedelta(days=7)
#             statements = client.get_statements(MONO_ACCOUNT, from_date, datetime.now())

#             time_window = 600
#             best_match = None
#             best_match_diff = float("inf")

#             for tx in statements:
#                 tx_amount = tx.get("amount", 0)
#                 tx_time = tx.get("time", 0)
#                 tx_id = tx.get("id", "")

#                 try:
#                     payment_timestamp = int(payment_id.split(":")[1])
#                     time_diff = abs(tx_time - payment_timestamp)
#                 except:
#                     time_diff = 0

#                 if await is_tx_used(tx_id):
#                     continue

#                 if tx_amount == target_amount_kop and time_diff <= time_window and tx_amount > 0:
#                     if time_diff < best_match_diff:
#                         best_match = tx
#                         best_match_diff = time_diff

#             if not best_match:
#                 kb = InlineKeyboardMarkup(inline_keyboard=[[
#                     InlineKeyboardButton(text="🔄 Перевірити платіж", callback_data="wallet_check")
#                 ]])
#                 await message.answer(
#                     f"❌ Платіж ще не знайдено.\n\n"
#                     f"✓ Відправив точно <b>{target_amount_grn} грн</b>\n"
#                     f"✓ На правильну картку: <b>{MONO_JAR_CARD}</b>\n\n"
#                     f"Почекай 1–2 хвилини і спробуй знову.",
#                     parse_mode="HTML", reply_markup=kb
#                 )
#                 return

#             # === Успішне зарахування ===
#             tx = best_match
#             tx_id = tx.get("id", "")

#             reserved = await mark_tx_used(tx_id, user_id, target_amount_kop, payment_id)
#             if not reserved:
#                 await message.answer("⚠️ Ця транзакція вже була зарахована.")
#                 return

#             await add_to_balance(user_id, target_amount_grn)
#             await update_daily_net(user_id, target_amount_grn)
#             await remove_pending_payment(user_id)
#             await add_payment_log(
#                 user_id=user_id,
#                 username=event.from_user.username or event.from_user.full_name,
#                 amount=target_amount_grn,
#                 comment=payment_id,
#             )

#             # Посилання на реферала
#             referral_link = (
#                 f"@{event.from_user.username}" 
#                 if event.from_user.username 
#                 else f'<a href="tg://user?id={user_id}">{event.from_user.full_name}</a>'
#             )

#             # Сповіщення адміністратору про поповнення
#             await message.bot.send_message(
#                 ADMIN_ID,
#                 f"💰 Нове поповнення балансу\n\n"
#                 f"👤 {referral_link}\n"
#                 f"💵 <b>{target_amount_grn} грн</b>\n"
#                 f"💳 Баланс: <b>{await get_balance(user_id)} грн</b>",
#                 parse_mode="HTML"
#             )

#             # Повідомлення користувачу
#             play_kb = ReplyKeyboardMarkup(
#                 keyboard=[[KeyboardButton(text="🎮 Грати")]],
#                 resize_keyboard=True,
#             )
#             await message.answer(
#                 f"✅ Платіж зараховано!\n\n"
#                 f"💰 {target_amount_grn} грн\n"
#                 f"💳 Баланс: {await get_balance(user_id)} грн",
#                 reply_markup=play_kb,
#                 parse_mode="HTML"
#             )

#             # ====================== РЕФЕРАЛЬНИЙ БЛОК ======================
#             referrer_id = await mark_referral_paid(user_id)
#             logging.info(f"🔗 mark_referral_paid повернув referrer_id = {referrer_id}")

#             if referrer_id and referrer_id != user_id:
#                 await add_to_balance(referrer_id, REFERRAL_BONUS)
#                 await update_daily_net(referrer_id, REFERRAL_BONUS)

#                 # Посилання на реферера
#                 referrer_link = f'<a href="tg://user?id={referrer_id}">{referrer_id}</a>'

#                 # Сповіщення рефереру
#                 try:
#                     await message.bot.send_message(
#                         referrer_id,
#                         f"🎉 Ваш реферал поповнив баланс!\n\n"
#                         f"👤 Користувач: {referral_link}\n"
#                         f"💰 Вам нараховано <b>+{REFERRAL_BONUS} грн</b>",
#                         parse_mode="HTML"
#                     )
#                 except Exception as e:
#                     logging.error(f"❌ Не вдалося відправити рефереру {referrer_id}: {e}")

#                 # Сповіщення адміністратору про видачу бонусу
#                 try:
#                     await message.bot.send_message(
#                         ADMIN_ID,
#                         f"🎁 Реферальний бонус виданий!\n\n"
#                         f"👤 Реферер: {referrer_link}\n"
#                         f"👤 Реферал: {referral_link}\n"
#                         f"💰 Бонус: <b>+{REFERRAL_BONUS} грн</b>",
#                         parse_mode="HTML"
#                     )
#                 except Exception as e:
#                     logging.error(f"❌ Не вдалося відправити адміну про бонус: {e}")

#             logging.info(f"✅ Поповнення успішно завершено для user {user_id}")

#         except monobank.TooManyRequests:
#             logging.warning(f"⚠️ Ліміт Monobank для user_id={user_id}")
#             await message.answer("⏳ Ліміт запитів. Зачекай 60 секунд.")
#         except Exception as e:
#             logging.error(f"❌ Критична помилка в check_payment: {e}", exc_info=True)
#             await message.answer("❌ Помилка при обробці платежу.")


import time
import json
import logging
from pathlib import Path
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
    get_cards,
)

import asyncio

# user_id -> asyncio.Lock. Паралельні натискання "Перевірити" від одного
# користувача виконуються послідовно, а не одночасно.
_payment_locks: dict[int, asyncio.Lock] = {}
router = Router(name="wallet")

MIN_SUM = 200
REFERRAL_BONUS = 50

CASHIER_URL = "https://t.me/KaSSa_4444"
KYIV_OFFSET = timedelta(hours=3)

# Розклад автооплати: з 22:00 до 09:00 (Київ)
AUTO_TOPUP_START_HOUR = 22
AUTO_TOPUP_END_HOUR = 9

# ==================== РЕЖИМ АВТООПЛАТИ (керування адміном) ====================

AUTOPAY_MODE_AUTO = "auto"           # за розкладом 22:00–09:00
AUTOPAY_MODE_FORCE_ON = "force_on"   # адмін примусово увімкнув автооплату
AUTOPAY_MODE_FORCE_OFF = "force_off" # адмін примусово вимкнув автооплату (ручний режим)

_SETTINGS_FILE = Path(__file__).resolve().parent.parent / "data" / "wallet_settings.json"


def _load_autopay_mode() -> str:
    try:
        if _SETTINGS_FILE.exists():
            data = json.loads(_SETTINGS_FILE.read_text(encoding="utf-8"))
            mode = data.get("autopay_mode", AUTOPAY_MODE_AUTO)
            if mode in (AUTOPAY_MODE_AUTO, AUTOPAY_MODE_FORCE_ON, AUTOPAY_MODE_FORCE_OFF):
                return mode
    except Exception as e:
        logging.error(f"❌ Не вдалося прочитати wallet_settings.json: {e}")
    return AUTOPAY_MODE_AUTO


def _save_autopay_mode(mode: str) -> None:
    try:
        _SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        _SETTINGS_FILE.write_text(json.dumps({"autopay_mode": mode}), encoding="utf-8")
    except Exception as e:
        logging.error(f"❌ Не вдалося зберегти wallet_settings.json: {e}")


_autopay_mode: str = _load_autopay_mode()


def _mode_label(mode: str) -> str:
    return {
        AUTOPAY_MODE_AUTO: "🕒 За розкладом (22:00–09:00)",
        AUTOPAY_MODE_FORCE_ON: "✅ Примусово УВІМКНЕНО",
        AUTOPAY_MODE_FORCE_OFF: "🚫 Примусово ВИМКНЕНО (ручний режим)",
    }.get(mode, mode)


def is_auto_topup_time() -> bool:
    """
    True, якщо зараз доступна автоплата через бота.
    Враховує ручний режим адміна (force_on / force_off),
    інакше — розклад 22:00–09:00 за Києвом.
    """
    if _autopay_mode == AUTOPAY_MODE_FORCE_ON:
        return True
    if _autopay_mode == AUTOPAY_MODE_FORCE_OFF:
        return False

    now_kyiv = datetime.utcnow() + KYIV_OFFSET
    hour = now_kyiv.hour
    # проміжок переходить через північ: 22:00 -> 09:00
    return hour >= AUTO_TOPUP_START_HOUR or hour < AUTO_TOPUP_END_HOUR


async def send_manual_topup_info(message: Message):
    cards = await get_cards()
    cards_text = "\n\n".join([f"🏦 {bank}: <code>{num}</code>" for bank, num in cards]) or "—"

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👨‍💼 Касир", url=CASHIER_URL)]
        ]
    )

    text = (
        f"⏰ Автооплата працює з "
        f"{AUTO_TOPUP_START_HOUR:02d}:00 до {AUTO_TOPUP_END_HOUR:02d}:00.\n\n"
        f"{cards_text}\n\n"
        "‼️ Мінімальне поповнення 200 грн‼️\n\n"
        "‼️ Після оплати надішліть касиру чек для зарахування коштів‼️"
    )

    await message.answer(
        text,
        reply_markup=kb,
        parse_mode="HTML",
    )


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
    if not is_auto_topup_time():
        await send_manual_topup_info(callback.message)
        await callback.answer()
        return

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
    if not is_auto_topup_time():
        await state.clear()
        await send_manual_topup_info(message)
        return

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

    if user_id not in _payment_locks:
        _payment_locks[user_id] = asyncio.Lock()
    lock = _payment_locks[user_id]

    if lock.locked():
        await message.answer("⏳ Платіж вже перевіряється, зачекай...")
        return

    async with lock:
        pending = await get_pending_payments()
        user_pending = [p for p in pending if p["user_id"] == user_id]
        if not user_pending:
            await message.answer("❌ Немає активних платежів.")
            return

        p = user_pending[0]
        target_amount_kop = p["amount_kop"]
        target_amount_grn = target_amount_kop // 100
        payment_id = p["comment"]

        await message.answer("🔍 Перевіряю платіж...")

        try:
            client = monobank.Client(token=MONO_TOKEN)
            from_date = datetime.now() - timedelta(days=7)
            statements = client.get_statements(MONO_ACCOUNT, from_date, datetime.now())

            time_window = 600
            best_match = None
            best_match_diff = float("inf")

            for tx in statements:
                tx_amount = tx.get("amount", 0)
                tx_time = tx.get("time", 0)
                tx_id = tx.get("id", "")

                try:
                    payment_timestamp = int(payment_id.split(":")[1])
                    time_diff = abs(tx_time - payment_timestamp)
                except:
                    time_diff = 0

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
                    parse_mode="HTML", reply_markup=kb
                )
                return

            # === Успішне зарахування ===
            tx = best_match
            tx_id = tx.get("id", "")

            reserved = await mark_tx_used(tx_id, user_id, target_amount_kop, payment_id)
            if not reserved:
                await message.answer("⚠️ Ця транзакція вже була зарахована.")
                return

            await add_to_balance(user_id, target_amount_grn)
            await update_daily_net(user_id, target_amount_grn)
            await remove_pending_payment(user_id)
            await add_payment_log(
                user_id=user_id,
                username=event.from_user.username or event.from_user.full_name,
                amount=target_amount_grn,
                comment=payment_id,
            )

            # Посилання на реферала
            referral_link = (
                f"@{event.from_user.username}" 
                if event.from_user.username 
                else f'<a href="tg://user?id={user_id}">{event.from_user.full_name}</a>'
            )

            # Сповіщення адміністратору про поповнення
            await message.bot.send_message(
                ADMIN_ID,
                f"💰 Нове поповнення балансу\n\n"
                f"👤 {referral_link}\n"
                f"💵 <b>{target_amount_grn} грн</b>\n"
                f"💳 Баланс: <b>{await get_balance(user_id)} грн</b>",
                parse_mode="HTML"
            )

            # Повідомлення користувачу
            play_kb = ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="🎮 Грати")]],
                resize_keyboard=True,
            )
            await message.answer(
                f"✅ Платіж зараховано!\n\n"
                f"💰 {target_amount_grn} грн\n"
                f"💳 Баланс: {await get_balance(user_id)} грн",
                reply_markup=play_kb,
                parse_mode="HTML"
            )

            # ====================== РЕФЕРАЛЬНИЙ БЛОК ======================
            referrer_id = await mark_referral_paid(user_id)
            logging.info(f"🔗 mark_referral_paid повернув referrer_id = {referrer_id}")

            if referrer_id and referrer_id != user_id:
                await add_to_balance(referrer_id, REFERRAL_BONUS)
                await update_daily_net(referrer_id, REFERRAL_BONUS)

                # Посилання на реферера
                referrer_link = f'<a href="tg://user?id={referrer_id}">{referrer_id}</a>'

                # Сповіщення рефереру
                try:
                    await message.bot.send_message(
                        referrer_id,
                        f"🎉 Ваш реферал поповнив баланс!\n\n"
                        f"👤 Користувач: {referral_link}\n"
                        f"💰 Вам нараховано <b>+{REFERRAL_BONUS} грн</b>",
                        parse_mode="HTML"
                    )
                except Exception as e:
                    logging.error(f"❌ Не вдалося відправити рефереру {referrer_id}: {e}")

                # Сповіщення адміністратору про видачу бонусу
                try:
                    await message.bot.send_message(
                        ADMIN_ID,
                        f"🎁 Реферальний бонус виданий!\n\n"
                        f"👤 Реферер: {referrer_link}\n"
                        f"👤 Реферал: {referral_link}\n"
                        f"💰 Бонус: <b>+{REFERRAL_BONUS} грн</b>",
                        parse_mode="HTML"
                    )
                except Exception as e:
                    logging.error(f"❌ Не вдалося відправити адміну про бонус: {e}")

            logging.info(f"✅ Поповнення успішно завершено для user {user_id}")

        except monobank.TooManyRequests:
            logging.warning(f"⚠️ Ліміт Monobank для user_id={user_id}")
            await message.answer("⏳ Ліміт запитів. Зачекай 60 секунд.")
        except Exception as e:
            logging.error(f"❌ Критична помилка в check_payment: {e}", exc_info=True)
            await message.answer("❌ Помилка при обробці платежу.")


# ==================== АДМІНКА: РУЧНЕ КЕРУВАННЯ АВТООПЛАТОЮ ====================

def autopay_admin_kb() -> InlineKeyboardMarkup:
    def mark(mode: str) -> str:
        return "🔘 " if _autopay_mode == mode else "⚪️ "

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text=f"{mark(AUTOPAY_MODE_AUTO)}🕒 За розкладом (22:00–09:00)",
                callback_data="autopay_mode_auto"
            )],
            [InlineKeyboardButton(
                text=f"{mark(AUTOPAY_MODE_FORCE_ON)}✅ Примусово увімкнути",
                callback_data="autopay_mode_on"
            )],
            [InlineKeyboardButton(
                text=f"{mark(AUTOPAY_MODE_FORCE_OFF)}🚫 Примусово вимкнути (ручний режим)",
                callback_data="autopay_mode_off"
            )],
        ]
    )


@router.message(F.text == "⚙️ Автооплата")
@router.message(Command("autopay"))
async def autopay_admin_menu(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer(
        f"⚙️ <b>Керування автооплатою</b>\n\n"
        f"Поточний режим: <b>{_mode_label(_autopay_mode)}</b>\n\n"
        f"Автооплата працює з 22:00 до 09:00"
        f"Можеш примусово перемкнути в будь-яку сторону — режим збережеться "
        f"навіть після перезапуску бота.",
        parse_mode="HTML",
        reply_markup=autopay_admin_kb(),
    )


@router.callback_query(F.data.startswith("autopay_mode_"))
async def set_autopay_mode(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer()
        return

    global _autopay_mode
    key = callback.data.removeprefix("autopay_mode_")
    mode_map = {
        "auto": AUTOPAY_MODE_AUTO,
        "on": AUTOPAY_MODE_FORCE_ON,
        "off": AUTOPAY_MODE_FORCE_OFF,
    }
    new_mode = mode_map.get(key, AUTOPAY_MODE_AUTO)
    _autopay_mode = new_mode
    _save_autopay_mode(new_mode)

    await callback.message.edit_text(
        f"⚙️ <b>Керування автооплатою</b>\n\n"
        f"Поточний режим: <b>{_mode_label(_autopay_mode)}</b>\n\n"
        f"За розкладом автоплата працює з 22:00 до 09:00 (Київ).",
        parse_mode="HTML",
        reply_markup=autopay_admin_kb(),
    )
    await callback.answer("✅ Збережено")