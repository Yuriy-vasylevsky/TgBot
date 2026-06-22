

# import re

# from aiogram import Router, F
# from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, CallbackQuery,ReplyKeyboardRemove
# from aiogram.fsm.context import FSMContext
# from aiogram.fsm.state import StatesGroup, State

# from handlers.config import ADMIN_ID
# from handlers.profile import notify_reward_progress
# from db.check import add_check_code, get_checks_stats, clear_all_checks
# from aiogram.types import (
#     ReplyKeyboardMarkup,
#     KeyboardButton,
#     InlineKeyboardMarkup,
#     InlineKeyboardButton
# )
# from db import get_balance, add_to_balance, log_check_issued
# from db.check import get_checks_count, get_free_check, remove_check, get_checks_total_balance
# from handlers.menu import checks_menu
# from handlers.casino_api import create_invoice, create_matic_checks

# router = Router(name="admin_checks")


# class CheckFSM(StatesGroup):
#     waiting_for_code = State()
#     waiting_for_custom_amount = State()   # ← Для динамічної суми Champion


# # Тільки Matic — Champion коди адмін більше не додає вручну (видається через API)
# CHECK_TABLES = {
#     "🎰 Чек 100 Matic": "matic_checks_100",
#     "🎰 Чек 200 Matic": "matic_checks_200",
# }

# # Matic — фіксовані готові коди з БД, без API
# MATIC_TABLES = {
#     100: "matic_checks_100",
#     200: "matic_checks_200",
# }

# # Champion — завжди через API (динамічна видача)
# CHAMPION_PRESET_AMOUNTS = [100, 200, 250]


# # ==================== АДМІН ПАНЕЛЬ (додавання кодів) ====================

# # @router.message(CheckFSM.waiting_for_code, F.text == "❌ Скасувати")
# # async def cancel_add_code(message: Message, state: FSMContext):
# #     if message.from_user.id != ADMIN_ID:
# #         return
# #     await state.clear()
# #     await message.answer("❌ Додавання чека скасовано", reply_markup=checks_menu())


# # @router.message(F.text == "💳 Чеки")
# # async def open_checks(message: Message):
# #     if message.from_user.id != ADMIN_ID:
# #         return

# #     stats = await get_checks_stats()
# #     total_balance = await get_checks_total_balance()

# #     text = "💳 <b>Меню чеків</b>\n\n📊 <b>Наявні чеки:</b>\n\n"

# #     for name, count in stats.items():
# #         if "Champion" in name:
# #             continue
# #         text += f"{name}: <b>{count}</b>\n"

# #     text += f"\n💰 <b>Баланс чеків:</b> {total_balance} грн"

# #     await message.answer(text, parse_mode="HTML", reply_markup=checks_menu())


# # @router.message(F.text.in_(CHECK_TABLES.keys()))
# # async def choose_type(message: Message, state: FSMContext):
# #     if message.from_user.id != ADMIN_ID:
# #         return

# #     await state.update_data(table=CHECK_TABLES[message.text])
# #     await state.set_state(CheckFSM.waiting_for_code)

# #     cancel_kb = ReplyKeyboardMarkup(
# #         keyboard=[[KeyboardButton(text="❌ Скасувати")]],
# #         resize_keyboard=True
# #     )

# #     await message.answer(
# #         "📩 Відправ код у форматі: 00-00-00-00-00-00-00\n",
# #         reply_markup=cancel_kb
# #     )


# # @router.message(CheckFSM.waiting_for_code)
# # async def save_code(message: Message, state: FSMContext):
# #     if message.from_user.id != ADMIN_ID:
# #         return

# #     code = message.text.strip()

# #     if not re.fullmatch(r"(\d{2}-){6}\d{2}", code):
# #         await message.answer("❌ Невірний формат коду")
# #         return

# #     data = await state.get_data()
# #     table = data["table"]

# #     await add_check_code(table, code)

# #     cancel_kb = ReplyKeyboardMarkup(
# #         keyboard=[[KeyboardButton(text="❌ Скасувати")]],
# #         resize_keyboard=True
# #     )

# #     await message.answer(
# #         f"✅ Код додано:\n<code>{code}</code>\n\n"
# #         f"📩 Надішли наступний код:",
# #         parse_mode="HTML",
# #         reply_markup=cancel_kb
# #     )


# # ==================== ГРА ДЛЯ КОРИСТУВАЧІВ ====================

# @router.message(F.text == "🎮 Грати")
# async def play_menu(message: Message):
#     user_id = message.from_user.id
#     balance = await get_balance(user_id)
#     checks = await get_checks_count()

#     text = (
#         f"💰 Баланс: <b>{balance} грн</b>\n\n"
#         # f"📦 Доступні чеки:\n\n"
#         # f"🎰 100 Matic: {checks['matic_100']}\n"
#         # f"🎰 200 Matic: {checks['matic_200']}\n\n"
#         # f"👇 Обери гру 👇"
#     )

#     kb = ReplyKeyboardMarkup(
#         keyboard=[
#             [KeyboardButton(text="🏆 Champion"), KeyboardButton(text="🎰 Matic")],
#             [KeyboardButton(text="🔒 Закрити чек")],
#              [KeyboardButton(text="💵 Поповнити чек")],
#             [KeyboardButton(text="🔙 Назад до головного меню")]
#         ],
#         resize_keyboard=True
#     )

#     inline_kb = InlineKeyboardMarkup(
#         inline_keyboard=[
#             [
#                 InlineKeyboardButton(text="💰 Поповнити", callback_data="wallet_topup"),
#                 InlineKeyboardButton(text="👨‍💼 Касир", url="https://t.me/KaSSa_4444")
#             ]
#         ]
#     )

#     await message.answer(text, parse_mode="HTML", reply_markup=inline_kb)
#     await message.answer(
#         "💰 Вивід через касира в робочий час з 9:00 до 00:00",
#         reply_markup=kb
#     )


# def champion_amount_kb() -> InlineKeyboardMarkup:
#     return InlineKeyboardMarkup(
#         inline_keyboard=[
#             [
#                 InlineKeyboardButton(text=f"{amount} грн", callback_data=f"champ_amt_{amount}")
#                 for amount in CHAMPION_PRESET_AMOUNTS
#             ],
#             [InlineKeyboardButton(text="✏️ Інша сума", callback_data="champ_amt_custom")],
#             [InlineKeyboardButton(text="❌ Скасувати", callback_data="champ_cancel")]
#         ]
#     )


# def matic_amount_kb() -> InlineKeyboardMarkup:
#     return InlineKeyboardMarkup(
#         inline_keyboard=[
#             [
#                 InlineKeyboardButton(text=f"{amount} грн", callback_data=f"matic_amt_{amount}")
#                 for amount in MATIC_TABLES
#             ],
#             [InlineKeyboardButton(text="❌ Скасувати", callback_data="matic_cancel")]
#         ]
#     )


# @router.message(F.text == "🏆 Champion")
# async def champion_menu(message: Message, state: FSMContext):
#     await state.clear()
#     await message.answer("🏆 Обери суму Champion:", reply_markup=champion_amount_kb())


# @router.message(F.text == "🎰 Matic")
# async def matic_menu(message: Message):
#     await message.answer("🎰 Обери суму Matic:", reply_markup=matic_amount_kb())


# # === ВИДАЧА ЧЕКА CHAMPION (через API) ===

# async def issue_champion_check(target_message: Message, user, amount: int):
#     user_id = user.id

#     invoice_data = await create_invoice(amount)

#     if not invoice_data or not invoice_data.get("success"):
#         await target_message.answer("❌ Помилка створення чека в казино. Спробуйте пізніше.")
#         return

#     invoice_code = invoice_data["invoice"]
#     game_url = invoice_data["url"]

#     await add_to_balance(user_id, -amount)
#     await log_check_issued(user_id, f"🏆 Champion {amount}", invoice_code, amount)
#     await notify_reward_progress(
#         target_message.bot, user_id,
#         user.username,
#         user.full_name or ""
#     )

#     name = f"@{user.username}" if user.username else user.full_name or f"#{user_id}"
#     await target_message.bot.send_message(
#         ADMIN_ID,
#         f"🎁 Видано чек (API)\n\n"
#         f"👤 {name}\n"
#         f"🏷 Тип: <b>Champion {amount} грн</b>\n"
#         f"🔑 Код: <code>{invoice_code}</code>",
#         parse_mode="HTML"
#     )

#     await target_message.answer(
#         f"🎉 <b>Гарної гри!</b>\n\n"
#         f"🔑 Код: <code>{invoice_code}</code>\n"
#         f"💳 Залишок: {await get_balance(user_id)} грн\n\n"
#         f"🔗 {game_url}",
#         parse_mode="HTML",
#         disable_web_page_preview=True
#     )


# @router.callback_query(F.data.startswith("champ_amt_"))
# async def champion_pick_amount(callback: CallbackQuery, state: FSMContext):
#     value = callback.data.removeprefix("champ_amt_")

#     if value == "custom":
#         await state.set_state(CheckFSM.waiting_for_custom_amount)
#         cancel_kb = InlineKeyboardMarkup(
#             inline_keyboard=[[InlineKeyboardButton(text="❌ Скасувати", callback_data="champ_cancel")]]
#         )
#         await callback.message.edit_text(
#             "🏆 Введіть суму для Champion (від 50 грн):",
#             reply_markup=cancel_kb
#         )
#         await callback.answer()
#         return

#     amount = int(value)
#     balance = await get_balance(callback.from_user.id)
#     if balance < amount:
#         await callback.answer("❌ Недостатньо коштів", show_alert=True)
#         return

#     await callback.message.edit_reply_markup(reply_markup=None)
#     await callback.answer()
#     await issue_champion_check(callback.message, callback.from_user, amount)


# @router.message(CheckFSM.waiting_for_custom_amount)
# async def process_custom_amount(message: Message, state: FSMContext):
#     try:
#         amount = int(message.text)
#         if amount < 50:
#             await message.answer("❌ Мінімальна сума — 50 грн")
#             return
#     except (TypeError, ValueError):
#         await message.answer("❌ Введіть тільки число")
#         return

#     balance = await get_balance(message.from_user.id)
#     if balance < amount:
#         await message.answer("❌ Недостатньо коштів")
#         return

#     await state.clear()
#     await issue_champion_check(message, message.from_user, amount)


# @router.callback_query(F.data == "champ_cancel")
# async def champion_cancel(callback: CallbackQuery, state: FSMContext):
#     await state.clear()
#     await callback.message.edit_text("❌ Скасовано")
#     await callback.answer()


# # === ВИДАЧА ЧЕКА MATIC (готові коди з БД, без API) ===

# async def issue_matic_check(target_message: Message, user, amount: int, code: str):
#     user_id = user.id

#     await add_to_balance(user_id, -amount)
#     await log_check_issued(user_id, f"🎰 Matic {amount}", code, amount)
#     await notify_reward_progress(
#         target_message.bot, user_id,
#         user.username,
#         user.full_name or ""
#     )

#     name = f"@{user.username}" if user.username else user.full_name or f"#{user_id}"
#     await target_message.bot.send_message(
#         ADMIN_ID,
#         f"🎁 Видано чек (БД)\n\n"
#         f"👤 {name}\n"
#         f"🏷 Тип: <b>Matic {amount} грн</b>\n"
#         f"🔑 Код: <code>{code}</code>",
#         parse_mode="HTML"
#     )

#     await target_message.answer(
#         f"🎉 <b>Гарної гри!</b>\n\n"
#         f"🔑 Код: <code>{code}</code>\n"
#         f"💳 Залишок: {await get_balance(user_id)} грн",
#         parse_mode="HTML"
#     )


# @router.callback_query(F.data.startswith("matic_amt_"))
# async def matic_pick_amount(callback: CallbackQuery):
#     amount = int(callback.data.removeprefix("matic_amt_"))
#     user_id = callback.from_user.id

#     balance = await get_balance(user_id)
#     if balance < amount:
#         await callback.answer("❌ Недостатньо коштів", show_alert=True)
#         return

#     await callback.answer("🔄 Генеруємо Matic чек...")

#     try:
#         result = await create_matic_checks(amount=amount, count=1)

#         if result.get("created", 0) > 0 and result.get("codes"):
#             code_info = result["codes"][0]
#             # Беремо код (може бути "code", "login", "key" — подивимось по відповіді)
#             code = code_info.get("code") or code_info.get("login") or code_info.get("key") or str(code_info)

#             await callback.message.edit_reply_markup(reply_markup=None)
#             await callback.answer()

#             await add_to_balance(user_id, -amount)
#             await log_check_issued(user_id, f"🎰 Matic {amount}", code, amount)

#             await issue_matic_check(callback.message, callback.from_user, amount, code)

#         else:
#             await callback.message.edit_text("❌ Не вдалося створити чек Matic.")
#     except Exception as e:
#         await callback.message.edit_text(f"❌ Помилка при створенні чека:\n{str(e)}")

# @router.callback_query(F.data == "matic_cancel")
# async def matic_cancel(callback: CallbackQuery):
#     await callback.message.edit_text("❌ Скасовано")
#     await callback.answer()


# # ==================== АДМІН СТАТИСТИКА ====================

# @router.message(F.text == "📊 Чеки")
# async def checks_stats(message: Message):
#     if message.from_user.id != ADMIN_ID:
#         return

#     stats = await get_checks_stats()
#     total_balance = await get_checks_total_balance()

#     text = "💳 <b>Статистика чеків</b>\n\n"

#     for name, count in stats.items():
#         if "Champion" in name:
#             continue
#         text += f"{name}: <b>{count}</b>\n"

#     text += f"\n💰 <b>Баланс чеків:</b> {total_balance} грн"

#     kb = InlineKeyboardMarkup(
#         inline_keyboard=[
#             [InlineKeyboardButton(text="🧹 Очистити всі чеки", callback_data="clear_checks_ask")]
#         ]
#     )

#     await message.answer(text, parse_mode="HTML", reply_markup=kb)


# @router.callback_query(F.data == "clear_checks_ask")
# async def ask_clear(callback: CallbackQuery):
#     if callback.from_user.id != ADMIN_ID:
#         await callback.answer("Тільки для адміна", show_alert=True)
#         return

#     kb = InlineKeyboardMarkup(
#         inline_keyboard=[
#             [
#                 InlineKeyboardButton(text="✅ Так, видалити", callback_data="clear_checks_confirm"),
#                 InlineKeyboardButton(text="❌ Скасувати", callback_data="clear_checks_cancel"),
#             ]
#         ]
#     )

#     await callback.message.edit_text(
#         "⚠️ Точно видалити ВСІ чеки?\nЦю дію НЕ можна скасувати!",
#         reply_markup=kb
#     )
#     await callback.answer()


# @router.callback_query(F.data == "clear_checks_confirm")
# async def confirm_clear(callback: CallbackQuery):
#     if callback.from_user.id != ADMIN_ID:
#         await callback.answer("Тільки для адміна", show_alert=True)
#         return

#     await clear_all_checks()
#     await callback.message.edit_text("🧹 Всі чеки видалено!")
#     await callback.answer("Готово!", show_alert=True)


# @router.callback_query(F.data == "clear_checks_cancel")
# async def cancel_clear(callback: CallbackQuery):
#     if callback.from_user.id != ADMIN_ID:
#         await callback.answer("Тільки для адміна", show_alert=True)
#         return

#     await callback.message.edit_text("❌ Скасовано")
#     await callback.answer()









# # ==================== ЗАКРИТТЯ ЧЕКА CHAMPION ДЛЯ ГРАВЦІВ ====================

# from handlers.casino_api import close_invoice, check_invoice
# from db import get_issued_checks_for_user, add_to_balance
# from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


# @router.message(F.text == "🔒 Закрити чек")
# async def show_my_checks(message: Message):
#     """Показує ТІЛЬКИ активні чеки Champion з балансом > 0"""
#     user_id = message.from_user.id
#     checks = await get_issued_checks_for_user(user_id)
    
#     champion_checks = [ch for ch in checks if "Champion" in ch.get("check_type", "")]
    
#     if not champion_checks:
#         await message.answer("❌ У вас немає виданих чеків Champion.")
#         return

#     text = "🔒 **Ваші активні чеки Champion**\n\nОберіть, який хочете закрити:\n\n"
#     buttons = []
#     active_count = 0

#     for ch in champion_checks:
#         code = ch["code"]
#         price = ch.get("price", "?")

#         # === Перевіряємо актуальний баланс через API ===
#         status = await check_invoice(code)
#         if not status or not status.get("success"):
#             continue

#         remaining = float(status.get("sum", 0))
        
#         if remaining <= 0:
#             continue  # пропускаємо закриті/порожні чеки

#         active_count += 1
#         short = code[-6:] if len(code) >= 6 else code
        
#         text += f"🔑 <code>{code}</code> — 💰 <b>{remaining:.0f} грн</b>\n"
        
#         buttons.append([
#             InlineKeyboardButton(
#                 text=f"🔒 Закрити •••{short} ({remaining:.0f} грн)",
#                 callback_data=f"close_champ_{code}"
#             )
#         ])

#     if active_count == 0:
#         await message.answer("❌ У вас немає активних чеків Champion з балансом більше 0 грн.")
#         return

#     buttons.append([
#         InlineKeyboardButton(text="❌ Скасувати", callback_data="close_cancel")
#     ])

#     await message.answer(
#         text,
#         parse_mode="HTML",
#         reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
#     )


# @router.callback_query(F.data.startswith("close_champ_"))
# async def process_close_check(callback: CallbackQuery):
#     invoice = callback.data.removeprefix("close_champ_")
#     user_id = callback.from_user.id

#     # Перевірка власності
#     user_checks = await get_issued_checks_for_user(user_id)
#     if not any(ch["code"] == invoice for ch in user_checks):
#         await callback.answer("❌ Цей чек вам не належить!", show_alert=True)
#         return

#     await callback.answer("🔄 Закриваємо чек...")

#     result = await close_invoice(invoice)

#     if not result or not result.get("success"):
#         await callback.message.edit_text("❌ Не вдалося закрити чек. Спробуйте пізніше.")
#         return

#     remaining = int(result.get("sum", 0))

#     if remaining > 0:
#         await add_to_balance(user_id, remaining)

#     await callback.message.edit_text(
#         f"✅ Чек <code>{invoice}</code> успішно закрито!\n\n"
#         f"💰 Повернено на баланс: <b>{remaining} грн</b>",
#         parse_mode="HTML"
#     )

#     # Повідомлення адміну
#     await callback.bot.send_message(
#         ADMIN_ID,
#         f"🔒 Користувач закрив чек Champion\n\n"
#         f"👤 {callback.from_user.full_name} (@{callback.from_user.username or '—'})\n"
#         f"🔑 Чек: <code>{invoice}</code>\n"
#         f"💰 Повернено: <b>{remaining} грн</b>",
#         parse_mode="HTML"
#     )


# @router.callback_query(F.data == "close_cancel")
# async def close_cancel(callback: CallbackQuery):
#     await callback.message.edit_text("❌ Закриття чека скасовано.")
#     await callback.answer()





# # ==================== ПОПОВНЕННЯ ЧЕКА CHAMPION ====================

# from handlers.casino_api import add_to_invoice, check_invoice
# from db import get_issued_checks_for_user, add_to_balance
# from aiogram.fsm.context import FSMContext
# from aiogram.fsm.state import StatesGroup, State


# class AddToCheckFSM(StatesGroup):
#     waiting_for_amount = State()


# @router.message(F.text == "💵 Поповнити чек")
# async def show_checks_to_topup(message: Message, state: FSMContext):
#     user_id = message.from_user.id
#     checks = await get_issued_checks_for_user(user_id)
    
#     champion_checks = [ch for ch in checks if "Champion" in ch.get("check_type", "")]

#     if not champion_checks:
#         await message.answer("❌ У вас немає виданих чеків Champion.")
#         return

#     text = "💵 **Оберіть чек для поповнення**\n\n"
#     buttons = []
#     active_count = 0

#     for ch in champion_checks:
#         code = ch["code"]
#         status = await check_invoice(code)
        
#         if not status or not status.get("success"):
#             continue
            
#         remaining = float(status.get("sum", 0))
#         # Показуємо навіть якщо 0, але не закриті (якщо API дозволяє)
#         active_count += 1
#         short = code[-6:]
        
#         text += f"🔑 <code>{code}</code> — 💰 {remaining:.0f} грн\n"
#         buttons.append([
#             InlineKeyboardButton(
#                 text=f"Поповнити •••{short} ({remaining:.0f} грн)",
#                 callback_data=f"topup_champ_{code}"
#             )
#         ])

#     if active_count == 0:
#         await message.answer("❌ Немає доступних чеків для поповнення.")
#         return

#     buttons.append([InlineKeyboardButton(text="❌ Скасувати", callback_data="topup_cancel")])

#     await message.answer(
#         text,
#         parse_mode="HTML",
#         reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
#     )


# @router.callback_query(F.data.startswith("topup_champ_"))
# async def start_topup_check(callback: CallbackQuery, state: FSMContext):
#     invoice = callback.data.removeprefix("topup_champ_")
    
#     await state.update_data(invoice=invoice)
#     await state.set_state(AddToCheckFSM.waiting_for_amount)

#     await callback.message.edit_text(
#         f"💵 Введіть суму поповнення для чека <code>{invoice}</code>\n"
#         f"(від 10 грн)",
#         parse_mode="HTML"
#     )
#     await callback.answer()


# @router.message(AddToCheckFSM.waiting_for_amount)
# async def process_topup_amount(message: Message, state: FSMContext):
#     try:
#         amount = int(message.text)
#         if amount < 10:
#             await message.answer("❌ Мінімальна сума поповнення — 10 грн")
#             return
#     except:
#         await message.answer("❌ Введіть число")
#         return

#     data = await state.get_data()
#     invoice = data.get("invoice")

#     user_id = message.from_user.id
#     balance = await get_balance(user_id)

#     if balance < amount:
#         await message.answer("❌ Недостатньо коштів на балансі.")
#         await state.clear()
#         return

#     # Поповнюємо чек
#     result = await add_to_invoice(invoice, amount)

#     if not result or not result.get("success"):
#         await message.answer("❌ Не вдалося поповнити чек. Спробуйте пізніше.")
#         await state.clear()
#         return

#     # Списуємо з балансу користувача
#     await add_to_balance(user_id, -amount)

#     new_sum = result.get("new_sum", amount)

#     await message.answer(
#         f"✅ Чек <code>{invoice}</code> успішно поповнено на <b>{amount} грн</b>\n\n"
#         f"Новий баланс чека: <b>{new_sum:.0f} грн</b>",
#         parse_mode="HTML"
#     )

#     # Повідомлення адміну
#     await message.bot.send_message(
#         ADMIN_ID,
#         f"💵 Користувач поповнив чек\n\n"
#         f"👤 {message.from_user.full_name} (@{message.from_user.username or '—'})\n"
#         f"🔑 Чек: <code>{invoice}</code>\n"
#         f"💰 Поповнено: <b>{amount} грн</b>",
#         parse_mode="HTML"
#     )

#     await state.clear()


# @router.callback_query(F.data == "topup_cancel")
# async def topup_cancel(callback: CallbackQuery, state: FSMContext):
#     await state.clear()
#     await callback.message.edit_text("❌ Поповнення скасовано.")
#     await callback.answer()



import re

from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from handlers.config import ADMIN_ID
from handlers.profile import notify_reward_progress
from db.check import get_checks_stats, clear_all_checks, get_checks_total_balance
from db import get_balance, add_to_balance, log_check_issued
from db import get_issued_checks_for_user
from handlers.menu import checks_menu
from handlers.casino_api import create_invoice, create_matic_checks, close_invoice, check_invoice, add_to_invoice

router = Router(name="admin_checks")


class CheckFSM(StatesGroup):
    waiting_for_custom_amount = State()      # Champion
    waiting_for_amount_topup = State()       # Поповнення


# ==================== КЛАВІАТУРИ ====================

def play_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🏆 Champion"), KeyboardButton(text="🎰 Matic")],
            [KeyboardButton(text="🔙 Назад до головного меню")]
        ],
        resize_keyboard=True
    )


def champion_main_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💰 Купити чек Champion")],
            [KeyboardButton(text="🔒 Закрити чек Champion")],
            [KeyboardButton(text="💵 Поповнити чек Champion")],
            [KeyboardButton(text="🔙 Назад")]
        ],
        resize_keyboard=True
    )


def matic_main_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💰 Купити чек Matic")],
            [KeyboardButton(text="🔒 Закрити чек Matic")],
            [KeyboardButton(text="💵 Поповнити чек Matic")],
            [KeyboardButton(text="🔙 Назад")]
        ],
        resize_keyboard=True
    )


def champion_amount_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="100 грн", callback_data="champ_amt_100"),
                InlineKeyboardButton(text="200 грн", callback_data="champ_amt_200"),
                InlineKeyboardButton(text="250 грн", callback_data="champ_amt_250"),
            ],
            [
                InlineKeyboardButton(text="✏️ Інша сума", callback_data="champ_amt_custom"),
                InlineKeyboardButton(text="❌ Скасувати", callback_data="champ_cancel")
            ]
        ]
    )


def matic_amount_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="100 грн", callback_data="matic_amt_100"),
                InlineKeyboardButton(text="200 грн", callback_data="matic_amt_200"),
            ],
            [InlineKeyboardButton(text="❌ Скасувати", callback_data="matic_cancel")]
        ]
    )


# ==================== ГОЛОВНЕ МЕНЮ ГРИ ====================

@router.message(F.text == "🎮 Грати")
async def play_menu(message: Message):
    balance = await get_balance(message.from_user.id)

    # === Перше повідомлення — Баланс + Інлайн кнопки ===
    inline_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="💰 Поповнити", callback_data="wallet_topup"),
                InlineKeyboardButton(text="👨‍💼 Касир", url="https://t.me/KaSSa_4444")
            ]
        ]
    )

    await message.answer(
        f"<b>💎 Ваш баланс:</b>\n\n"
        f"💰 <b>{balance:,} грн</b>\n",
        parse_mode="HTML",
        reply_markup=inline_kb
    )

    # === Друге повідомлення — Інформація про вивід + Основне меню ===
    await message.answer(
        "💸  Вивід лише через касира з 🕒 <b>9:00 до 00:00</b>\n\n",
        parse_mode="HTML",
        reply_markup=play_menu_kb()
    )

# ==================== CHAMPION ====================

@router.message(F.text == "🏆 Champion")
async def champion_menu(message: Message):
    await message.answer(
        "🏆 <b>Champion</b>\n\nОберіть дію:",
        parse_mode="HTML",
        reply_markup=champion_main_kb()
    )


@router.message(F.text == "💰 Купити чек Champion")
async def buy_champion(message: Message):
    await message.answer(
        "🏆 Оберіть суму Champion:",
        reply_markup=champion_amount_kb()
    )


# ==================== MATIC ====================

@router.message(F.text == "🎰 Matic")
async def matic_menu(message: Message):
    await message.answer(
        "🎰 <b>Matic</b>\n\nОберіть дію:",
        parse_mode="HTML",
        reply_markup=matic_main_kb()
    )


@router.message(F.text == "💰 Купити чек Matic")
async def buy_matic(message: Message):
    await message.answer(
        "🎰 Оберіть суму Matic:",
        reply_markup=matic_amount_kb()
    )


# ==================== ВИДАЧА ЧЕКІВ ====================

async def issue_champion_check(target_message: Message, user, amount: int):
    user_id = user.id
    invoice_data = await create_invoice(amount)

    if not invoice_data or not invoice_data.get("success"):
        await target_message.answer("❌ Помилка створення чека Champion.")
        return

    invoice_code = invoice_data["invoice"]
    game_url = invoice_data["url"]

    await add_to_balance(user_id, -amount)
    await log_check_issued(user_id, f"🏆 Champion {amount}", invoice_code, amount)
    await notify_reward_progress(target_message.bot, user_id, user.username, user.full_name or "")

    name = f"@{user.username}" if user.username else user.full_name or f"#{user_id}"
    await target_message.bot.send_message(
        ADMIN_ID,
        f"🎁 Видано Champion {amount} грн\n👤 {name}\n🔑 <code>{invoice_code}</code>",
        parse_mode="HTML"
    )

    await target_message.answer(
        f"✅ <b>Чек Champion видано!</b>\n\n"
        f"🔑 Код: <code>{invoice_code}</code>\n"
        f"🔗 {game_url}\n\n"
        f"💰 Залишок: {await get_balance(user_id)} грн",
        parse_mode="HTML",
        disable_web_page_preview=True
    )

    await target_message.answer("🏆 Champion меню:", reply_markup=champion_main_kb())


async def issue_matic_check(target_message: Message, user, amount: int, code: str):
    user_id = user.id

    await add_to_balance(user_id, -amount)
    await log_check_issued(user_id, f"🎰 Matic {amount}", code, amount)
    await notify_reward_progress(target_message.bot, user_id, user.username, user.full_name or "")

    name = f"@{user.username}" if user.username else user.full_name or f"#{user_id}"
    await target_message.bot.send_message(
        ADMIN_ID,
        f"🎁 Видано Matic {amount} грн\n👤 {name}\n🔑 <code>{code}</code>",
        parse_mode="HTML"
    )

    await target_message.answer(
        f"✅ <b>Чек Matic видано!</b>\n\n"
        f"🔑 Код: <code>{code}</code>\n"
        f"💰 Залишок: {await get_balance(user_id)} грн",
        parse_mode="HTML"
    )

    await target_message.answer("🎰 Matic меню:", reply_markup=matic_main_kb())


# ==================== CALLBACKS КУПІВЛІ ====================

@router.callback_query(F.data.startswith("champ_amt_"))
async def champion_pick_amount(callback: CallbackQuery, state: FSMContext):
    value = callback.data.removeprefix("champ_amt_")
    if value == "custom":
        await state.set_state(CheckFSM.waiting_for_custom_amount)
        await callback.message.edit_text("🏆 Введіть суму Champion (від 50 грн):")
        await callback.answer()
        return

    amount = int(value)
    if await get_balance(callback.from_user.id) < amount:
        await callback.answer("❌ Недостатньо коштів", show_alert=True)
        return

    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer()
    await issue_champion_check(callback.message, callback.from_user, amount)


@router.message(CheckFSM.waiting_for_custom_amount)
async def process_custom_champion(message: Message, state: FSMContext):
    try:
        amount = int(message.text)
        if amount < 50:
            await message.answer("❌ Мінімум 50 грн")
            return
    except:
        await message.answer("❌ Введіть число")
        return

    if await get_balance(message.from_user.id) < amount:
        await message.answer("❌ Недостатньо коштів")
        await state.clear()
        return

    await state.clear()
    await issue_champion_check(message, message.from_user, amount)


@router.callback_query(F.data == "champ_cancel")
async def champion_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Скасовано")
    await callback.answer()


@router.callback_query(F.data.startswith("matic_amt_"))
async def matic_pick_amount(callback: CallbackQuery):
    amount = int(callback.data.removeprefix("matic_amt_"))
    if await get_balance(callback.from_user.id) < amount:
        await callback.answer("❌ Недостатньо коштів", show_alert=True)
        return

    await callback.answer("🔄 Генеруємо...")
    try:
        result = await create_matic_checks(amount=amount, count=1)
        if result.get("created", 0) > 0 and result.get("codes"):
            code_info = result["codes"][0]
            code = code_info.get("code") or code_info.get("login") or code_info.get("key") or str(code_info)
            await callback.message.edit_reply_markup(reply_markup=None)
            await issue_matic_check(callback.message, callback.from_user, amount, code)
        else:
            await callback.message.edit_text("❌ Не вдалося створити Matic чек")
    except Exception as e:
        await callback.message.edit_text(f"❌ Помилка: {e}")


@router.callback_query(F.data == "matic_cancel")
async def matic_cancel(callback: CallbackQuery):
    await callback.message.edit_text("❌ Скасовано")
    await callback.answer()


# ==================== ЗАКРИТТЯ ТА ПОПОВНЕННЯ ====================

# @router.message(F.text == "🔒 Закрити чек Champion")
# async def show_my_champion_checks(message: Message):
#     user_id = message.from_user.id
#     checks = await get_issued_checks_for_user(user_id)
#     champion_checks = [ch for ch in checks if "Champion" in ch.get("check_type", "")]

#     if not champion_checks:
#         await message.answer("❌ У вас немає активних чеків Champion.")
#         return

#     text = "🔒 **Ваші чеки Champion**\n\nОберіть для закриття:\n\n"
#     buttons = []

#     for ch in champion_checks:
#         code = ch["code"]
#         status = await check_invoice(code)
#         if not status or not status.get("success"):
#             continue
#         remaining = float(status.get("sum", 0))
#         if remaining <= 0:
#             continue

#         short = code[-6:] if len(code) >= 6 else code
#         text += f"🔑 <code>{code}</code> — 💰 <b>{remaining:.0f} грн</b>\n"
#         buttons.append([InlineKeyboardButton(
#             text=f"🔒 Закрити •••{short} ({remaining:.0f} грн)",
#             callback_data=f"close_champ_{code}"
#         )])

#     buttons.append([InlineKeyboardButton(text="❌ Скасувати", callback_data="close_cancel")])

#     await message.answer(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))


# @router.message(F.text == "🔒 Закрити чек Matic")
# async def show_my_matic_checks(message: Message):
#     await message.answer("🔄 Функція закриття Matic чеків скоро буде доступна.")


# @router.callback_query(F.data.startswith("close_champ_"))
# async def process_close_check(callback: CallbackQuery):
#     invoice = callback.data.removeprefix("close_champ_")
#     user_id = callback.from_user.id

#     result = await close_invoice(invoice)
#     if not result or not result.get("success"):
#         await callback.message.edit_text("❌ Не вдалося закрити чек.")
#         return

#     remaining = int(result.get("sum", 0))
#     if remaining > 0:
#         await add_to_balance(user_id, remaining)

#     await callback.message.edit_text(
#         f"✅ Чек закрито!\nПовернено: <b>{remaining} грн</b>",
#         parse_mode="HTML"
#     )

#     await callback.bot.send_message(
#         ADMIN_ID,
#         f"🔒 Закрито Champion чек\nКористувач: {callback.from_user.full_name}\nПовернено: {remaining} грн",
#         parse_mode="HTML"
#     )


# @router.callback_query(F.data == "close_cancel")
# async def close_cancel(callback: CallbackQuery):
#     await callback.message.edit_text("❌ Скасовано")
#     await callback.answer()


# @router.message(F.text == "💵 Поповнити чек Champion")
# async def show_champion_to_topup(message: Message, state: FSMContext):
#     user_id = message.from_user.id
#     checks = await get_issued_checks_for_user(user_id)
#     champion_checks = [ch for ch in checks if "Champion" in ch.get("check_type", "")]

#     if not champion_checks:
#         await message.answer("❌ У вас немає чеків Champion.")
#         return

#     text = "💵 **Оберіть чек для поповнення**\n\n"
#     buttons = []

#     for ch in champion_checks:
#         code = ch["code"]
#         status = await check_invoice(code)
#         if not status or not status.get("success"):
#             continue
#         remaining = float(status.get("sum", 0))
#         short = code[-6:]
#         text += f"🔑 <code>{code}</code> — {remaining:.0f} грн\n"
#         buttons.append([InlineKeyboardButton(
#             text=f"Поповнити •••{short}",
#             callback_data=f"topup_champ_{code}"
#         )])

#     buttons.append([InlineKeyboardButton(text="❌ Скасувати", callback_data="topup_cancel")])
#     await message.answer(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))


# @router.message(F.text == "💵 Поповнити чек Matic")
# async def show_matic_to_topup(message: Message):
#     await message.answer("🔄 Функція поповнення Matic чеків скоро буде доступна.")


# @router.callback_query(F.data.startswith("topup_champ_"))
# async def start_topup(callback: CallbackQuery, state: FSMContext):
#     invoice = callback.data.removeprefix("topup_champ_")
#     await state.update_data(invoice=invoice)
#     await state.set_state(CheckFSM.waiting_for_amount_topup)
#     await callback.message.edit_text(
#         f"Введіть суму поповнення для чека <code>{invoice}</code> (від 10 грн):", 
#         parse_mode="HTML"
#     )


# @router.message(CheckFSM.waiting_for_amount_topup)
# async def process_topup_amount(message: Message, state: FSMContext):
#     try:
#         amount = int(message.text)
#         if amount < 10:
#             await message.answer("❌ Мінімум 10 грн")
#             return
#     except:
#         await message.answer("❌ Введіть число")
#         return

#     data = await state.get_data()
#     invoice = data.get("invoice")
#     user_id = message.from_user.id

#     if await get_balance(user_id) < amount:
#         await message.answer("❌ Недостатньо коштів")
#         await state.clear()
#         return

#     result = await add_to_invoice(invoice, amount)
#     if not result or not result.get("success"):
#         await message.answer("❌ Не вдалося поповнити чек")
#         await state.clear()
#         return

#     await add_to_balance(user_id, -amount)
#     new_sum = result.get("new_sum", amount)

#     await message.answer(
#         f"✅ Чек поповнено на <b>{amount} грн</b>\nНовий баланс: <b>{new_sum} грн</b>",
#         parse_mode="HTML"
#     )
#     await state.clear()


# @router.callback_query(F.data == "topup_cancel")
# async def topup_cancel(callback: CallbackQuery, state: FSMContext):
#     await state.clear()
#     await callback.message.edit_text("❌ Скасовано")
#     await callback.answer()


# ==================== ЗАКРИТТЯ ТА ПОПОВНЕННЯ ====================

from handlers.casino_api import SuperplatMatic

# Глобальний екземпляр API для Matic
matic_api = SuperplatMatic()


# ==================== CHAMPION ====================

@router.message(F.text == "🔒 Закрити чек Champion")
async def show_my_champion_checks(message: Message):
    user_id = message.from_user.id
    checks = await get_issued_checks_for_user(user_id)
    champion_checks = [ch for ch in checks if "Champion" in ch.get("check_type", "")]

    if not champion_checks:
        await message.answer("❌ У вас немає активних чеків Champion.")
        return

    text = "🔒 **Ваші активні чеки Champion**\n\nОберіть чек для закриття:\n\n"
    buttons = []
    active_count = 0

    for ch in champion_checks:
        code = ch["code"]
        try:
            status = await check_invoice(code)
            if not status or not status.get("success"):
                continue
            remaining = float(status.get("sum", 0))
            if remaining <= 0:
                continue

            active_count += 1
            short = code[-6:] if len(code) >= 6 else code
            text += f"🔑 <code>{code}</code> — 💰 <b>{remaining:.0f} грн</b>\n"
            
            buttons.append([
                InlineKeyboardButton(
                    text=f"🔒 Закрити •••{short} ({remaining:.0f} грн)",
                    callback_data=f"close_champ_{code}"
                )
            ])
        except:
            continue

    if active_count == 0:
        await message.answer("❌ Немає активних чеків Champion з балансом > 0.")
        return

    buttons.append([InlineKeyboardButton(text="❌ Скасувати", callback_data="close_cancel")])

    await message.answer(
        text, 
        parse_mode="HTML", 
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )


@router.message(F.text == "💵 Поповнити чек Champion")
async def show_champion_to_topup(message: Message, state: FSMContext):
    user_id = message.from_user.id
    checks = await get_issued_checks_for_user(user_id)
    champion_checks = [ch for ch in checks if "Champion" in ch.get("check_type", "")]

    if not champion_checks:
        await message.answer("❌ У вас немає чеків Champion.")
        return

    text = "💵 **Оберіть чек Champion для поповнення**\n\n"
    buttons = []

    for ch in champion_checks:
        code = ch["code"]
        try:
            status = await check_invoice(code)
            if not status or not status.get("success"):
                continue
            remaining = float(status.get("sum", 0))
            short = code[-6:]
            text += f"🔑 <code>{code}</code> — 💰 {remaining:.0f} грн\n"
            buttons.append([
                InlineKeyboardButton(
                    text=f"💵 Поповнити •••{short}",
                    callback_data=f"topup_champ_{code}"
                )
            ])
        except:
            continue

    if not buttons:
        await message.answer("❌ Немає доступних чеків для поповнення.")
        return

    buttons.append([InlineKeyboardButton(text="❌ Скасувати", callback_data="topup_cancel")])
    await message.answer(
        text, 
        parse_mode="HTML", 
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )


# ==================== MATIC ====================

@router.message(F.text == "🔒 Закрити чек Matic")
async def show_my_matic_checks(message: Message):
    user_id = message.from_user.id
    checks = await get_issued_checks_for_user(user_id)
    matic_checks = [ch for ch in checks if "Matic" in ch.get("check_type", "")]

    if not matic_checks:
        await message.answer("❌ У вас немає активних чеків Matic.")
        return

    text = "🔒 **Ваші активні чеки Matic**\n\nОберіть чек для закриття:\n\n"
    buttons = []
    active_count = 0

    for ch in matic_checks:
        code = ch["code"]
        try:
            status = await matic_api.check_code(code)
            remaining = float(status.get("balance", 0) / 100)  # переводимо з копійок

            if remaining <= 0:
                continue

            active_count += 1
            short = code[-6:] if len(code) >= 6 else code
            text += f"🔑 <code>{code}</code> — 💰 <b>{remaining:.0f} грн</b>\n"
            
            buttons.append([
                InlineKeyboardButton(
                    text=f"🔒 Закрити •••{short} ({remaining:.0f} грн)",
                    callback_data=f"close_matic_{code}"
                )
            ])
        except Exception as e:
            print(f"[Matic Check Error] {code}: {e}")
            continue

    if active_count == 0:
        await message.answer("❌ Немає активних Matic чеків з балансом > 0.")
        return

    buttons.append([InlineKeyboardButton(text="❌ Скасувати", callback_data="close_cancel")])

    await message.answer(
        text, 
        parse_mode="HTML", 
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )


@router.message(F.text == "💵 Поповнити чек Matic")
async def show_matic_to_topup(message: Message, state: FSMContext):
    user_id = message.from_user.id
    checks = await get_issued_checks_for_user(user_id)
    matic_checks = [ch for ch in checks if "Matic" in ch.get("check_type", "")]

    if not matic_checks:
        await message.answer("❌ У вас немає чеків Matic.")
        return

    text = "💵 **Оберіть Matic чек для поповнення**\n\n"
    buttons = []

    for ch in matic_checks:
        code = ch["code"]
        try:
            status = await matic_api.check_code(code)
            remaining = float(status.get("balance", 0) / 100)
            short = code[-6:]
            text += f"🔑 <code>{code}</code> — 💰 {remaining:.0f} грн\n"
            buttons.append([
                InlineKeyboardButton(
                    text=f"💵 Поповнити •••{short}",
                    callback_data=f"topup_matic_{code}"
                )
            ])
        except:
            continue

    if not buttons:
        await message.answer("❌ Немає доступних Matic чеків для поповнення.")
        return

    buttons.append([InlineKeyboardButton(text="❌ Скасувати", callback_data="topup_cancel")])
    await message.answer(
        text, 
        parse_mode="HTML", 
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )


# ==================== CALLBACKS ЗАКРИТТЯ ====================

@router.callback_query(F.data.startswith("close_champ_"))
async def process_close_champion(callback: CallbackQuery):
    invoice = callback.data.removeprefix("close_champ_")
    user_id = callback.from_user.id

    await callback.answer("🔄 Закриваємо чек...")

    result = await close_invoice(invoice)
    if not result or not result.get("success"):
        await callback.message.edit_text("❌ Не вдалося закрити чек Champion.")
        return

    remaining = int(result.get("sum", 0))
    if remaining > 0:
        await add_to_balance(user_id, remaining)

    await callback.message.edit_text(
        f"✅ Champion чек успішно закрито!\n\n"
        f"💰 Повернено на баланс: <b>{remaining} грн</b>",
        parse_mode="HTML"
    )

    await callback.bot.send_message(
        ADMIN_ID,
        f"🔒 Закрито Champion чек\n"
        f"Користувач: {callback.from_user.full_name}\n"
        f"Повернено: {remaining} грн",
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("close_matic_"))
async def process_close_matic(callback: CallbackQuery):
    code = callback.data.removeprefix("close_matic_")
    user_id = callback.from_user.id

    await callback.answer("🔄 Закриваємо Matic чек...")

    try:
        result = await matic_api.close_code(code)
        remaining = float(result.get("balance", result.get("sum", 0)) / 100)

        if remaining > 0:
            await add_to_balance(user_id, int(remaining))

        await callback.message.edit_text(
            f"✅ Matic чек успішно закрито!\n\n"
            f"💰 Повернено на баланс: <b>{remaining:.0f} грн</b>",
            parse_mode="HTML"
        )

        await callback.bot.send_message(
            ADMIN_ID,
            f"🔒 Закрито Matic чек\n"
            f"Користувач: {callback.from_user.full_name}\n"
            f"Повернено: {remaining:.0f} грн",
            parse_mode="HTML"
        )
    except Exception as e:
        await callback.message.edit_text(f"❌ Помилка при закритті Matic чека:\n{str(e)}")



# ==================== CALLBACKS ПОПОВНЕННЯ ====================

@router.callback_query(F.data.startswith("topup_champ_"))
async def start_topup_champion(callback: CallbackQuery, state: FSMContext):
    invoice = callback.data.removeprefix("topup_champ_")
    await state.update_data(invoice=invoice, check_type="champion")
    await state.set_state(CheckFSM.waiting_for_amount_topup)
    await callback.message.edit_text(
        f"💵 Введіть суму поповнення для чека <code>{invoice}</code>\n(від 10 грн)",
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("topup_matic_"))
async def start_topup_matic(callback: CallbackQuery, state: FSMContext):
    code = callback.data.removeprefix("topup_matic_")
    await state.update_data(matic_code=code, check_type="matic")
    await state.set_state(CheckFSM.waiting_for_amount_topup)
    await callback.message.edit_text(
        f"💵 Введіть суму поповнення для Matic чека <code>{code}</code>\n(від 10 грн)",
        parse_mode="HTML"
    )


@router.message(CheckFSM.waiting_for_amount_topup)
async def process_topup_amount(message: Message, state: FSMContext):
    try:
        amount = int(message.text)
        if amount < 10:
            await message.answer("❌ Мінімальна сума поповнення — 10 грн")
            return
    except:
        await message.answer("❌ Введіть тільки число")
        return

    user_id = message.from_user.id
    if await get_balance(user_id) < amount:
        await message.answer("❌ Недостатньо коштів на балансі.")
        await state.clear()
        return

    data = await state.get_data()
    check_type = data.get("check_type")

    try:
        if check_type == "champion":
            invoice = data.get("invoice")
            result = await add_to_invoice(invoice, amount)
            success = result and result.get("success")
            new_sum = result.get("new_sum", amount) if result else amount
        else:  # matic
            matic_code = data.get("matic_code")
            result = await matic_api.add_to_code(matic_code, amount)
            success = True
            new_sum = "Оновлено"

        if success:
            await add_to_balance(user_id, -amount)
            await message.answer(
                f"✅ Чек успішно поповнено на <b>{amount} грн</b>\n"
                f"Новий баланс чека: <b>{new_sum}</b>",
                parse_mode="HTML"
            )
        else:
            await message.answer("❌ Не вдалося поповнити чек.")
    except Exception as e:
        await message.answer(f"❌ Помилка: {str(e)}")

    await state.clear()


@router.callback_query(F.data == "close_cancel")
@router.callback_query(F.data == "topup_cancel")
async def cancel_action(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Дію скасовано.")
    await callback.answer()

# ==================== НАЗАД ====================

@router.message(F.text == "🔙 Назад")
async def back_handler(message: Message):
    await play_menu(message)


@router.message(F.text == "🔙 Назад до головного меню")
async def back_to_main(message: Message):
    await message.answer("Повертаємося в головне меню...", reply_markup=checks_menu())


# ==================== АДМІНКА ====================

@router.message(F.text == "📊 Чеки")
async def checks_stats(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    stats = await get_checks_stats()
    total_balance = await get_checks_total_balance()

    text = "💳 <b>Статистика чеків</b>\n\n"
    for name, count in stats.items():
        if "Champion" in name:
            continue
        text += f"{name}: <b>{count}</b>\n"

    text += f"\n💰 <b>Баланс чеків:</b> {total_balance} грн"

    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🧹 Очистити всі чеки", callback_data="clear_checks_ask")]]
    )

    await message.answer(text, parse_mode="HTML", reply_markup=kb)


@router.callback_query(F.data == "clear_checks_ask")
async def ask_clear(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Так, видалити", callback_data="clear_checks_confirm"),
         InlineKeyboardButton(text="❌ Скасувати", callback_data="clear_checks_cancel")]
    ])
    await callback.message.edit_text("⚠️ Видалити ВСІ чеки?", reply_markup=kb)


@router.callback_query(F.data == "clear_checks_confirm")
async def confirm_clear(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    await clear_all_checks()
    await callback.message.edit_text("🧹 Всі чеки видалено!")


@router.callback_query(F.data == "clear_checks_cancel")
async def cancel_clear(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    await callback.message.edit_text("❌ Скасовано")