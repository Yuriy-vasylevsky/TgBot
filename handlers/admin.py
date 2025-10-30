import aiosqlite
import logging
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import ReplyKeyboardRemove
from db import (
    get_winrate,
    set_winrate,
    get_all_users_info,
    add_promocode,
    list_promocodes,
    check_promocode,
    set_user_access,
    has_claimed_gift,
    add_casino_code,
    ensure_ban_table,
    ban_user,
    unban_user,
    increment_games_played,
)
from menu import admin_menu, main_menu
from games import games_menu as imported_games_menu
from states import WinrateFSM, Broadcast, PromoFSM, EnterPromoFSM, CodeLinkFSM
import config
from aiogram import Router, F, types
from pathlib import Path
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
import re
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    Message,
    CallbackQuery,
)
from aiogram.fsm.state import StatesGroup, State
from aiogram.filters.state import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
)
from typing import Optional
from db import DB_PATH
import random
import string
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from config import ADMIN_ID

import aiosqlite
from menu import main_menu

router = Router()


ADMIN_ID = config.ADMIN_ID
USERS_PER_PAGE = 12

router = Router()


# ==========================
# ⚙️ Адмін панель
# ==========================
@router.message(F.text == "⚙️ Адмін панель")
async def admin_panel(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer("🔐 Адмін панель", reply_markup=admin_menu())
    else:
        await message.answer("⛔ У вас немає доступу")


# ==========================
# 🎯 Winrate
# ==========================
@router.message(F.text == "🎯 Winrate")
async def show_winrate(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    current = await get_winrate()
    user_id = message.from_user.id
    # gift_claimed = await has_claimed_gift(user_id)
    percent = round(current * 100)
    await message.answer(
        f"🎯 Поточний winrate: <b>{percent}%</b>\n\nВведіть новий відсоток виграшу (0–100):",
        reply_markup=ReplyKeyboardRemove(),
        keyboard=main_menu(is_admin=(user_id == ADMIN_ID)),
    )
    await state.set_state(WinrateFSM.waiting_for_value)


@router.message(WinrateFSM.waiting_for_value)
async def set_new_winrate(message: types.Message, state: FSMContext):

    if message.from_user.id != ADMIN_ID:
        return
    try:
        val = int(message.text.strip())
        if not (0 <= val <= 100):
            raise ValueError
        await set_winrate(val / 100)
        user_id = message.from_user.id
        await message.answer(
            f"✅ Новий winrate збережено: {val}%",
            reply_markup=main_menu(is_admin=(user_id == ADMIN_ID)),
        )
    except ValueError:
        await message.answer(
            "❌ Введіть число від 0 до 100.",
            reply_markup=(main_menu(is_admin=(user_id == ADMIN_ID)),),
        )

    await state.clear()


# ==========================
# 👥 Список користувачів
# ==========================


from aiogram import types, F, Router
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime, timezone, timedelta
from config import ADMIN_ID
from db import get_all_users_info


USERS_PER_PAGE = 5


# ===== Сервісна функція для безпечного парсингу дат =====
def parse_dt_safe(dt_str: str):
    try:
        dt = datetime.fromisoformat(dt_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return datetime.min.replace(tzinfo=timezone.utc)


# ===== Форматування часу у вигляді "29.10 о 22:41" =====
def format_time(dt_str: str):
    try:
        dt = datetime.fromisoformat(dt_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        local = dt.astimezone(timezone(timedelta(hours=2)))  # Київ
        return local.strftime("%d.%m о %H:%M")
    except Exception:
        return "немає даних"


# ===== Основна функція для відображення списку =====


async def send_users_page(message_or_query, users, page: int):
    users.sort(key=lambda x: parse_dt_safe(x.get("last_active")), reverse=True)

    total_pages = (len(users) + USERS_PER_PAGE - 1) // USERS_PER_PAGE
    start = (page - 1) * USERS_PER_PAGE
    end = start + USERS_PER_PAGE
    current_users = users[start:end]

    text = f"👥 <b>Користувачі (сторінка {page}/{total_pages}):</b>\n\n"

    for i, user in enumerate(current_users, start=start + 1):
        full_name = user.get("full_name") or "—"
        username = user.get("username") or "—"
        user_id = user.get("user_id")
        last_active = format_time(user.get("last_active") or "")
        last_actions = user.get("last_actions") or "—"

        # 🔹 форматуємо останні дії в стовпчик
        if last_actions and last_actions != "—":
            actions_list = last_actions.split(" | ")
            actions_text = "\n".join([f"   {a.strip()}" for a in actions_list])
            last_actions_str = f"📜 <b>Останні дії:</b>\n{actions_text}"
        else:
            last_actions_str = "📜 Немає даних"

        text += (
            f"{i}. <b>{full_name}</b>\n"
            f"🔗 @{username}\n"
            f"🕒 {last_active}\n"
            f"{last_actions_str}\n"
            f"🔐 <code>{user_id}</code>\n\n"
        )

    kb = InlineKeyboardBuilder()
    if page > 1:
        kb.button(text="⬅️ Назад", callback_data=f"users_page:{page - 1}")
    if end < len(users):
        kb.button(text="➡️ Далі", callback_data=f"users_page:{page + 1}")
    kb.adjust(2)

    # Оновлюємо або надсилаємо повідомлення
    if isinstance(message_or_query, types.CallbackQuery):
        await message_or_query.message.edit_text(
            text, parse_mode="HTML", reply_markup=kb.as_markup()
        )
        await message_or_query.answer()
    else:
        await message_or_query.answer(
            text, parse_mode="HTML", reply_markup=kb.as_markup()
        )


# ===== Команда: список користувачів =====
@router.message(F.text == "👥 Список користувачів")
async def list_users(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    users = await get_all_users_info()
    if not users:
        await message.answer("❌ Користувачів ще немає.")
        return
    await send_users_page(message, users, page=1)


# ===== Кнопки пагінації =====
@router.callback_query(F.data.startswith("users_page:"))
async def paginate_users(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Лише для адміністратора.", show_alert=True)
        return
    page = int(callback.data.split(":")[1])
    users = await get_all_users_info()
    await send_users_page(callback, users, page)

# ========================================================================================================
#                                            📢 Розсилка
# ========================================================================================================
@router.message(F.text == "📢 Розсилка")
async def start_broadcast(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await state.set_state(Broadcast.waiting_for_text)
    cancel_kb = InlineKeyboardBuilder()
    cancel_kb.button(text="❌ Скасувати розсилку", callback_data="cancel_broadcast")
    await message.answer(
        "✍️ Введіть текст розсилки або натисніть «❌ Скасувати розсилку»:",
        reply_markup=cancel_kb.as_markup(),
    )


@router.message(Broadcast.waiting_for_text)
async def process_broadcast_text(message: types.Message, state: FSMContext):
    text = message.text
    confirm_kb = InlineKeyboardBuilder()
    confirm_kb.button(text="✅ Надіслати", callback_data="confirm_broadcast")
    confirm_kb.button(text="❌ Скасувати", callback_data="cancel_broadcast")
    await state.update_data(broadcast_text=text)
    await message.answer(
        f"📨 Текст розсилки:\n\n{text}\n\nНадіслати розсилку?",
        reply_markup=confirm_kb.as_markup(),
    )


@router.callback_query(F.data == "confirm_broadcast")
async def confirm_broadcast(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    text = data.get("broadcast_text")

    async with aiosqlite.connect("users.db") as conn:
        async with conn.execute("SELECT user_id FROM users") as cur:
            rows = await cur.fetchall()

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


@router.callback_query(F.data == "cancel_broadcast")
async def cancel_broadcast(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer("❌ Розсилку скасовано.")
    await callback.answer()


# ______________________________________________________________________________________________________
import asyncio
import aiosqlite
from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import ADMIN_ID
from menu import main_menu


# ---------------- FSM ----------------
class MenuUpdate(StatesGroup):
    waiting_for_text = State()


# ---------------- Команда для адміна ----------------
@router.message(F.text == "🛠 Оновити меню")
async def start_menu_update(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await state.set_state(MenuUpdate.waiting_for_text)

    cancel_kb = InlineKeyboardBuilder()
    cancel_kb.button(text="❌ Скасувати", callback_data="cancel_menu_update")

    await message.answer(
        "✍️ Введіть текст, який буде надіслано всім користувачам разом з новим меню.\n\n"
        "Натисніть «❌ Скасувати», щоб вийти.",
        reply_markup=cancel_kb.as_markup(),
    )


# ---------------- Отримання тексту ----------------
@router.message(MenuUpdate.waiting_for_text)
async def process_menu_update_text(message: types.Message, state: FSMContext):
    text = message.text

    confirm_kb = InlineKeyboardBuilder()
    confirm_kb.button(text="✅ Надіслати", callback_data="confirm_menu_update")
    confirm_kb.button(text="❌ Скасувати", callback_data="cancel_menu_update")

    await state.update_data(update_text=text)
    await message.answer(
        f"📨 <b>Підтвердіть оновлення меню</b>\n\n" f"Текст повідомлення:\n\n{text}",
        parse_mode="HTML",
        reply_markup=confirm_kb.as_markup(),
    )


# ---------------- Підтвердження ----------------
@router.callback_query(F.data == "confirm_menu_update")
async def confirm_menu_update(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    text = data.get("update_text", "")

    await callback.message.edit_text("📤 Починаю оновлення меню...")

    async with aiosqlite.connect("users.db") as conn:
        async with conn.execute("SELECT user_id FROM users") as cur:
            rows = await cur.fetchall()

    total = len(rows)
    success = 0
    failed = 0

    for (user_id,) in rows:
        gift_claimed = await has_claimed_gift(user_id)
        try:
            await callback.bot.send_message(
                user_id,
                text,
                reply_markup=main_menu(
                    is_admin=(user_id == ADMIN_ID), user_has_gift=gift_claimed
                ),
                parse_mode="HTML",
            )
            success += 1
            await asyncio.sleep(0.05)
        except Exception:
            failed += 1
            continue

    await callback.message.answer(
        f"✅ Оновлення меню завершено!\n\n"
        f"📬 Успішно: <b>{success}</b>\n"
        f"⚠️ Помилок: <b>{failed}</b>\n"
        f"👥 Всього користувачів: <b>{total}</b>",
        parse_mode="HTML",
    )

    await state.clear()
    await callback.answer()


# ---------------- Скасування ----------------
@router.callback_query(F.data == "cancel_menu_update")
async def cancel_menu_update(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Оновлення меню скасовано.")
    await callback.answer()


# ___________________________________________________________________________________________________________________


# ---------------- FSM ----------------
# class PromoFSM(StatesGroup):
#     waiting_for_count = State()
class PromoFSM(StatesGroup):
    waiting_for_code = State()  # для ручного вводу промокоду
    waiting_for_count = State()


# ==========================
# 🎟 Промокоди
# ==========================
@router.message(F.text == "➕ Створити промокод")
async def create_promocode(message: types.Message, state: FSMContext):

    if message.from_user.id != ADMIN_ID:
        return
    await state.set_state(PromoFSM.waiting_for_code)
    await message.answer(
        "🆕 Введіть новий промокод:", reply_markup=ReplyKeyboardRemove()
    )


@router.message(PromoFSM.waiting_for_code)
async def save_promocode_handler(message: types.Message, state: FSMContext):

    if message.from_user.id != ADMIN_ID:
        return
    code = message.text.strip()
    # user_id = message.from_user.id
    await add_promocode(code)
    await message.answer(
        f"✅ Промокод <b>{code}</b> збережено",
        reply_markup=admin_menu(),
    )
    await state.clear()


# __________________________________________________________________________________________________________


# ---------------- Автоматична генерація ----------------
@router.message(F.text == "🤞 Згенерувати промо")
async def ask_promo_count(message: types.Message, state: FSMContext):
    """Запитує кількість промокодів"""
    if message.from_user.id != ADMIN_ID:
        return

    await state.set_state(PromoFSM.waiting_for_count)

    # Клавіатура з вибором кількості
    num_kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=str(i)) for i in range(1, 6)],
            [
                KeyboardButton(text="10"),
                # KeyboardButton(text="20"),
                # KeyboardButton(text="50"),
            ],
            # [KeyboardButton(text="100")],
        ],
        resize_keyboard=True,
    )

    # Inline кнопка відміни
    cancel_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="❌ Відмінити", callback_data="cancel_promo_gen"
                )
            ]
        ]
    )

    await message.answer(
        "🔢 Введіть або виберіть кількість промокодів для генерації:",
        reply_markup=num_kb,
    )
    await message.answer(
        "👇 Якщо передумали, натисніть нижче:",
        reply_markup=cancel_kb,
    )


# ---------------- Обробка введеної кількості ----------------
@router.message(PromoFSM.waiting_for_count)
async def generate_promocodes(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    try:
        count = int(message.text)
        if count <= 0 or count > 100:
            raise ValueError
    except ValueError:
        await message.answer("⚠️ Введіть число від 1 до 100 або натисніть кнопку.")
        return

    generated = []
    for _ in range(count):
        code = "PROMO-" + "".join(
            random.choices(string.ascii_uppercase + string.digits, k=6)
        )
        await add_promocode(code)
        generated.append(code)

    text = "\n".join(generated)
    await message.answer(
        f"✅ Згенеровано {count} промокодів:\n\n<code>{text}</code>",
        parse_mode="HTML",
        reply_markup=main_menu(is_admin=user_id == ADMIN_ID),
    )
    await state.clear()


# ---------------- Відміна через inline кнопку ----------------
@router.callback_query(F.data == "cancel_promo_gen")
async def cancel_promo_gen(callback: types.CallbackQuery, state: FSMContext):
    """Обробка натискання кнопки 'Відмінити'"""
    await state.clear()
    await callback.message.edit_text(
        "❌ Створення промокодів скасовано.",
    )
    await callback.message.answer(
        "🔙 Повертаємось у головне меню.",
        reply_markup=main_menu(is_admin=callback.from_user.id == ADMIN_ID),
    )
    await callback.answer()  # закриває “годинник” Telegram


# ---------------- Допоміжна функція ----------------
async def add_promocode(code: str):
    """Додає промокод у базу."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO promocodes (code, active) VALUES (?, 1)", (code,)
        )
        await db.commit()


# ___________________________________________________________________________________________________________


@router.message(F.text == "🎟 Активні промокоди")
async def show_promocodes(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    codes = await list_promocodes()
    if not codes:
        await message.answer("❌ Немає активних промокодів")
        return

    formatted_codes = "\n".join([f"🎟️ <code>{code}</code>" for code in codes])
    builder = InlineKeyboardBuilder()
    builder.button(text="📋 Скопіювати всі", callback_data="copy_codes")
    builder.button(text="🗑 Очистити всі", callback_data="confirm_clear_codes")
    builder.adjust(1)
    await message.answer(
        f"🎟 <b>Активні промокоди:</b>\n\n{formatted_codes}",
        reply_markup=builder.as_markup(),
    )


@router.callback_query(F.data == "copy_codes")
async def copy_codes_callback(callback: types.CallbackQuery):
    codes = await list_promocodes()
    if not codes:
        await callback.message.answer("❌ Немає активних промокодів")
        await callback.answer()
        return
    codes_text = "\n".join(codes)
    await callback.message.answer(
        f"📋 <b>Скопіюйте промокоди нижче:</b>\n\n<code>{codes_text}</code>"
    )
    await callback.answer("✅ Готово — коди можна скопіювати!")


@router.callback_query(F.data == "confirm_clear_codes")
async def confirm_clear_codes(callback: types.CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Так, видалити", callback_data="clear_codes")
    builder.button(text="❌ Скасувати", callback_data="cancel_clear")
    builder.adjust(2)
    await callback.message.answer(
        "⚠️ Ви впевнені, що хочете <b>видалити всі промокоди</b>?",
        reply_markup=builder.as_markup(),
    )
    await callback.answer()


@router.callback_query(F.data == "clear_codes")
async def clear_codes(callback: types.CallbackQuery):
    await clear_all_promocodes()
    await callback.message.answer("✅ Усі промокоди успішно видалено.")
    await callback.answer("Видалено ✅")


@router.callback_query(F.data == "cancel_clear")
async def cancel_clear(callback: types.CallbackQuery):
    await callback.message.answer("Операцію скасовано.")
    await callback.answer("❌ Скасовано")


# ==========================
# Очистка промокодів
# ==========================
async def clear_all_promocodes():
    async with aiosqlite.connect("users.db") as db:
        await db.execute("DELETE FROM promocodes")
        await db.commit()


# ==========================
# Введення промокоду користувачем
# ==========================
@router.message(F.text == "🎟 Ввести промокод")
async def enter_promocode(message: types.Message, state: FSMContext):
    await state.set_state(EnterPromoFSM.waiting_for_code)
    await message.answer("🔑 Введіть ваш промокод:", reply_markup=ReplyKeyboardRemove())
    # await increment_games_played(message.from_user.id)


@router.message(EnterPromoFSM.waiting_for_code)
async def check_user_promo(message: types.Message, state: FSMContext):
    code = message.text.strip()
    user_id = message.from_user.id

    # Перевіряємо, чи користувач вже отримав подарунок
    gift_claimed = await has_claimed_gift(user_id)

    if await check_promocode(code):
        await set_user_access(user_id, True)
        text = (
            "✅ <b>Промокод активовано!</b>\n\n"
            "🎮 Виберіть гру, щоб перевірити свою удачу!\n\n"
            "🎁 Виграні купони можна поставити в казино 🎰"
        )
        await increment_games_played(message.from_user.id)
        await message.answer(text, reply_markup=imported_games_menu())
    else:
        # Передаємо актуальний стан подарунка у меню
        await message.answer(
            "❌ Невірний або вже використаний промокод.",
            reply_markup=main_menu(
                is_admin=(user_id == ADMIN_ID), user_has_gift=gift_claimed
            ),
        )

    # Очищаємо стан FSM
    await state.clear()


# ======================
# СТАНИ
# ======================
class AddCodeFSM(StatesGroup):
    waiting_for_code = State()


# class CodeLinkFSM(StatesGroup):
#     waiting_for_code = State()


# FSM для додавання коду
class AddCodeFSM(StatesGroup):
    waiting_for_type = State()
    waiting_for_code = State()


# ======================
# ДОДАВАННЯ КОДУ (для адміна)
# ======================
@router.message(F.text == "➕ Додати код")
async def ask_code_type(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ Тільки адміністратор.")
        return

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🏆 Champion", callback_data="add_code_type:champion"
                ),
                InlineKeyboardButton(
                    text="🎰 Superomatic", callback_data="add_code_type:superomatic"
                ),
            ]
        ]
    )
    await message.answer("Виберіть тип коду для додавання:", reply_markup=kb)


@router.callback_query(F.data.startswith("add_code_type:"))
async def on_choose_add_type(cb: CallbackQuery, state: FSMContext):
    _, code_type = cb.data.split(":")
    await state.update_data(casino_type=code_type)
    await state.set_state(AddCodeFSM.waiting_for_code)
    await cb.message.answer(f"Введіть новий код для {code_type}:")
    await cb.answer()


@router.message(AddCodeFSM.waiting_for_code)
async def add_code_receive(message: Message, state: FSMContext):
    data = await state.get_data()
    casino_type = data.get("casino_type")
    code = message.text.strip()

    if not re.fullmatch(r"(\d{2}-){6}\d{2}", code):
        await message.answer("❌ Невірний формат! Приклад: 11-36-36-50-20-11-33")
        return

    await add_casino_code(code, casino_type)

    await message.answer(
        f"✅ Код <code>{code}</code> додано до {casino_type}.", parse_mode="HTML"
    )
    await state.clear()


class AddCodeFSM(StatesGroup):
    waiting_for_code = State()


# ++++++++++++++++++                  код в посилання            +++++++++++++++++++++++++++++++++


@router.message(F.text.regexp(r"^\d{2}(?:-\d{2}){6}$"))
async def auto_generate_links(message: Message, state: FSMContext):
    current_state = await state.get_state()

    # якщо бот зараз очікує код від адміна — пропускаємо
    if current_state == AddCodeFSM.waiting_for_code.state:
        return

    code = message.text.strip().replace("-", "")
    await message.answer(f"🏆 Champion:\nhttps://spinplanet.net/?login_code={code}")
    await message.answer(f"🎰 Superomatic:\nhttps://code.greenhost.pw/?c={code}")


# ________________________________________________БАН________________________________________________________________


async def is_banned(user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT 1 FROM banned_users WHERE user_id=?", (user_id,)
        ) as cur:
            row = await cur.fetchone()
            return bool(row)


async def list_banned() -> list[tuple]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            """
            SELECT b.user_id, u.full_name, b.reason, b.banned_by, b.ts
            FROM banned_users b
            LEFT JOIN users u ON u.user_id = b.user_id
            ORDER BY b.ts DESC
            """
        ) as cur:
            return await cur.fetchall()


# -----------------------
# FSM
# -----------------------
class BanStates(StatesGroup):
    waiting_for_ban_id = State()
    waiting_for_unban_id = State()
    waiting_for_ban_reason = State()


# -----------------------
# Адмінські хендлери (Router)
# -----------------------


# Кнопка: почати бан (адмін натискає)
@router.message(F.text == "🚫 Забанити")
async def cmd_start_ban(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ Тільки адміністратор.")
        return
    await message.answer("Введи ID користувача для бану:")
    await state.set_state(BanStates.waiting_for_ban_id)


@router.message(BanStates.waiting_for_ban_id)
async def handle_ban_id(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Введи тільки числовий ID.")
        return
    uid = int(message.text)
    if uid == ADMIN_ID:
        await message.answer("⛔ Нельзя банити себе.")
        await state.clear()
        return
    await state.update_data(ban_target=uid)
    await message.answer("Введи причину бану (можеш залишити порожньою):")
    await state.set_state(BanStates.waiting_for_ban_reason)


@router.message(BanStates.waiting_for_ban_reason)
async def handle_ban_reason(message: types.Message, state: FSMContext):
    data = await state.get_data()
    uid = data.get("ban_target")
    reason = message.text.strip() or None
    await ban_user(uid, banned_by=message.from_user.id, reason=reason)
    await state.clear()
    await message.answer(
        f"✅ Користувач <code>{uid}</code> заблокований.\nПричина: {reason or '—'}",
        parse_mode="HTML",
    )


@router.message(BanStates.waiting_for_ban_reason)
async def handle_ban_reason(message: types.Message, state: FSMContext):
    data = await state.get_data()
    uid = data.get("ban_target")
    reason = message.text.strip() or None
    await ban_user(uid, banned_by=message.from_user.id, reason=reason)
    await state.clear()
    await message.answer(
        f"✅ Користувач <code>{uid}</code> заблокований.\nПричина: {reason or '—'}",
        parse_mode="HTML",
        reply_markup=admin_menu(),
    )


# -----------------------
# Розбан
# -----------------------
@router.message(F.text == "🔓 Розбанити")
async def cmd_start_unban(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ Тільки адміністратор.")
        return
    await message.answer("Введи ID користувача для розбану (тільки цифри):")
    await state.set_state(BanStates.waiting_for_unban_id)


@router.message(BanStates.waiting_for_unban_id)
async def handle_unban_id(message: types.Message, state: FSMContext):
    text = message.text.strip()
    if not text.isdigit():
        await message.answer("Невірний формат. Введи тільки числовий ID або /cancel.")
        return
    uid = int(text)
    await unban_user(uid)
    await state.clear()
    await message.answer(
        f"✅ Користувач <code>{uid}</code> розблокований.",
        parse_mode="HTML",
        reply_markup=admin_menu(),
    )


# -----------------------
# Список банів
# -----------------------


@router.message(F.text == "📋 Список банів")
async def view_banned_list(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ Тільки адміністратор.")
        return

    rows = await list_banned()
    if not rows:
        await message.answer(
            "📭 Список банів пустий.", reply_markup=main_menu(is_admin=True)
        )
        return

    lines = []
    for uid, full_name, reason, banned_by, ts in rows:
        name = full_name or "—"
        by = str(banned_by) if banned_by else "—"
        r = reason if reason else "—"
        lines.append(
            f"👤 <b>{name}</b>\n 🔮ID: <code>{uid}</code>\n 📄Причина: {r}\n🕒 {ts}\n"
        )

    text = "📋 <b>Заблоковані користувачі:</b>\n\n" + "\n".join(lines)
    await message.answer(text, parse_mode="HTML", reply_markup=admin_menu())


# 🔒 by: {by}
# -----------------------
# Cancel / back
# -----------------------
@router.message(F.text.in_({"/cancel", "❌ Відмінити", "скасувати"}))
async def cancel_state(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "❌ Дія скасована.",
        reply_markup=main_menu(is_admin=(message.from_user.id == ADMIN_ID)),
    )


# _______________________________ Оновлення карт ______________________________

from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from db import get_cards, update_card
from aiogram import Router, types, F
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove

# router = Router()


class CardFSM(StatesGroup):
    waiting_for_bank = State()
    waiting_for_number = State()


@router.message(F.text == "💳 Керування картами")
async def manage_cards(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return

    cards = await get_cards()
    text = "🏦 Поточні картки:\n\n" + "\n".join(
        [f"{bank}: <code>{num}</code>" for bank, num in cards]
    )

    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Приват"), KeyboardButton(text="Ощад")],
            [KeyboardButton(text="❌ Відмінити")],
        ],
        resize_keyboard=True,
    )

    await message.answer(
        f"{text}\n\n🔧 Виберіть банк для редагування:", reply_markup=kb
    )
    await state.set_state(CardFSM.waiting_for_bank)


@router.message(CardFSM.waiting_for_bank)
async def ask_new_card(message: types.Message, state: FSMContext):
    bank = message.text
    if bank == "❌ Відмінити":
        await state.clear()
        await message.answer("❌ Скасовано.", reply_markup=admin_menu())
        return

    await state.update_data(bank_name=bank)
    await message.answer(
        f"💳 Введіть новий номер картки для {bank}:", reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(CardFSM.waiting_for_number)


@router.message(CardFSM.waiting_for_number)
async def save_new_card(message: types.Message, state: FSMContext):
    data = await state.get_data()
    bank_name = data.get("bank_name")
    new_number = message.text.strip()

    await update_card(bank_name, new_number)
    await message.answer(
        f"✅ Картку для {bank_name} оновлено на:\n<code>{new_number}</code>",
        parse_mode="HTML",
        reply_markup=admin_menu(),
    )
    await state.clear()


from aiogram import Router, F, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import ADMIN_ID
from db import reset_all_game_stats

# router = Router()


@router.message(F.text == "🧹 Очистити статистику ігор")
async def confirm_clear_stats(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ Ця команда доступна лише адміну.")
        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Так, очистити", callback_data="admin:confirm_clear_stats"
                ),
                InlineKeyboardButton(text="❌ Ні", callback_data="admin:cancel_clear"),
            ]
        ]
    )
    await message.answer(
        "⚠️ Ви впевнені, що хочете обнулити статистику всіх користувачів?",
        reply_markup=keyboard,
    )


@router.callback_query(F.data == "admin:confirm_clear_stats")
async def clear_stats(cb: types.CallbackQuery):
    if cb.from_user.id != ADMIN_ID:
        await cb.answer("⛔ Тільки адміністратор може це зробити.")
        return

    await cb.answer()
    await reset_all_game_stats()
    await cb.message.edit_text("✅ Статистика всіх гравців успішно обнулена!")


@router.callback_query(F.data == "admin:cancel_clear")
async def cancel_clear(cb: types.CallbackQuery):
    await cb.answer("❌ Скасовано.")
    await cb.message.edit_text("Очищення статистики скасовано.")


# _________________________ скачати бд ________________________________________________

from aiogram import Router, F, types
from aiogram.types import FSInputFile
from config import ADMIN_ID
from pathlib import Path


@router.message(F.text == "📦 Скачати БД")
async def download_db(message: types.Message):
    """Відправляє адміну файл бази даних users.db"""
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ Ця команда доступна лише адміну.")
        return

    db_path = Path(__file__).resolve().parent.parent / "users.db"

    if not db_path.exists():
        await message.answer("⚠️ Файл бази даних не знайдено.")
        return

    await message.answer("⏳ Готую базу даних до відправки...")
    await message.answer_document(
        FSInputFile(db_path), caption="📦 База даних користувачів"
    )
