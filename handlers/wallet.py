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
# )
# from aiogram.fsm.context import FSMContext
# from aiogram.fsm.state import State, StatesGroup

# import monobank
# from handlers.config import MONO_TOKEN, MONO_ACCOUNT, MONO_CARD
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
# )

# router = Router(name="wallet")


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
#     await callback.message.answer("Введіть суму поповнення в гривнях (від 200 грн):")
#     await state.set_state(WalletStates.enter_amount)
#     await callback.answer()


# @router.message(WalletStates.enter_amount)
# async def process_amount(message: Message, state: FSMContext):
#     try:
#         amount_grn = int(message.text)
#         if amount_grn < 200:
#             await message.answer("❌ Мінімум 200 грн")
#             return
#     except:
#         await message.answer("Введи тільки число")
#         return

#     amount_kop = amount_grn * 100

#     # 🎯 Генеруємо унікальний ID платежу
#     payment_id = f"PAYMENT:{int(time.time())}:{message.from_user.id}:{int(time.time() * 1000) % 10000}"

#     await add_pending_payment(message.from_user.id, amount_kop, payment_id)

#     logging.info(
#         f"📤 НОВИЙ ПЛАТІЖ СТВОРЕНИЙ | user_id={message.from_user.id} | "
#         f"sum={amount_grn} грн | payment_id='{payment_id}'"
#     )

    

#     text = (
#         f"💰 Поповнення на <b>{amount_grn} грн</b>\n\n"
#         f"Перекажіть <b>точно</b> цю суму на картку Monobank:\n\n"
#         f"<code>{MONO_CARD}</code>\n\n"
#         f"Після оплати натисни кнопку нижче"
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


# # ==================== ПЕРЕВІРКА ПЛАТЕЖУ ====================
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

#     pending = await get_pending_payments()
#     user_pending = [p for p in pending if p["user_id"] == user_id]
#     if not user_pending:
#         await message.answer(
#             "❌ Немає активних платежів. Почни з кнопки 'Поповнити баланс'"
#         )
#         return

#     p = user_pending[0]
#     target_amount_kop = p["amount_kop"]
#     target_amount_grn = target_amount_kop // 100
#     payment_id = p["comment"]

#     # 🎯 Парсимо дані з payment_id
#     try:
#         parts = payment_id.split(":")
#         payment_timestamp = int(parts[1])
#         expected_user_id = int(parts[2])
#     except:
#         payment_timestamp = int(time.time())
#         expected_user_id = user_id

#     logging.info(
#         f"🔍 ПЕРЕВІРКА ПЛАТЕЖУ | user_id={user_id} | "
#         f"payment_id='{payment_id}' | sum={target_amount_grn} грн ({target_amount_kop} коп)"
#     )

#     await message.answer("🔍 Перевіряю платіж по сумі...")

#     try:
#         client = monobank.Client(token=MONO_TOKEN)

#         from_date = datetime.now() - timedelta(days=7)
#         to_date = datetime.now()

#         statements = client.get_statements(MONO_ACCOUNT, from_date, to_date)

#         logging.info(f"📥 Отримано {len(statements)} транзакцій з Monobank за 7 днів")

#         time_window = 600  # 10 хвилин

#         best_match = None
#         best_match_diff = float("inf")

#         for tx in statements:
#             tx_amount = tx.get("amount", 0)
#             tx_time = tx.get("time", 0)
#             tx_id = tx.get("id", "")
#             time_diff = abs(tx_time - payment_timestamp)

#             # 🛡️ КРИТИЧНО: Пропускаємо вже використані TX!
#             if await is_tx_used(tx_id):
#                 logging.debug(f"  ⏭️ TX вже використана: '{tx_id}' - пропускаємо")
#                 continue

#             # ✅ ОСНОВНІ УМОВИ:
#             if (
#                 tx_amount == target_amount_kop
#                 and time_diff <= time_window
#                 and tx_amount > 0
#             ):

#                 # Якщо ДЕКІЛЬКА платежів на ту ж суму - беремо НАЙБЛИЖЧИЙ по часу
#                 if time_diff < best_match_diff:
#                     best_match = tx
#                     best_match_diff = time_diff

#                     logging.info(
#                         f"  📌 Кандидат знайдений: time_diff={time_diff}s, "
#                         f"tx_id='{tx_id}', description='{tx.get('description', '')}'"
#                     )

#         if not best_match:
#             logging.warning(
#                 f"⚠️ Платіж НЕ ЗНАЙДЕНО! user_id={user_id} | "
#                 f"payment_id='{payment_id}' | шукали: {target_amount_grn} грн за {time_window}s"
#             )
#             kb = InlineKeyboardMarkup(
#                 inline_keyboard=[
#                     [
#                         InlineKeyboardButton(
#                             text="🔄 Перевірити платіж",
#                             callback_data="wallet_check"
#                         )
#                     ]
#                 ]
#             )

#             await message.answer(
#                 f"❌ Платіж ще не знайдено.\n\n"
#                 f"Переконайся:\n"
#                 f"✓ Відправив точно <b>{target_amount_grn} грн</b>\n"
#                 f"✓ На правильну картку: <b>{MONO_CARD}</b>\n"
#                 f"✓ Платіж успішно обробився\n\n"
#                 f"Почекай 1–2 хвилини і натисни кнопку нижче.",
#                 parse_mode="HTML",
#                 reply_markup=kb
#             )
#             return

#         # 🎯 ЗНАЙШЛИ! Зарахуємо платіж
#         tx = best_match
#         tx_id = tx.get("id", "")

#         # 🛡️ ВАЖЛИВО: Позначаємо TX як використану!
#         await mark_tx_used(tx_id, user_id, target_amount_kop, payment_id)

#         await add_to_balance(user_id, target_amount_grn)
#         await remove_pending_payment(user_id)

#         await add_payment_log(
#         user_id=user_id,
#         username=event.from_user.username or "-",
#         amount=target_amount_grn,
#         comment=payment_id
#     )
#         user_name = (
#             f"@{event.from_user.username}"
#             if event.from_user.username
#             else event.from_user.full_name
#         )

#         await message.bot.send_message(
#             ADMIN_ID,
#             f"💰 Поповнення балансу\n\n"
#             f"👤 Користувач: {user_name}\n"
#             f"💵 Сума: <b>{target_amount_grn} грн</b>\n"
#             f"💳 Новий баланс: <b>{await get_balance(user_id)} грн</b>",
#             parse_mode="HTML"
# )


#         tx_hold = tx.get("hold", False)
#         tx_description = tx.get("description", "")

#         status_msg = " (холд ще тримається)" if tx_hold else ""

#         from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

#         play_kb = ReplyKeyboardMarkup(
#             keyboard=[
#                 [KeyboardButton(text="🎮 Грати")]
#             ],
#             resize_keyboard=True
#         )

#         await message.answer(
#             f"✅ Платіж зараховано!\n\n"
#             f"💰 Сума: {target_amount_grn} грн\n"
#             f"💳 Новий баланс: {await get_balance(user_id)} грн",
#             reply_markup=play_kb
#         )

#         # await message.answer(
#         #     # f"✅ Платіж зараховано{status_msg}!\n\n"
#         #     f"✅ Платіж зараховано!\n\n"
#         #     f"Сума: {target_amount_grn} грн\n"
#         #     f"Новий баланс: {await get_balance(user_id)} грн"
#         # )

#         logging.info(
#             f"✅ ПЛАТІЖ ЗАРАХОВАНО! user_id={user_id} | "
#             f"{target_amount_grn} грн | payment_id='{payment_id}' | "
#             f"tx_id='{tx_id}' | time_diff={best_match_diff}s | "
#             f"from='{tx_description}'{status_msg}"
#         )


#         referrer_id = await mark_referral_paid(user_id)
#         if referrer_id:
#             # бонус тому хто запросив
#             await add_to_balance(referrer_id, 50)
#             await message.bot.send_message(
#                 referrer_id,
#                 f"🎉 Ваш реферал поповнив баланс!\n"
#                 f"💰 Вам нараховано <b>50 грн</b>",
#                 parse_mode="HTML"
#             )

#             # бонус тому кого запросили — тільки всередині if referrer_id!
#             await add_to_balance(user_id, 50)
#             await message.bot.send_message(
#                 user_id,
#                 f"🎁 Вам нараховано бонус <b>50 грн</b> за реєстрацію по запрошенню друга!\n"
#                 f"💳 Баланс: <b>{await get_balance(user_id)} грн</b>",
#                 parse_mode="HTML"
#             )

#     except monobank.TooManyRequests:
#         logging.warning(f"⚠️ Ліміт запитів Monobank для user_id={user_id}")
#         await message.answer("⏳ Ліміт запитів до Monobank. Почекай 60 секунд.")
#     except Exception as e:
#         logging.error(f"❌ ПОМИЛКА MONOBANK для user_id={user_id}: {e}", exc_info=True)
#         await message.answer("❌ Помилка перевірки. Спробуй пізніше.")


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
from handlers.config import MONO_TOKEN, MONO_ACCOUNT, MONO_CARD
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
)

router = Router(name="wallet")

MIN_SUM = 1

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


# @router.message(WalletStates.enter_amount)
# async def process_amount(message: Message, state: FSMContext):
#     try:
#         amount_grn = int(message.text)
#         if amount_grn < MIN_SUM:
#             await message.answer(f"❌ Мінімум {MIN_SUM} грн")
#             return
#     except Exception:
#         await message.answer("Введи тільки число ")
#         return

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
        f"Перекажіть <b>точно</b> цю суму на картку Monobank:\n\n"
        f"<code>{MONO_CARD}</code>\n\n"
        f"Після оплати натисни кнопку нижче"
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


# ==================== ПЕРЕВІРКА ПЛАТЕЖУ ====================
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
        expected_user_id = int(parts[2])
    except Exception:
        payment_timestamp = int(time.time())
        expected_user_id = user_id

    logging.info(
        f"🔍 ПЕРЕВІРКА ПЛАТЕЖУ | user_id={user_id} | "
        f"payment_id='{payment_id}' | sum={target_amount_grn} грн ({target_amount_kop} коп)"
    )

    await message.answer("🔍 Перевіряю платіж по сумі...")

    try:
        client = monobank.Client(token=MONO_TOKEN)

        from_date = datetime.now() - timedelta(days=7)
        to_date = datetime.now()

        statements = client.get_statements(MONO_ACCOUNT, from_date, to_date)

        logging.info(f"📥 Отримано {len(statements)} транзакцій з Monobank за 7 днів")

        time_window = 600

        best_match = None
        best_match_diff = float("inf")

        for tx in statements:
            tx_amount = tx.get("amount", 0)
            tx_time = tx.get("time", 0)
            tx_id = tx.get("id", "")
            time_diff = abs(tx_time - payment_timestamp)

            if await is_tx_used(tx_id):
                logging.debug(f"  ⏭️ TX вже використана: '{tx_id}' - пропускаємо")
                continue

            if (
                tx_amount == target_amount_kop
                and time_diff <= time_window
                and tx_amount > 0
            ):
                if time_diff < best_match_diff:
                    best_match = tx
                    best_match_diff = time_diff

                    logging.info(
                        f"  📌 Кандидат знайдений: time_diff={time_diff}s, "
                        f"tx_id='{tx_id}', description='{tx.get('description', '')}'"
                    )

        if not best_match:
            logging.warning(
                f"⚠️ Платіж НЕ ЗНАЙДЕНО! user_id={user_id} | "
                f"payment_id='{payment_id}' | шукали: {target_amount_grn} грн за {time_window}s"
            )
            kb = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="🔄 Перевірити платіж",
                            callback_data="wallet_check",
                        )
                    ]
                ]
            )
            await message.answer(
                f"❌ Платіж ще не знайдено.\n\n"
                f"Переконайся:\n"
                f"✓ Відправив точно <b>{target_amount_grn} грн</b>\n"
                f"✓ На правильну картку: <b>{MONO_CARD}</b>\n"
                f"✓ Платіж успішно обробився\n\n"
                f"Почекай 1–2 хвилини і натисни кнопку нижче.",
                parse_mode="HTML",
                reply_markup=kb,
            )
            return

        tx = best_match
        tx_id = tx.get("id", "")

        await mark_tx_used(tx_id, user_id, target_amount_kop, payment_id)
        await add_to_balance(user_id, target_amount_grn)
        await remove_pending_payment(user_id)

        # await add_payment_log(
        #     user_id=user_id,
        #     username=event.from_user.username or "-",
        #     amount=target_amount_grn,
        #     comment=payment_id,
        # )

        await add_payment_log(
            user_id=user_id,
            username=event.from_user.username if event.from_user.username else event.from_user.full_name,
            amount=target_amount_grn,
            comment=payment_id
        )



        user_name = (
            f"@{event.from_user.username}"
            if event.from_user.username
            else event.from_user.full_name
        )

        await message.bot.send_message(
            ADMIN_ID,
            f"💰 Поповнення балансу\n\n"
            f"👤 Користувач: {user_name}\n"
            f"💵 Сума: <b>{target_amount_grn} грн</b>\n"
            f"💳 Новий баланс: <b>{await get_balance(user_id)} грн</b>",
            parse_mode="HTML",
        )

        tx_hold = tx.get("hold", False)
        tx_description = tx.get("description", "")
        status_msg = " (холд ще тримається)" if tx_hold else ""

        play_kb = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="🎮 Грати")]],
            resize_keyboard=True,
        )

        await message.answer(
            f"✅ Платіж зараховано!\n\n"
            f"💰 Сума: {target_amount_grn} грн\n"
            f"💳 Новий баланс: {await get_balance(user_id)} грн",
            reply_markup=play_kb,
        )

        logging.info(
            f"✅ ПЛАТІЖ ЗАРАХОВАНО! user_id={user_id} | "
            f"{target_amount_grn} грн | payment_id='{payment_id}' | "
            f"tx_id='{tx_id}' | time_diff={best_match_diff}s | "
            f"from='{tx_description}'{status_msg}"
        )

        referrer_id = await mark_referral_paid(user_id)
        if referrer_id:
            await add_to_balance(referrer_id, 50)
            await message.bot.send_message(
                referrer_id,
                f"🎉 Ваш реферал поповнив баланс!\n"
                f"💰 Вам нараховано <b>50 грн</b>",
                parse_mode="HTML",
            )

            await add_to_balance(user_id, 50)
            await message.bot.send_message(
                user_id,
                f"🎁 Вам нараховано бонус <b>50 грн</b> за реєстрацію по запрошенню друга!\n"
                f"💳 Баланс: <b>{await get_balance(user_id)} грн</b>",
                parse_mode="HTML",
            )

    except monobank.TooManyRequests:
        logging.warning(f"⚠️ Ліміт запитів Monobank для user_id={user_id}")
        await message.answer("⏳ Ліміт запитів до Monobank. Почекай 60 секунд.")
    except Exception as e:
        logging.error(f"❌ ПОМИЛКА MONOBANK для user_id={user_id}: {e}", exc_info=True)
        await message.answer("❌ Помилка перевірки. Спробуй пізніше.")