import logging
from aiogram import Router, F, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from db import (
    get_user_data,
    add_or_update_user,
    has_claimed_gift,
    get_user_task_progress,
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

    await add_or_update_user(user_id, username, full_name)
    user_data = await get_user_data(user_id)
    if not user_data:
        await message.answer("⚠️ Ваш профіль ще не створений. Спробуйте пізніше.")
        return

    games_won = user_data.get("games_won", 0)
    visual = "🏆" * min(games_won, 20)  # максимум 20 елементів щоб не зламало телеграм
    if games_won == 0:
        visual = "—"

    weekly_coupons = user_data["games_played"]
    coupons_display = "🎟️" * min(weekly_coupons, 20)
    if weekly_coupons > 20:
        coupons_display += f" +{weekly_coupons - 20}"
    if not coupons_display:
        coupons_display = "—"

    if weekly_coupons > 0:
        winrate = round((games_won / weekly_coupons) * 100)
    else:
        winrate = 0

    tasks = await get_user_task_progress(user_id)
    if tasks:
        tasks_text = "\n\n".join(
            [
                f"<b>{i+1}. {t['title']}</b>\n"
                f"🎯 <b>Завдання:</b> <i>{t['description'] or 'Без опису'}</i>\n"
                f"🎁 <b>Нагорода:</b> {t['reward'] or '—'}\n"
                f"⏰ <b>Час на виконання:</b> {t['duration'] or 'Не вказано'}"
                for i, t in enumerate(tasks)
            ]
        )
    else:
        tasks_text = "Немає активних завдань на цей тиждень."

    text = (
        f"👤 <b>Кабінет гравця</b>\n\n"
        f"🆔 <b>ID:</b> <code>{user_id}</code>\n"
        f"💬 <b>Ім’я:</b> {user_data['full_name']}\n"
        f"🍀 <b>WinRate:</b> <code>{winrate}%</code>\n\n"
        f"<b>Зібрано PROMO за тиждень: {weekly_coupons}</b>\n {coupons_display}\n\n"
        f"<b>Виграно ігор за тиждень: </b> <code>{games_won}</code>\n"
        f"{visual}\n\n"  # ← ВІЗУАЛІЗАЦІЯ
        f"📅 <b>Тижневі завдання:</b>\n{tasks_text}"
    )

    keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🏠 Головне меню")]],
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
