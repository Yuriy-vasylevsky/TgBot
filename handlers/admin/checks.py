
import re

from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from handlers.config import ADMIN_ID
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

router = Router(name="admin_checks")


class CheckFSM(StatesGroup):
    waiting_for_code = State()


class ClearChecksFSM(StatesGroup):
    confirm = State()


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
            [
                KeyboardButton(text="🏆 Champion 100"),
                KeyboardButton(text="🏆 Champion 200")
            ],
            [
                KeyboardButton(text="🎰 Matic 100"),
                KeyboardButton(text="🎰 Matic 200")
            ],
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


@router.message(F.text.in_(CHECKS.keys()))
async def play_game(message: Message):
    user_id = message.from_user.id
    table, price = CHECKS[message.text]

    balance = await get_balance(user_id)

    if balance < price:
        await message.answer("❌ Недостатньо коштів")
        return

    code = await get_free_check(table)
    if not code:
        await message.answer("❌ Чеків немає")
        return

    await add_to_balance(user_id, -price)
    await remove_check(table, code)
    await log_check_issued(user_id, message.text, code, price)

    user = message.from_user
    name = f"@{user.username}" if user.username else user.full_name or f"#{user.id}"

    await message.bot.send_message(
        ADMIN_ID,
        f"🎁 Видано чек\n\n"
        f"👤 {name}\n"
        f"🏷 Тип: <b>{message.text}</b>\n"
        f"🔑 Код: <code>{code}</code>",
        parse_mode="HTML"
    )

    clean_code = code.replace("-", "")

    if "Champion" in message.text:
        url = f"https://spinplanet.net/?login_code={clean_code}"
    else:
        url = f"https://code.greenhost.pw/?c={clean_code}"

    await message.answer(
        f"🎉 <b>Гарної гри!</b>\n\n"
        f"🔑 Код: <code>{code}</code>\n"
        f"💳 Залишок: {await get_balance(user_id)} грн\n\n"
        f"🔗 {url}",
        parse_mode="HTML",
        disable_web_page_preview=True
    )