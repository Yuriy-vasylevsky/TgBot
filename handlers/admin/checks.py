import re

from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from handlers.config import ADMIN_ID
from handlers.profile import notify_reward_progress
from db.check import add_check_code, get_checks_stats, clear_all_checks
from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from db import get_balance, add_to_balance, log_check_issued
from db.check import get_checks_count, get_free_check, remove_check, get_checks_total_balance
from handlers.menu import checks_menu
from handlers.casino_api import create_invoice

router = Router(name="admin_checks")


class CheckFSM(StatesGroup):
    waiting_for_code = State()
    waiting_for_custom_amount = State()   # ← Для динамічної суми Champion


CHECK_TABLES = {
    "🏆 Чек 100 Champion": "champion_checks_100",
    "🏆 Чек 200 Champion": "champion_checks_200",
    "🎰 Чек 100 Matic": "matic_checks_100",
    "🎰 Чек 200 Matic": "matic_checks_200",
}

CHECKS = {
    "🏆 Champion 100": ("champion_checks_100", 100),
    "🏆 Champion 200": ("champion_checks_200", 200),
    "🎰 Matic 100": ("matic_checks_100", 100),
    "🎰 Matic 200": ("matic_checks_200", 200),
}


# ==================== АДМІН ПАНЕЛЬ ====================

@router.message(CheckFSM.waiting_for_code, F.text == "❌ Скасувати")
async def cancel_add_code(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await state.clear()
    await message.answer("❌ Додавання чека скасовано", reply_markup=checks_menu())


@router.message(F.text == "💳 Чеки")
async def open_checks(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    stats = await get_checks_stats()
    total_balance = await get_checks_total_balance()

    text = "💳 <b>Меню чеків</b>\n\n📊 <b>Наявні чеки:</b>\n\n"

    for name, count in stats.items():
        text += f"{name}: <b>{count}</b>\n"

    text += f"\n💰 <b>Баланс чеків:</b> {total_balance} грн"

    await message.answer(text, parse_mode="HTML", reply_markup=checks_menu())


@router.message(F.text.in_(CHECK_TABLES.keys()))
async def choose_type(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return

    await state.update_data(table=CHECK_TABLES[message.text])
    await state.set_state(CheckFSM.waiting_for_code)

    cancel_kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Скасувати")]],
        resize_keyboard=True
    )

    await message.answer(
        "📩 Відправ код у форматі: 00-00-00-00-00-00-00\n",
        reply_markup=cancel_kb
    )


@router.message(CheckFSM.waiting_for_code)
async def save_code(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return

    code = message.text.strip()

    if not re.fullmatch(r"(\d{2}-){6}\d{2}", code):
        await message.answer("❌ Невірний формат коду")
        return

    data = await state.get_data()
    table = data["table"]

    await add_check_code(table, code)

    cancel_kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Скасувати")]],
        resize_keyboard=True
    )

    await message.answer(
        f"✅ Код додано:\n<code>{code}</code>\n\n"
        f"📩 Надішли наступний код:",
        parse_mode="HTML",
        reply_markup=cancel_kb
    )


# ==================== ГРА ДЛЯ КОРИСТУВАЧІВ ====================

@router.message(F.text == "🎮 Грати")
async def play_menu(message: Message):
    user_id = message.from_user.id
    balance = await get_balance(user_id)
    checks = await get_checks_count()

    text = (
        f"💰 Баланс: <b>{balance} грн</b>\n\n"
        f"📦 Доступні чеки:\n\n"
        f"🏆 100 Champion: {checks['champion_100']}\n"
        f"🏆 200 Champion: {checks['champion_200']}\n"
        f"🎰 100 Matic: {checks['matic_100']}\n"
        f"🎰 200 Matic: {checks['matic_200']}\n\n"
        f"👇 Обери гру 👇"
    )

    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🏆 Champion"), KeyboardButton(text="🏆 Champion 100")],
            [KeyboardButton(text="🏆 Champion 200"), KeyboardButton(text="🎰 Matic 100")],
            [KeyboardButton(text="🎰 Matic 200"), KeyboardButton(text="🎰 Джекпот")],
            [KeyboardButton(text="🔙 Назад до головного меню")]
        ],
        resize_keyboard=True
    )

    inline_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="💰 Поповнити", callback_data="wallet_topup"),
                InlineKeyboardButton(text="👨‍💼 Касир", url="https://t.me/KaSSa_4444")
            ]
        ]
    )

    await message.answer(text, parse_mode="HTML", reply_markup=inline_kb)
    await message.answer(
        "💰 Вивід через касира в робочий час з 9:00 до 00:00",
        reply_markup=kb
    )


# === ДИНАМІЧНИЙ CHAMPION ===
@router.message(F.text == "🏆 Champion")
async def choose_champion_amount(message: Message, state: FSMContext):
    await state.set_state(CheckFSM.waiting_for_custom_amount)
    
    cancel_kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Скасувати")]],
        resize_keyboard=True
    )
    
    await message.answer(
        "🏆 Введіть суму для Champion (від 50 грн):",
        reply_markup=cancel_kb
    )


@router.message(CheckFSM.waiting_for_custom_amount)
async def process_custom_amount(message: Message, state: FSMContext):
    if message.text == "❌ Скасувати":
        await state.clear()
        await message.answer("❌ Скасовано")
        return

    try:
        amount = int(message.text)
        if amount < 50:
            await message.answer("❌ Мінімальна сума — 50 грн")
            return
    except:
        await message.answer("❌ Введіть тільки число")
        return

    user_id = message.from_user.id

    invoice_data = await create_invoice(amount)
    
    if not invoice_data or not invoice_data.get("success"):
        await message.answer("❌ Помилка створення чека в казино. Спробуйте пізніше.")
        await state.clear()
        return

    invoice_code = invoice_data["invoice"]
    game_url = invoice_data["url"]

    await add_to_balance(user_id, -amount)
    await log_check_issued(user_id, f"🏆 Champion {amount}", invoice_code, amount)
    await notify_reward_progress(
        message.bot, user_id,
        message.from_user.username,
        message.from_user.full_name or ""
    )

    name = f"@{message.from_user.username}" if message.from_user.username else message.from_user.full_name or f"#{user_id}"
    await message.bot.send_message(
        ADMIN_ID,
        f"🎁 Видано чек (API)\n\n"
        f"👤 {name}\n"
        f"🏷 Тип: <b>Champion {amount} грн</b>\n"
        f"🔑 Код: <code>{invoice_code}</code>",
        parse_mode="HTML"
    )

    await message.answer(
        f"🎉 <b>Гарної гри!</b>\n\n"
        f"🔑 Код: <code>{invoice_code}</code>\n"
        f"💳 Залишок: {await get_balance(user_id)} грн\n\n"
        f"🔗 {game_url}",
        parse_mode="HTML",
        disable_web_page_preview=True
    )

    await state.clear()


# === СТАРА ЛОГІКА ДЛЯ ФІКСОВАНИХ ЧЕКІВ ===
@router.message(F.text.in_(CHECKS.keys()))
async def play_game(message: Message):
    user_id = message.from_user.id
    check_name = message.text
    _, price = CHECKS[check_name]

    balance = await get_balance(user_id)
    if balance < price:
        await message.answer("❌ Недостатньо коштів")
        return

    invoice_data = await create_invoice(price)

    if invoice_data and invoice_data.get("success"):
        invoice_code = invoice_data["invoice"]
        game_url = invoice_data["url"]

        await add_to_balance(user_id, -price)
        await log_check_issued(user_id, check_name, invoice_code, price)
        await notify_reward_progress(
            message.bot, user_id,
            message.from_user.username,
            message.from_user.full_name or ""
        )

        name = f"@{message.from_user.username}" if message.from_user.username else message.from_user.full_name or f"#{user_id}"
        await message.bot.send_message(
            ADMIN_ID,
            f"🎁 Видано чек (API)\n\n"
            f"👤 {name}\n"
            f"🏷 Тип: <b>{check_name}</b>\n"
            f"🔑 Код: <code>{invoice_code}</code>",
            parse_mode="HTML"
        )

        await message.answer(
            f"🎉 <b>Гарної гри!</b>\n\n"
            f"🔑 Код: <code>{invoice_code}</code>\n"
            f"💳 Залишок: {await get_balance(user_id)} грн\n\n"
            f"🔗 {game_url}",
            parse_mode="HTML",
            disable_web_page_preview=True
        )
    else:
        await message.answer("❌ Помилка створення чека. Спробуйте пізніше.")


# ==================== АДМІН СТАТИСТИКА ====================

@router.message(F.text == "📊 Чеки")
async def checks_stats(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    stats = await get_checks_stats()
    total_balance = await get_checks_total_balance()

    text = "💳 <b>Статистика чеків</b>\n\n"

    for name, count in stats.items():
        text += f"{name}: <b>{count}</b>\n"

    text += f"\n💰 <b>Баланс чеків:</b> {total_balance} грн"

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🧹 Очистити всі чеки", callback_data="clear_checks_ask")]
        ]
    )

    await message.answer(text, parse_mode="HTML", reply_markup=kb)


# ... (весь інший код з callback'ами clear_checks залишити без змін)
@router.callback_query(F.data == "clear_checks_ask")
async def ask_clear(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Тільки для адміна", show_alert=True)
        return

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Так, видалити", callback_data="clear_checks_confirm"),
                InlineKeyboardButton(text="❌ Скасувати", callback_data="clear_checks_cancel"),
            ]
        ]
    )

    await callback.message.edit_text(
        "⚠️ Точно видалити ВСІ чеки?\nЦю дію НЕ можна скасувати!",
        reply_markup=kb
    )
    await callback.answer()


@router.callback_query(F.data == "clear_checks_confirm")
async def confirm_clear(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Тільки для адміна", show_alert=True)
        return

    await clear_all_checks()
    await callback.message.edit_text("🧹 Всі чеки видалено!")
    await callback.answer("Готово!", show_alert=True)


@router.callback_query(F.data == "clear_checks_cancel")
async def cancel_clear(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Тільки для адміна", show_alert=True)
        return

    await callback.message.edit_text("❌ Скасовано")
    await callback.answer()


from aiogram import Router, F, types
from aiogram.types import FSInputFile
from handlers.config import ADMIN_ID
from pathlib import Path


@router.message(F.text == "📦 Скачати БД")
async def download_db(message: types.Message):
    """Відправляє адміну файл бази даних users.db"""
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ Ця команда доступна лише адміну.")
        return

    # Шукаємо базу і в /data (Railway volume), і поруч з кодом (запасний варіант)
    possible_paths = [
        Path("/data/users.db"),
        Path(__file__).resolve().parent.parent / "users.db",
    ]

    db_path = next((p for p in possible_paths if p.exists()), None)

    if db_path is None:
        await message.answer(
            "⚠️ Файл бази даних не знайдено. Перевірені шляхи:\n"
            + "\n".join(str(p) for p in possible_paths)
        )
        return

    await message.answer("⏳ Готую базу даних до відправки...")
    await message.answer_document(
        FSInputFile(db_path), caption=f"📦 База даних користувачів\n📍 {db_path}"
    )