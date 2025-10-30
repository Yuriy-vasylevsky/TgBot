


# import logging
# from aiogram import Router, F, types
# from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

# from db import get_user_data, add_or_update_user, has_claimed_gift
# from menu import main_menu

# router = Router()
# logging.basicConfig(level=logging.INFO)


# # ===============================
# #   Команда або кнопка "👤 Мій кабінет"
# # ===============================
# @router.message(F.text == "👤 Мій кабінет")
# async def show_profile(message: types.Message):
#     user_id = message.from_user.id
#     username = message.from_user.username or "—"
#     full_name = message.from_user.full_name or "—"

#     # Оновлюємо дані користувача при кожному вході
#     await add_or_update_user(user_id, username, full_name)

#     user_data = await get_user_data(user_id)

#     if not user_data:
#         await message.answer("⚠️ Ваш профіль ще не створений. Спробуйте пізніше.")
#         return

#     # Отримуємо кількість зіграних ігор (умовно — купонів за тиждень)
#     weekly_coupons = user_data["games_played"]

#     # Створюємо рядок зі смайликами 🎟️, але обмежимо до 20, щоб не було забагато
#     max_emojis = 20
#     if weekly_coupons > max_emojis:
#         coupons_display = "🎟️" * max_emojis + f" +{weekly_coupons - max_emojis}"
#     elif weekly_coupons > 0:
#         coupons_display = "🎟️" * weekly_coupons
#     else:
#         coupons_display = "—"

#     # Формування повідомлення
#     text = (
#         f"👤 <b>Кабінет гравця</b>\n\n"
#         f"🆔 <b>ID:</b> <code>{user_id}</code>\n"
#         f"💬 <b>Ім’я:</b> {user_data['full_name']}\n\n"
#         # f"🏷 <b>Username:</b> @{user_data['username']}\n\n"
#         # f"🎮 <b>Ігор зіграно:</b> {user_data['games_played']}\n"
#         f" <b>Зібрано купонів за тиждень:</b>\n {coupons_display}\n"
#     )

#     keyboard = ReplyKeyboardMarkup(
#         keyboard=[
#             [KeyboardButton(text="🏠 Головне меню")],
#         ],
#         resize_keyboard=True,
#     )

#     await message.answer(text, reply_markup=keyboard, parse_mode="HTML")


# # ===============================
# #   Повернення до головного меню
# # ===============================
# @router.message(F.text == "🏠 Головне меню")
# async def back_to_main_menu(message: types.Message):
#     user_id = message.from_user.id
#     gift_claimed = await has_claimed_gift(user_id)
#     await message.answer(
#         "🏠 Повертаємось до головного меню.",
#         reply_markup=main_menu(user_has_gift=gift_claimed),
#     )
import logging
from aiogram import Router, F, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

from db import (
    get_user_data,
    add_or_update_user,
    has_claimed_gift,
    get_user_task_progress,  # нова функція для тижневих завдань
)
from menu import main_menu

router = Router()
logging.basicConfig(level=logging.INFO)


# ===============================
#   Команда або кнопка "👤 Мій кабінет"
# ===============================
@router.message(F.text == "👤 Мій кабінет")
async def show_profile(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or "—"
    full_name = message.from_user.full_name or "—"

    # Оновлюємо дані користувача при кожному вході
    await add_or_update_user(user_id, username, full_name)

    user_data = await get_user_data(user_id)

    if not user_data:
        await message.answer("⚠️ Ваш профіль ще не створений. Спробуйте пізніше.")
        return

    # Отримуємо кількість зіграних ігор (умовно — купонів за тиждень)
    weekly_coupons = user_data["games_played"]

    # Створюємо рядок зі смайликами 🎟️, максимум 20 для естетики
    max_emojis = 20
    if weekly_coupons > max_emojis:
        coupons_display = "🎟️" * max_emojis + f" +{weekly_coupons - max_emojis}"
    elif weekly_coupons > 0:
        coupons_display = "🎟️" * weekly_coupons
    else:
        coupons_display = "—"

    # Отримуємо тижневі завдання користувача
    tasks = await get_user_task_progress(user_id)
    if tasks:
        tasks_text = "\n".join([
            f"{i+1}. {t['title']} — {'✅' if t['is_completed'] else '❌'}"
            for i, t in enumerate(tasks)
        ])
    else:
        tasks_text = "Немає активних завдань на цей тиждень."

    # Формування повідомлення
    text = (
        f"👤 <b>Кабінет гравця</b>\n\n"
        f"🆔 <b>ID:</b> <code>{user_id}</code>\n"
        f"💬 <b>Ім’я:</b> {user_data['full_name']}\n"
        f"🏷 <b>Username:</b> @{user_data['username']}\n\n"
        f"🎮 <b>Ігор зіграно:</b> {user_data['games_played']}\n"
        f"🎟️ <b>Купонів за тиждень:</b> {coupons_display}\n\n"
        f"📅 <b>Тижневі завдання:</b>\n{tasks_text}"
    )

    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🏠 Головне меню")],
        ],
        resize_keyboard=True,
    )

    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")


# ===============================
#   Повернення до головного меню
# ===============================
@router.message(F.text == "🏠 Головне меню")
async def back_to_main_menu(message: types.Message):
    user_id = message.from_user.id
    gift_claimed = await has_claimed_gift(user_id)
    await message.answer(
        "🏠 Повертаємось до головного меню.",
        reply_markup=main_menu(user_has_gift=gift_claimed),
    )
