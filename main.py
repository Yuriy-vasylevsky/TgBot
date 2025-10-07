import logging
import asyncio
import re
from typing import Any, Callable, Awaitable, Dict
from aiogram import Bot, Dispatcher, F, types, BaseMiddleware
from aiogram.enums import ParseMode
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.client.default import DefaultBotProperties
from aiogram.utils.keyboard import InlineKeyboardBuilder

import config  

from db import (
    init_db, save_user, get_all_users_info,
    add_promocode, list_promocodes, check_promocode,
    set_user_access, add_game_result,
)

from games import register_game_handlers, games_menu as imported_games_menu
from stats import router as stats_router  # ✅ новий модуль статистики
from aiogram import types, F
from config import ADMIN_ID

# ==========================
# Логування
# ==========================
logging.basicConfig(level=logging.INFO)

bot = Bot(
    token=config.TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()
dp.include_router(stats_router)  # ✅ підключаємо новий модуль статистики

ADMIN_ID = config.ADMIN_ID


# ==========================
# Middleware: збереження користувачів
# ==========================
class SaveUserMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[types.TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: types.TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        if isinstance(event, types.Message) and event.from_user:
            try:
                await save_user(event.from_user.id, event.from_user.username, event.from_user.full_name)
            except Exception as e:
                logging.error("Save user error: %s", e)
        return await handler(event, data)


dp.message.middleware(SaveUserMiddleware())


# ==========================
# Меню (основне)
# ==========================
# def main_menu(is_admin=False):
#     keyboard = [
#         ["🎟 Ввести промокод"],
#         ["💫 КОД в посилання"],
#         ["💳 Номер карти"],
#         ["🎲 Група", "💎 Касир"],
#         ["🔹 Акції", "💥 Демо гра"],
#     ]
#     if is_admin:
#         keyboard.append(["⚙️ Адмін панель"])
#     return ReplyKeyboardMarkup(
#         keyboard=[[KeyboardButton(text=b) for b in row] for row in keyboard],
#         resize_keyboard=True
#     )

def main_menu(is_admin=False):
    """
    Головне меню користувача або адміна.
    Адмін не бачить кнопку промокоду, але має доступ до ігор.
    """
    if is_admin:
        keyboard = [
            ["🎮 Ігри"],                    # ✅ тільки для адміна
            ["💳 Номер карти"],
            ["🎲 Група", "💎 Касир"],
            ["🔹 Акції", "💥 Демо гра"],
            ["📊 Статистика", "⚙️ Адмін панель"]
        ]
    else:
        keyboard = [
            ["🎟 Ввести промокод"],          # ✅ лише для користувачів
            ["💫 КОД в посилання"],
            ["💳 Номер карти"],
            ["🎲 Група", "💎 Касир"],
            ["🔹 Акції", "💥 Демо гра"],
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
        ["📊 Статистика"],  # ✅ нова кнопка (в stats.py є “Очистити статистику”)
        ["🔙 Назад до головного меню"]
    ]
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=b) for b in row] for row in keyboard],
        resize_keyboard=True
    )


# ==========================
# FSM (Станові машини)
# ==========================
class Broadcast(StatesGroup):
    waiting_for_text = State()


class PromoFSM(StatesGroup):
    waiting_for_code = State()


class EnterPromoFSM(StatesGroup):
    waiting_for_code = State()


class CodeLinkFSM(StatesGroup):
    waiting_for_code = State()


# ==========================
# /start
# ==========================
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user = message.from_user
    if user:
        await save_user(user.id, user.username, user.full_name)
        is_admin = (user.id == ADMIN_ID)
    else:
        is_admin = False

    try:
        await message.answer_photo(
            photo=types.FSInputFile("images/4444.jpg"),
            caption="🎰 НАЙКРАЩИЙ ІГРОВИЙ ДОСВІД ЧЕКАЄ НА ВАС У ЧЕТВІРКАХ! 🎰",
            reply_markup=main_menu(is_admin=is_admin)
        )
    except Exception:
        await message.answer("🎰 Ласкаво просимо!", reply_markup=main_menu(is_admin=is_admin))


# =============================================================================================
#                     --- Адмін панель ---
# =============================================================================================
@dp.message(F.text == "⚙️ Адмін панель")
async def admin_panel(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer("🔐 Адмін панель", reply_markup=admin_menu())
    else:
        await message.answer("⛔ У вас немає доступу")


# =============================================================================================
#                     --- Список юзерів---
# =============================================================================================

USERS_PER_PAGE = 7


@dp.message(F.text == "👥 Список користувачів")
async def list_users(message: types.Message):
    """Показує список користувачів (нові — на початку)."""
    if message.from_user.id != ADMIN_ID:
        return

    users = await get_all_users_info()
    if not users:
        await message.answer("❌ Користувачів ще немає.")
        return

    # 🔁 Тепер сортуємо за last_active у зворотному порядку (новіші спочатку)
    users.sort(key=lambda x: x[3] or "", reverse=True)

    await send_users_page(message, users, page=1)


async def send_users_page(message_or_query, users, page: int):
    """Формує сторінку зі списком користувачів (зворотне сортування)."""
    total_pages = (len(users) + USERS_PER_PAGE - 1) // USERS_PER_PAGE
    start = (page - 1) * USERS_PER_PAGE
    end = start + USERS_PER_PAGE
    current_users = users[start:end]

    text = f"👥 <b>Користувачі (сторінка {page}/{total_pages}):</b>\n\n"

    for i, (uid, username, full_name, last_active) in enumerate(current_users, start=start + 1):
        text += (
            f"{i}. 👤 <b>{full_name}</b>\n"
            f"   🔗 @{username or '—'}\n"
            # f"   🆔 <code>{uid}</code>\n"
            f"   🕒 {last_active or 'немає даних'}\n\n"
        )

    # Кнопки пагінації — але логіка тепер зворотна
    kb = InlineKeyboardBuilder()
    if page > 1:
        kb.button(text="⬅️ Новіші", callback_data=f"users_page:{page - 1}")
    if end < len(users):
        kb.button(text="➡️ Старіші", callback_data=f"users_page:{page + 1}")
    kb.adjust(2)

    if isinstance(message_or_query, types.CallbackQuery):
        await message_or_query.message.edit_text(text, parse_mode="HTML", reply_markup=kb.as_markup())
        await message_or_query.answer()
    else:
        await message_or_query.answer(text, parse_mode="HTML", reply_markup=kb.as_markup())


@dp.callback_query(F.data.startswith("users_page:"))
async def paginate_users(callback: types.CallbackQuery):
    """Обробляє кнопки пагінації (зворотній порядок)."""
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Лише для адміністратора.", show_alert=True)
        return

    page = int(callback.data.split(":")[1])
    users = await get_all_users_info()
    users.sort(key=lambda x: x[3] or "", reverse=True)

    await send_users_page(callback, users, page)




# =============================================================================================
#                     --- Розсилка ---
# =============================================================================================
@dp.message(F.text == "📢 Розсилка")
async def start_broadcast(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return

    await state.set_state(Broadcast.waiting_for_text)
    cancel_kb = InlineKeyboardBuilder()
    cancel_kb.button(text="❌ Скасувати розсилку", callback_data="cancel_broadcast")

    await message.answer(
        "✍️ Введіть текст розсилки або натисніть «❌ Скасувати розсилку»:",
        reply_markup=cancel_kb.as_markup()
    )


@dp.message(Broadcast.waiting_for_text)
async def process_broadcast_text(message: types.Message, state: FSMContext):
    text = message.text
    confirm_kb = InlineKeyboardBuilder()
    confirm_kb.button(text="✅ Надіслати", callback_data="confirm_broadcast")
    confirm_kb.button(text="❌ Скасувати", callback_data="cancel_broadcast")
    await state.update_data(broadcast_text=text)
    await message.answer(
        f"📨 Текст розсилки:\n\n{text}\n\nНадіслати розсилку?",
        reply_markup=confirm_kb.as_markup()
    )


@dp.callback_query(F.data == "confirm_broadcast")
async def confirm_broadcast(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    text = data.get("broadcast_text")

    import aiosqlite
    conn = await aiosqlite.connect("users.db")
    try:
        async with conn.execute("SELECT id FROM users") as cur:
            rows = await cur.fetchall()
    finally:
        await conn.close()

    count = 0
    for (user_id,) in rows:
        try:
            await callback.bot.send_message(user_id, text)
            count += 1
        except Exception:
            continue

    await callback.message.answer(f"✅ Розсилку надіслано {count} користувачам.")
    await state.clear()
    await callback.answer()


@dp.callback_query(F.data == "cancel_broadcast")
async def cancel_broadcast(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer("❌ Розсилку скасовано.")
    await callback.answer()


# =============================================================================================
#                     --- Промокоди ---
# =============================================================================================
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
    await message.answer(f"✅ Промокод <b>{code}</b> збережено", reply_markup=admin_menu())
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


# --- Промокод користувача ---
@dp.message(F.text == "🎟 Ввести промокод")
async def enter_promocode(message: types.Message, state: FSMContext):
    await state.set_state(EnterPromoFSM.waiting_for_code)
    await message.answer("Введіть ваш промокод:")


@dp.message(EnterPromoFSM.waiting_for_code)
async def check_user_promo(message: types.Message, state: FSMContext):
    code = message.text.strip()
    if await check_promocode(code):
        await set_user_access(message.from_user.id, True)
        await message.answer(
            "✅ Промокод активовано! Доступ до ігор відкритий 🎮",
            reply_markup=imported_games_menu()
        )
    else:
        await message.answer(
            "❌ Невірний або вже використаний промокод",
            reply_markup=main_menu(is_admin=(message.from_user.id == ADMIN_ID))
        )
    await state.clear()


# =============================================================================================
#                     --- Інші кнопки ---
# =============================================================================================
@dp.message(F.text == "🎲 Група")
async def send_group(message: types.Message):
    await message.answer(f"Приєднуйтесь до нашої групи: {config.GROUP_LINK}")


@dp.message(F.text == "💎 Касир")
async def send_casher(message: types.Message):
    await message.answer(f"Касир: {config.CONTACT_PHONE}")


@dp.message(F.text == "💳 Номер карти")
async def send_card(message: types.Message):
    await message.answer(config.CARD_NUMBER)


@dp.message(F.text == "💥 Демо гра")
async def send_demo(message: types.Message):
    await message.answer(config.DEMO)


@dp.message(F.text == "🔹 Акції")
async def send_actions(message: types.Message):
    await message.answer("Оберіть одну з наших акцій:", reply_markup=actions_menu())

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

# ===========================================================================================
# #                               --- КОД в посилання ---
# # ===========================================================================================

@dp.message(F.text == "💫 КОД в посилання")
async def ask_code_for_links(message: types.Message, state: FSMContext):
    await state.set_state(CodeLinkFSM.waiting_for_code)
    await message.answer("Введіть код у форматі: 00-00-00-00-00-00-00")

@dp.message(lambda message: re.fullmatch(r'\d{2}(-\d{2}){6}', message.text or ""))
async def global_code_to_links(message: types.Message):
    code = (message.text or "").replace("-", "")
    await message.answer(f"Чемпіон https://spinplanet.net/?login_code={code}")
    await message.answer(f"Суперматік https://code.greenhost.pw/?c={code}")

# =============================================================================================
#                     --- Повернення в меню ---
# =============================================================================================
@dp.message(F.text == "🔙 Назад до головного меню")
async def back_to_main(message: types.Message, state: FSMContext):
    await state.clear()
    is_admin = (message.from_user.id == ADMIN_ID)
    await message.answer("🔙 Повернення у головне меню", reply_markup=main_menu(is_admin=is_admin))


# ==========================
# 🎮 Меню ігор (для адміна)
# ==========================
@dp.message(F.text == "🎮 Ігри")
async def admin_games_menu(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer("🎮 Меню ігор (адмін доступ):", reply_markup=imported_games_menu())
    else:
        await message.answer("⛔ Ця функція лише для адміністратора.")


# =============================================================================================
#                     --- Запуск ---
# =============================================================================================
async def main():
    await init_db()
    logging.info("✅ DB ініціалізовано")

    await register_game_handlers(dp, bot, main_menu, ADMIN_ID)
    logging.info("✅ Ігри підключено")

    logging.info("🚀 Бот запущений")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

