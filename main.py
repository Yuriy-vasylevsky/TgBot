


# import logging
# import asyncio
# import re
# import random
# from typing import Any, Callable, Awaitable, Dict

# from aiogram import Bot, Dispatcher, F, types, BaseMiddleware
# from aiogram.enums import ParseMode
# from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
# from aiogram.filters import Command
# from aiogram.fsm.state import StatesGroup, State
# from aiogram.fsm.context import FSMContext
# from aiogram.client.default import DefaultBotProperties
# from aiogram.exceptions import TelegramForbiddenError  
# import config
# from db import (
#     init_db, save_user, get_all_users, get_all_users_info,
#     add_promocode, list_promocodes, check_promocode,
#     set_user_access, get_user_access
# )


# # Логування
# logging.basicConfig(level=logging.INFO)

# # ==========================
# # Ініціалізація бота
# # ==========================
# bot = Bot(
#     token=config.TOKEN,
#     default=DefaultBotProperties(parse_mode=ParseMode.HTML)
# )
# dp = Dispatcher()

# # ==========================
# # Налаштування
# # ==========================
# ADMIN_ID = 6335987620
# DB_NAME = "users.db"

# # ==========================
# # Middleware: збереження юзерів
# # ==========================
# class SaveUserMiddleware(BaseMiddleware):
#     async def __call__(
#         self,
#         handler: Callable[[types.TelegramObject, Dict[str, Any]], Awaitable[Any]],
#         event: types.TelegramObject,
#         data: Dict[str, Any]
#     ) -> Any:
#         if isinstance(event, types.Message) and event.from_user:
#             save_user(event.from_user.id, event.from_user.username, event.from_user.full_name)
#         return await handler(event, data)

# dp.message.middleware(SaveUserMiddleware())

# # ==========================
# # Меню
# # ==========================
# def main_menu(is_admin=False):
#     keyboard = [
#         ["🎟 Ввести промокод"],
#         ["💫 КОД в посилання"],
#         ["🎲 Група", "💎 Касир"],
#         ["💳 Номер карти", "❓ Як грати"],
#         ["💲 Вивід", "🔹 Акції"],
#         ["💥 Демо гра"]
#     ]
#     if is_admin:
#         keyboard.append(["⚙️ Адмін панель"])
#     return ReplyKeyboardMarkup(
#         keyboard=[[KeyboardButton(text=b) for b in row] for row in keyboard],
#         resize_keyboard=True
#     )

# def games_menu():
#     keyboard = [
#         # ["🎮 Морський бій", "🎲 Сейф"],
#         [ "🎯 Один з трьох", "🎰 Слоти"],  # Нова гра
#         ["🔙 Назад до головного меню"]
#     ]
#     return ReplyKeyboardMarkup(
#         keyboard=[[KeyboardButton(text=b) for b in row] for row in keyboard],
#         resize_keyboard=True
#     )

# def actions_menu():
#     keyboard = [
#         ["🔙 Назад до головного меню"],
#         ["🎮 Морський бій", "🎲 Сейф"],
#         ["🃏 Cash Back"]
#     ]
#     return ReplyKeyboardMarkup(
#         keyboard=[[KeyboardButton(text=b) for b in row] for row in keyboard],
#         resize_keyboard=True
#     )

# def admin_menu():
#     keyboard = [
#         ["📢 Розсилка"],
#         ["👥 Список користувачів"],
#         ["➕ Створити промокод"],
#         ["🎟 Активні промокоди"],
#         ["🔙 Назад до головного меню"]
#     ]
#     return ReplyKeyboardMarkup(
#         keyboard=[[KeyboardButton(text=b) for b in row] for row in keyboard],
#         resize_keyboard=True
#     )

# # ==========================
# # FSM
# # ==========================
# class Broadcast(StatesGroup):
#     waiting_for_text = State()

# class PromoFSM(StatesGroup):
#     waiting_for_code = State()

# class EnterPromoFSM(StatesGroup):
#     waiting_for_code = State()

# class CodeLinkFSM(StatesGroup):
#     waiting_for_code = State()

# class CouponGameFSM(StatesGroup):
#     playing = State()

# # ==========================
# # Хендлери
# # ==========================
# @dp.message(Command("start"))
# async def cmd_start(message: types.Message):
#     user = message.from_user
#     if user:
#         save_user(user.id, user.username, user.full_name)
#         is_admin = (user.id == ADMIN_ID)
#     else:
#         is_admin = False

#     await message.answer_photo(
#         photo=types.FSInputFile("images/4444.jpg"),
#         caption="🎰 НАЙКРАЩИЙ ІГРОВИЙ ДОСВІД ЧЕКАЄ НА ВАС У ЧЕТВІРКАХ! 🎰",
#         reply_markup=main_menu(is_admin=is_admin)
#     )

# # --- Адмін панель ---
# @dp.message(F.text == "⚙️ Адмін панель")
# async def admin_panel(message: types.Message):
#     if message.from_user and message.from_user.id == ADMIN_ID:
#         await message.answer("🔐 Адмін панель", reply_markup=admin_menu())
#     else:
#         await message.answer("⛔ У вас немає доступу")

# @dp.message(F.text == "👥 Список користувачів")
# async def list_users(message: types.Message):
#     if message.from_user.id != ADMIN_ID:
#         return
#     users = get_all_users_info()
#     if not users:
#         await message.answer("❌ Користувачів ще немає")
#         return

#     text = "👥 Користувачі:\n\n"
#     for i, (uid, username, full_name) in enumerate(users, start=1):
#         text += (
#             f"{i}. Ім'я: {full_name}\n"
#             f"   Нік: @{username or '---'}\n"
#             f"   ID: <code>{uid}</code>\n\n"
#         )
#     await message.answer(text)


# @dp.message(F.text == "📢 Розсилка")
# async def start_broadcast(message: types.Message, state: FSMContext):
#     if message.from_user.id != ADMIN_ID:
#         return
#     await state.set_state(Broadcast.waiting_for_text)
#     await message.answer("✍️ Введіть текст розсилки:")

# @dp.message(Broadcast.waiting_for_text)
# async def send_broadcast(msg: types.Message, state: FSMContext):
#     if msg.from_user.id != ADMIN_ID:
#         return
#     users = get_all_users()
#     success = 0
#     for uid in users:
#         try:
#             await bot.send_message(uid, msg.text or "")
#             success += 1
#         except Exception as e:
#             logging.error(f"Не зміг відправити {uid}: {e}")
#     await msg.answer(f"✅ Розсилка завершена. Відправлено {success}/{len(users)}")
#     await state.clear()

# # --- Промокоди ---
# @dp.message(F.text == "➕ Створити промокод")
# async def create_promocode(message: types.Message, state: FSMContext):
#     if message.from_user.id != ADMIN_ID:
#         return
#     await state.set_state(PromoFSM.waiting_for_code)
#     await message.answer("Введіть новий промокод:")

# @dp.message(PromoFSM.waiting_for_code)
# async def save_promocode_handler(message: types.Message, state: FSMContext):
#     if message.from_user.id != ADMIN_ID:
#         return
#     code = message.text.strip()
#     add_promocode(code)
#     await message.answer(f"✅ Промокод <b>{code}</b> збережений", reply_markup=admin_menu())
#     await state.clear()

# @dp.message(F.text == "🎟 Активні промокоди")
# async def show_promocodes(message: types.Message):
#     if message.from_user.id != ADMIN_ID:
#         return
#     codes = list_promocodes()
#     if not codes:
#         await message.answer("❌ Немає активних промокодів")
#     else:
#         text = "🎟 Активні промокоди:\n\n" + "\n".join(codes)
#         await message.answer(text)

# # --- Промокод для користувача ---
# @dp.message(F.text == "🎟 Ввести промокод")
# async def enter_promocode(message: types.Message, state: FSMContext):
#     await state.set_state(EnterPromoFSM.waiting_for_code)
#     await message.answer("Введіть ваш промокод:")

# @dp.message(EnterPromoFSM.waiting_for_code)
# async def check_user_promo(message: types.Message, state: FSMContext):
#     code = message.text.strip()
#     if check_promocode(code):
#         set_user_access(message.from_user.id, True)
#         await message.answer("✅ Промокод активований! Доступ до ігор відкритий 🎮", reply_markup=games_menu())
#     else:
#         await message.answer("❌ Невірний або вже використаний промокод", reply_markup=main_menu(is_admin=(message.from_user.id == ADMIN_ID)))
#     await state.clear()

# # --- КОД в посилання ---
# @dp.message(F.text == "💫 КОД в посилання")
# async def ask_code_for_links(message: types.Message, state: FSMContext):
#     await state.set_state(CodeLinkFSM.waiting_for_code)
#     await message.answer("Введіть код у форматі: 00-00-00-00-00-00-00")

# @dp.message(lambda message: re.fullmatch(r'\d{2}(-\d{2}){6}', message.text or ""))
# async def global_code_to_links(message: types.Message):
#     code = (message.text or "").replace("-", "")
#     await message.answer(f"Чемпіон https://spinplanet.net/?login_code={code}")
#     await message.answer(f"Суперматік https://code.greenhost.pw/?c={code}")

# # --- Гра Купон ---
# @dp.message(F.text == "🎯 Один з трьох")
# async def start_coupon_game(message: types.Message, state: FSMContext):
#     if not get_user_access(message.from_user.id):
#         await message.answer("⛔ У вас немає доступу. Активуйте промокод!")
#         return

#     await state.set_state(CouponGameFSM.playing)
#     await message.answer(
#         "🎯 <b>Гра Купон!</b>\n\n"
#         "Правила прості:\n"
#         "У тебе є 3 кнопки. Лише одна виграшна ✅\n"
#         "Можна грати тільки один раз.\n\n"
#         "Обери свій варіант:",
#         reply_markup=ReplyKeyboardMarkup(
#             keyboard=[
#                 [KeyboardButton(text="🎁 Варіант 1")],
#                 [KeyboardButton(text="🎁 Варіант 2")],
#                 [KeyboardButton(text="🎁 Варіант 3")],
#             ],
#             resize_keyboard=True
#         )
#     )

# # ==========================
# # 🎰 СЛОТИ ЗА КУПОНИ
# # ==========================
# class SlotGameFSM(StatesGroup):
#     playing = State()

# @dp.message(F.text == "🎰 Слоти")
# async def start_slots(message: types.Message, state: FSMContext):
#     """Початок гри"""
#     if not get_user_access(message.from_user.id):
#         await message.answer("⛔ У вас немає доступу. Активуйте промокод!")
#         return

#     await state.set_state(SlotGameFSM.playing)
#     await state.update_data(coupons=10)
#     await show_slot_menu(message, state)


# async def show_slot_menu(message: types.Message, state: FSMContext):
#     """Меню вибору ставки"""
#     data = await state.get_data()
#     coupons = data.get("coupons", 10)

#     await message.answer(
#         f"🎰 <b>Слоти</b>\n\n"
#         f"Ваш баланс: <b>{coupons}</b> купонів\n"
#         "Оберіть ставку:",
#         reply_markup=ReplyKeyboardMarkup(
#             keyboard=[
#                 [KeyboardButton(text="1 купон"), KeyboardButton(text="2 купони"), KeyboardButton(text="3 купони")],
#                 [KeyboardButton(text="💰 Забрати виграш")],
#                 [KeyboardButton(text="🔙 Вийти з гри")]
#             ],
#             resize_keyboard=True
#         )
#     )


# @dp.message(SlotGameFSM.playing)
# async def slot_spin(message: types.Message, state: FSMContext):
#     """Основна логіка слотів"""
#     text = message.text.strip()

#     # Вихід
#     if text == "🔙 Вийти з гри":
#         await message.answer("❌ Ви вийшли з гри.", reply_markup=main_menu(is_admin=(message.from_user.id == ADMIN_ID)))
#         await state.clear()
#         return

#     # Забрати виграш
#     if text == "💰 Забрати виграш":
#         data = await state.get_data()
#         coupons = data.get("coupons", 10)
#         await message.answer(f"💰 Ви забрали {coupons} купонів!", reply_markup=main_menu(is_admin=(message.from_user.id == ADMIN_ID)))

#         # Сповіщення адміна
#         await bot.send_message(
#             ADMIN_ID,
#             f"👤 <b>@{message.from_user.username or message.from_user.full_name}</b> забрав {coupons} купонів у слотах 🎰"
#         )
#         await state.clear()
#         return

#     # Обробка ставки
#     try:
#         bet = int(text.split()[0])
#     except ValueError:
#         await message.answer("⚠️ Виберіть ставку з кнопок.")
#         return

#     data = await state.get_data()
#     coupons = data.get("coupons", 10)

#     if bet > coupons:
#         await message.answer("⚠️ Недостатньо купонів для цієї ставки.")
#         return

#     import random
#     # Більше символів → зменшує ймовірність виграшу
#     symbols = ["🍒", "🍋", "🍊",  "🍇", "🍉", "🍓", "🍍", "🥭", "🃏", 💎]
#     reels = [random.choice(symbols) for _ in range(3)]

#     # Логіка виграшів
#     if reels[0] == reels[1] == reels[2]:
#         multiplier = 12  # Джекпот рідкісний
#         outcome = "🎉 Джекпот! 3 однакових символи!"
#     elif reels[0] == reels[1] or reels[1] == reels[2] or reels[0] == reels[2]:
#         multiplier = 4  # Менший виграш за пару
#         outcome = "✨ Є пара символів!"
#     else:
#         multiplier = 0
#         outcome = "❌ Програш!"

#     win_amount = int(bet * multiplier)
#     coupons = coupons - bet + win_amount

#     await state.update_data(coupons=coupons)


#     await message.answer(
#         f"🎰 {reels[0]} | {reels[1]} | {reels[2]}\n\n"
#         f"{outcome}\n"
#         f"Ставка: {bet}\n"
#         f"Виграш: {win_amount}\n"
#         f"Баланс: {coupons}"
#     )

#     # Програш (0 купонів)
#     if coupons <= 0:
#         await message.answer("💀 Ви програли всі купони! Гра завершена.", reply_markup=main_menu(is_admin=(message.from_user.id == ADMIN_ID)))
#         await bot.send_message(
#             ADMIN_ID,
#             f"💀 <b>@{message.from_user.username or message.from_user.full_name}</b> програв усі купони в слотах."
#         )
#         await state.clear()
#         return

#     # Перемога (30 купонів)
#     if coupons >= 30:
#         await message.answer("🎉 Ви досягли максимального виграшу (30 купонів)! Гра завершена 🎯", reply_markup=main_menu(is_admin=(message.from_user.id == ADMIN_ID)))
#         await bot.send_message(
#             ADMIN_ID,
#             f"🏆 <b>@{message.from_user.username or message.from_user.full_name}</b> виграв {coupons} купонів у слотах (досяг максимуму)."
#         )
#         await state.clear()
#         return

#     # Якщо ще не кінець — показати меню знову
#     await show_slot_menu(message, state)


# # =====================================

# @dp.message(CouponGameFSM.playing)
# async def coupon_game_choice(message: types.Message, state: FSMContext):
#     import random
#     winning_button = random.choice(["🎁 Варіант 1", "🎁 Варіант 2", "🎁 Варіант 3"])
#     user_choice = message.text

#     if user_choice == winning_button:
#         result_text = "🎉 Вітаю! Ви виграли 30 грн! Адмін вам сам напише і видасть код✅"
#         outcome = "ВИГРАВ ✅"
#     else:
#         result_text = f"❌ На жаль, ви програли.\nВиграш був у кнопці: {winning_button}"
#         outcome = "ПРОГРАВ ❌"

#     # повідомляємо адміна у будь-якому випадку
#     await bot.send_message(
#         ADMIN_ID,
#         f"🎯 Гравець зіграв у 'Гра Купон'\n\n"
#         f"ID: {message.from_user.id}\n"
#         f"Username: @{message.from_user.username or '---'}\n"
#         f"Ім'я: {message.from_user.full_name}\n"
#         f"Вибір: {user_choice}\n"
#         f"Результат: {outcome}"
#     )

#     await message.answer(
#         result_text + "\n\n🔙 Повертаємось у головне меню.",
#         reply_markup=main_menu(is_admin=(message.from_user.id == ADMIN_ID))
#     )
#     await state.clear()


# # --- Назад у головне меню ---
# @dp.message(F.text == "🔙 Назад до головного меню")
# async def back_to_main(message: types.Message, state: FSMContext):
#     await state.clear()
#     is_admin = (message.from_user.id == ADMIN_ID)
#     await message.answer("🔙 Повернення у головне меню", reply_markup=main_menu(is_admin=is_admin))

# # --- Інші кнопки ---
# @dp.message(F.text == "🎲 Група")
# async def send_group(message: types.Message):
#     await message.answer(f"Приєднуйтесь до нашої групи: {config.GROUP_LINK}")

# @dp.message(F.text == "💎 Касир")
# async def send_casher(message: types.Message):
#     await message.answer(f"Касир: {config.CONTACT_PHONE}")

# @dp.message(F.text == "💳 Номер карти")
# async def send_card(message: types.Message):
#     await message.answer(config.CARD_NUMBER)

# @dp.message(F.text == "❓ Як грати")
# async def send_help(message: types.Message):
#     await message.answer(config.HALP)

# @dp.message(F.text == "💥 Демо гра")
# async def send_demo(message: types.Message):
#     await message.answer(config.DEMO)

# @dp.message(F.text == "💲 Вивід")
# async def send_output(message: types.Message):
#     await message.answer(f"Для виводу напишіть нашому касиру: {config.CONTACT_PHONE}")

# @dp.message(F.text == "🎮 Морський бій")
# async def send_mb(message: types.Message):
#     await message.answer_photo(types.FSInputFile("images/1.jpg"), caption=config.AK1)

# @dp.message(F.text == "🎲 Сейф")
# async def send_seif(message: types.Message):
#     await message.answer_photo(types.FSInputFile("images/2.jpg"), caption=config.AK2)

# @dp.message(F.text == "🃏 Cash Back")
# async def send_cash(message: types.Message):
#     await message.answer_photo(types.FSInputFile("images/3.jpg"), caption=config.AK3)

# @dp.message(F.text == "🔹 Акції")
# async def send_actions(message: types.Message):
#     await message.answer("Оберіть одну з наших акцій:", reply_markup=actions_menu())

# # ==========================
# # Запуск
# # ==========================
# async def main():
#     init_db()
#     logging.info("Бот запущений ✅")
#     await dp.start_polling(bot)

# if __name__ == "__main__":
#     asyncio.run(main())


# bot.py
import logging
import asyncio
import re
import random
from typing import Any, Callable, Awaitable, Dict, Optional

from aiogram import Bot, Dispatcher, F, types, BaseMiddleware
from aiogram.enums import ParseMode
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.client.default import DefaultBotProperties

import config  # переконайся що є config.py з TOKEN та іншими константами
from db import (
    init_db, save_user, get_all_users, get_all_users_info,
    add_promocode, list_promocodes, check_promocode,
    set_user_access, get_user_access,
    add_game_result, get_all_stats
)

# Логування
logging.basicConfig(level=logging.INFO)

# ==========================
# Ініціалізація бота
# ==========================
bot = Bot(
    token=config.TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

# ==========================
# Налаштування
# ==========================
ADMIN_ID = config.ADMIN_ID  # постав в config.py свій адмін ID

# ==========================
# Middleware: збереження юзерів
# ==========================
class SaveUserMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[types.TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: types.TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        if isinstance(event, types.Message) and event.from_user:
            await save_user(event.from_user.id, event.from_user.username, event.from_user.full_name)
        return await handler(event, data)

dp.message.middleware(SaveUserMiddleware())

# ==========================
# Меню
# ==========================
def main_menu(is_admin=False):
    keyboard = [
        ["🎟 Ввести промокод"],
        ["💫 КОД в посилання"],
        ["🎲 Група", "💎 Касир"],
        ["💳 Номер карти", "❓ Як грати"],
        ["💲 Вивід", "🔹 Акції"],
        ["💥 Демо гра"]
    ]
    if is_admin:
        keyboard.append(["⚙️ Адмін панель"])
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=b) for b in row] for row in keyboard],
        resize_keyboard=True
    )

def games_menu():
    keyboard = [
        [ "🎯 Один з трьох", "🎰 Слоти"],
        ["🔙 Назад до головного меню"]
    ]
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=b) for b in row] for row in keyboard],
        resize_keyboard=True
    )

def actions_menu():
    keyboard = [
        ["🔙 Назад до головного меню"],
        ["🎮 Морський бій", "🎲 Сейф"],
        ["🃏 Cash Back"]
    ]
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=b) for b in row] for row in keyboard],
        resize_keyboard=True
    )

def admin_menu():
    keyboard = [
        ["📢 Розсилка"],
        ["👥 Список користувачів"],
        ["➕ Створити промокод"],
        ["🎟 Активні промокоди"],
        ["📊 Статистика ігор"],
        ["🔙 Назад до головного меню"]
    ]
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=b) for b in row] for row in keyboard],
        resize_keyboard=True
    )

# ==========================
# FSM
# ==========================
class Broadcast(StatesGroup):
    waiting_for_text = State()

class PromoFSM(StatesGroup):
    waiting_for_code = State()

class EnterPromoFSM(StatesGroup):
    waiting_for_code = State()

class CodeLinkFSM(StatesGroup):
    waiting_for_code = State()

class CouponGameFSM(StatesGroup):
    playing = State()

class SlotGameFSM(StatesGroup):
    playing = State()

# ==========================
# Хендлери
# ==========================
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user = message.from_user
    if user:
        await save_user(user.id, user.username, user.full_name)
        is_admin = (user.id == ADMIN_ID)
    else:
        is_admin = False

    # Відправляємо фото, якщо є файл — інакше просто текст
    try:
        await message.answer_photo(
            photo=types.FSInputFile("images/4444.jpg"),
            caption="🎰 НАЙКРАЩИЙ ІГРОВИЙ ДОСВІД ЧЕКАЄ НА ВАС У ЧЕТВІРКАХ! 🎰",
            reply_markup=main_menu(is_admin=is_admin)
        )
    except Exception:
        await message.answer("🎰 Ласкаво просимо!", reply_markup=main_menu(is_admin=is_admin))

# --- Адмін панель ---
@dp.message(F.text == "⚙️ Адмін панель")
async def admin_panel(message: types.Message):
    if message.from_user and message.from_user.id == ADMIN_ID:
        await message.answer("🔐 Адмін панель", reply_markup=admin_menu())
    else:
        await message.answer("⛔ У вас немає доступу")

@dp.message(F.text == "👥 Список користувачів")
async def list_users(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    users = await get_all_users_info()
    if not users:
        await message.answer("❌ Користувачів ще немає")
        return

    text = "👥 Користувачі:\n\n"
    for i, (uid, username, full_name) in enumerate(users, start=1):
        text += (
            f"{i}. Ім'я: {full_name}\n"
            f"   Нік: @{username or '---'}\n"
            f"   ID: <code>{uid}</code>\n\n"
        )
    await message.answer(text)

@dp.message(F.text == "📢 Розсилка")
async def start_broadcast(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await state.set_state(Broadcast.waiting_for_text)
    await message.answer("✍️ Введіть текст розсилки:")

@dp.message(Broadcast.waiting_for_text)
async def send_broadcast(msg: types.Message, state: FSMContext):
    if msg.from_user.id != ADMIN_ID:
        return
    users = await get_all_users()
    success = 0
    for uid in users:
        try:
            await bot.send_message(uid, msg.text or "")
            success += 1
        except Exception as e:
            logging.error(f"Не зміг відправити {uid}: {e}")
    await msg.answer(f"✅ Розсилка завершена. Відправлено {success}/{len(users)}")
    await state.clear()

# --- Промокоди ---
@dp.message(F.text == "➕ Створити промокод")
async def create_promocode(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await state.set_state(PromoFSM.waiting_for_code)
    await message.answer("Введіть новий промокод:")

@dp.message(PromoFSM.waiting_for_code)
async def save_promocode_handler(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    code = message.text.strip()
    await add_promocode(code)
    await message.answer(f"✅ Промокод <b>{code}</b> збережений", reply_markup=admin_menu())
    await state.clear()

@dp.message(F.text == "🎟 Активні промокоди")
async def show_promocodes(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    codes = await list_promocodes()
    if not codes:
        await message.answer("❌ Немає активних промокодів")
    else:
        text = "🎟 Активні промокоди:\n\n" + "\n".join(codes)
        await message.answer(text)

# --- Промокод для користувача ---
@dp.message(F.text == "🎟 Ввести промокод")
async def enter_promocode(message: types.Message, state: FSMContext):
    await state.set_state(EnterPromoFSM.waiting_for_code)
    await message.answer("Введіть ваш промокод:")

@dp.message(EnterPromoFSM.waiting_for_code)
async def check_user_promo(message: types.Message, state: FSMContext):
    code = message.text.strip()
    if await check_promocode(code):
        await set_user_access(message.from_user.id, True)
        await message.answer("✅ Промокод активований! Доступ до ігор відкритий 🎮", reply_markup=games_menu())
    else:
        await message.answer("❌ Невірний або вже використаний промокод", reply_markup=main_menu(is_admin=(message.from_user.id == ADMIN_ID)))
    await state.clear()

# --- КОД в посилання ---
@dp.message(F.text == "💫 КОД в посилання")
async def ask_code_for_links(message: types.Message, state: FSMContext):
    await state.set_state(CodeLinkFSM.waiting_for_code)
    await message.answer("Введіть код у форматі: 00-00-00-00-00-00-00")

@dp.message(lambda message: re.fullmatch(r'\d{2}(-\d{2}){6}', message.text or ""))
async def global_code_to_links(message: types.Message):
    code = (message.text or "").replace("-", "")
    await message.answer(f"Чемпіон https://spinplanet.net/?login_code={code}")
    await message.answer(f"Суперматік https://code.greenhost.pw/?c={code}")

# --- Гра Купон ---
@dp.message(F.text == "🎯 Один з трьох")
async def start_coupon_game(message: types.Message, state: FSMContext):
    if not await get_user_access(message.from_user.id):
        await message.answer("⛔ У вас немає доступу. Активуйте промокод!")
        return

    await state.set_state(CouponGameFSM.playing)
    await message.answer(
        "🎯 <b>Гра Купон!</b>\n\n"
        "Правила прості:\n"
        "У тебе є 3 кнопки. Лише одна виграшна ✅\n"
        "Можна грати тільки один раз.\n\n"
        "Обери свій варіант:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="🎁 Варіант 1")],
                [KeyboardButton(text="🎁 Варіант 2")],
                [KeyboardButton(text="🎁 Варіант 3")],
            ],
            resize_keyboard=True
        )
    )

@dp.message(CouponGameFSM.playing)
async def coupon_game_choice(message: types.Message, state: FSMContext):
    winning_button = random.choice(["🎁 Варіант 1", "🎁 Варіант 2", "🎁 Варіант 3"])
    user_choice = message.text

    if user_choice == winning_button:
        result_text = "🎉 Вітаю! Ви виграли 30 грн! Адмін вам сам напише і видасть код✅"
        outcome = "ВИГРАВ ✅"
        is_win = True
    else:
        result_text = f"❌ На жаль, ви програли.\nВиграш був у кнопці: {winning_button}"
        outcome = "ПРОГРАВ ❌"
        is_win = False

    # повідомляємо адміна у будь-якому випадку
    await bot.send_message(
        ADMIN_ID,
        f"🎯 Гравець зіграв у 'Гра Купон'\n\n"
        f"ID: {message.from_user.id}\n"
        f"Username: @{message.from_user.username or '---'}\n"
        f"Ім'я: {message.from_user.full_name}\n"
        f"Вибір: {user_choice}\n"
        f"Результат: {outcome}"
    )

    # Запис результату в БД (агрегована статистика по грі "Купон")
    try:
        await add_game_result("Купон", is_win)
    except Exception as e:
        logging.error("Error saving coupon game stat: %s", e)

    await message.answer(
        result_text + "\n\n🔙 Повертаємось у головне меню.",
        reply_markup=main_menu(is_admin=(message.from_user.id == ADMIN_ID))
    )
    await state.clear()

# ==========================
# 🎰 СЛОТИ ЗА КУПОНИ
# ==========================
@dp.message(F.text == "🎰 Слоти")
async def start_slots(message: types.Message, state: FSMContext):
    """Початок гри"""
    if not await get_user_access(message.from_user.id):
        await message.answer("⛔ У вас немає доступу. Активуйте промокод!")
        return

    await state.set_state(SlotGameFSM.playing)
    await state.update_data(coupons=10)
    await show_slot_menu(message, state)

async def show_slot_menu(message: types.Message, state: FSMContext):
    data = await state.get_data()
    coupons = data.get("coupons", 10)

    await message.answer(
        f"🎰 <b>Слоти</b>\n\n"
        f"Ваш баланс: <b>{coupons}</b> купонів\n"
        "Оберіть ставку:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="1 купон"), KeyboardButton(text="2 купони"), KeyboardButton(text="3 купони")],
                [KeyboardButton(text="💰 Забрати виграш")],
                [KeyboardButton(text="🔙 Вийти з гри")]
            ],
            resize_keyboard=True
        )
    )

@dp.message(SlotGameFSM.playing)
async def slot_spin(message: types.Message, state: FSMContext):
    text = (message.text or "").strip()

    # Вихід
    if text == "🔙 Вийти з гри":
        await message.answer("❌ Ви вийшли з гри.", reply_markup=main_menu(is_admin=(message.from_user.id == ADMIN_ID)))
        await state.clear()
        return

    # Забрати виграш
    if text == "💰 Забрати виграш":
        data = await state.get_data()
        coupons = data.get("coupons", 10)
        await message.answer(f"💰 Ви забрали {coupons} купонів!", reply_markup=main_menu(is_admin=(message.from_user.id == ADMIN_ID)))
        await bot.send_message(
            ADMIN_ID,
            f"👤 <b>@{message.from_user.username or message.from_user.full_name}</b> забрав {coupons} купонів у слотах 🎰"
        )
        await state.clear()
        return

    # Обробка ставки
    try:
        bet = int(text.split()[0])
    except Exception:
        await message.answer("⚠️ Виберіть ставку з кнопок.")
        return

    data = await state.get_data()
    coupons = data.get("coupons", 10)

    if bet > coupons:
        await message.answer("⚠️ Недостатньо купонів для цієї ставки.")
        return

    # Символи — всі як строки
    symbols = ["🍒", "🍋", "🍊", "🍇", "🍉", "🍓", "🍍", "🥭", "🃏", "💎"]
    reels = [random.choice(symbols) for _ in range(3)]

    # Логіка виграшів
    if reels[0] == reels[1] == reels[2]:
        multiplier = 12  # Джекпот рідкісний
        outcome = "🎉 Джекпот! 3 однакових символи!"
    elif reels[0] == reels[1] or reels[1] == reels[2] or reels[0] == reels[2]:
        multiplier = 4  # Менший виграш за пару
        outcome = "✨ Є пара символів!"
    else:
        multiplier = 0
        outcome = "❌ Програш!"

    win_amount = int(bet * multiplier)
    coupons = coupons - bet + win_amount

    await state.update_data(coupons=coupons)

    await message.answer(
        f"🎰 {reels[0]} | {reels[1]} | {reels[2]}\n\n"
        f"{outcome}\n"
        f"Ставка: {bet}\n"
        f"Виграш: {win_amount}\n"
        f"Баланс: {coupons}"
    )

    # Записуємо результат у статистику по грі "Слоти"
    try:
        await add_game_result("Слоти", multiplier > 0)
    except Exception as e:
        logging.error("Error saving slots game stat: %s", e)

    # Програш (0 купонів)
    if coupons <= 0:
        await message.answer("💀 Ви програли всі купони! Гра завершена.", reply_markup=main_menu(is_admin=(message.from_user.id == ADMIN_ID)))
        await bot.send_message(
            ADMIN_ID,
            f"💀 <b>@{message.from_user.username or message.from_user.full_name}</b> програв усі купони в слотах."
        )
        await state.clear()
        return

    # Перемога (30 купонів)
    if coupons >= 30:
        await message.answer("🎉 Ви досягли максимального виграшу (30 купонів)! Гра завершена 🎯", reply_markup=main_menu(is_admin=(message.from_user.id == ADMIN_ID)))
        await bot.send_message(
            ADMIN_ID,
            f"🏆 <b>@{message.from_user.username or message.from_user.full_name}</b> виграв {coupons} купонів у слотах (досяг максимуму)."
        )
        await state.clear()
        return

    # Якщо ще не кінець — показати меню знову
    await show_slot_menu(message, state)

# --- Назад у головне меню ---
@dp.message(F.text == "🔙 Назад до головного меню")
async def back_to_main(message: types.Message, state: FSMContext):
    await state.clear()
    is_admin = (message.from_user.id == ADMIN_ID)
    await message.answer("🔙 Повернення у головне меню", reply_markup=main_menu(is_admin=is_admin))

# --- Інші кнопки ---
@dp.message(F.text == "🎲 Група")
async def send_group(message: types.Message):
    await message.answer(f"Приєднуйтесь до нашої групи: {config.GROUP_LINK}")

@dp.message(F.text == "💎 Касир")
async def send_casher(message: types.Message):
    await message.answer(f"Касир: {config.CONTACT_PHONE}")

@dp.message(F.text == "💳 Номер карти")
async def send_card(message: types.Message):
    await message.answer(config.CARD_NUMBER)

@dp.message(F.text == "❓ Як грати")
async def send_help(message: types.Message):
    await message.answer(config.HALP)

@dp.message(F.text == "💥 Демо гра")
async def send_demo(message: types.Message):
    await message.answer(config.DEMO)

@dp.message(F.text == "💲 Вивід")
async def send_output(message: types.Message):
    await message.answer(f"Для виводу напишіть нашому касиру: {config.CONTACT_PHONE}")

@dp.message(F.text == "🎮 Морський бій")
async def send_mb(message: types.Message):
    try:
        await message.answer_photo(types.FSInputFile("images/1.jpg"), caption=config.AK1)
    except Exception:
        await message.answer(config.AK1)

@dp.message(F.text == "🎲 Сейф")
async def send_seif(message: types.Message):
    try:
        await message.answer_photo(types.FSInputFile("images/2.jpg"), caption=config.AK2)
    except Exception:
        await message.answer(config.AK2)

@dp.message(F.text == "🃏 Cash Back")
async def send_cash(message: types.Message):
    try:
        await message.answer_photo(types.FSInputFile("images/3.jpg"), caption=config.AK3)
    except Exception:
        await message.answer(config.AK3)

@dp.message(F.text == "🔹 Акції")
async def send_actions(message: types.Message):
    await message.answer("Оберіть одну з наших акцій:", reply_markup=actions_menu())

# --- Статистика ігор (адмін) ---
@dp.message(F.text == "📊 Статистика ігор")
async def show_game_stats(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return

    stats = await get_all_stats()
    if not stats:
        await message.answer("Поки що статистики немає 📭")
        return

    text = "📊 <b>Загальна статистика по іграх:</b>\n\n"
    for name, total, wins in stats:
        win_rate = (wins / total * 100) if total > 0 else 0
        text += f"🎮 <b>{name}</b>\n🔹 Ігор: {total}\n🔹 Перемог: {wins} ({win_rate:.1f}%)\n\n"

    await message.answer(text)

# ==========================
# Запуск
# ==========================
async def main():
    await init_db()
    logging.info("DB inited")
    logging.info("Бот запущений ✅")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
