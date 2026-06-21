from aiogram import Router, F
from aiogram.types import (
    Message,
    CallbackQuery,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from handlers.config import ADMIN_ID
from handlers.profile import notify_reward_progress
from db import get_balance, add_to_balance, log_check_issued, get_issued_checks_for_user
from handlers.casino_api import create_invoice, close_invoice, check_invoice, add_to_invoice

router = Router(name="admin_checks")


class CheckFSM(StatesGroup):
    waiting_for_custom_amount = State()   # ← Для динамічної суми Champion


class AddToCheckFSM(StatesGroup):
    waiting_for_amount = State()


# Champion — завжди через API (динамічна видача)
CHAMPION_PRESET_AMOUNTS = [100, 200, 250]


# ==================== ГРА ДЛЯ КОРИСТУВАЧІВ ====================

@router.message(F.text == "🎮 Грати")
async def play_menu(message: Message):
    user_id = message.from_user.id
    balance = await get_balance(user_id)

    text = (
        f"💰 Баланс: <b>{balance} грн</b>\n\n"
        f"👇 Обери гру 👇"
    )

    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🏆 Champion")],
            [KeyboardButton(text="🎰 Matic")],
            [KeyboardButton(text="🔒 Закрити чек")],
            [KeyboardButton(text="💵 Поповнити чек")],
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


def champion_amount_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=f"{amount} грн", callback_data=f"champ_amt_{amount}")
                for amount in CHAMPION_PRESET_AMOUNTS
            ],
            [InlineKeyboardButton(text="✏️ Інша сума", callback_data="champ_amt_custom")],
            [InlineKeyboardButton(text="❌ Скасувати", callback_data="champ_cancel")]
        ]
    )


@router.message(F.text == "🏆 Champion")
async def champion_menu(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("🏆 Обери суму Champion:", reply_markup=champion_amount_kb())


# === ВИДАЧА ЧЕКА CHAMPION (через API) ===

async def issue_champion_check(target_message: Message, user, amount: int):
    user_id = user.id

    invoice_data = await create_invoice(amount)

    if not invoice_data or not invoice_data.get("success"):
        await target_message.answer("❌ Помилка створення чека в казино. Спробуйте пізніше.")
        return

    invoice_code = invoice_data["invoice"]
    game_url = invoice_data["url"]

    await add_to_balance(user_id, -amount)
    await log_check_issued(user_id, f"🏆 Champion {amount}", invoice_code, amount)
    await notify_reward_progress(
        target_message.bot, user_id,
        user.username,
        user.full_name or ""
    )

    name = f"@{user.username}" if user.username else user.full_name or f"#{user_id}"
    await target_message.bot.send_message(
        ADMIN_ID,
        f"🎁 Видано чек (API)\n\n"
        f"👤 {name}\n"
        f"🏷 Тип: <b>Champion {amount} грн</b>\n"
        f"🔑 Код: <code>{invoice_code}</code>",
        parse_mode="HTML"
    )

    await target_message.answer(
        f"🎉 <b>Гарної гри!</b>\n\n"
        f"🔑 Код: <code>{invoice_code}</code>\n"
        f"💳 Залишок: {await get_balance(user_id)} грн\n\n"
        f"🔗 {game_url}",
        parse_mode="HTML",
        disable_web_page_preview=True
    )


@router.callback_query(F.data.startswith("champ_amt_"))
async def champion_pick_amount(callback: CallbackQuery, state: FSMContext):
    value = callback.data.removeprefix("champ_amt_")

    if value == "custom":
        await state.set_state(CheckFSM.waiting_for_custom_amount)
        cancel_kb = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="❌ Скасувати", callback_data="champ_cancel")]]
        )
        await callback.message.edit_text(
            "🏆 Введіть суму для Champion (від 50 грн):",
            reply_markup=cancel_kb
        )
        await callback.answer()
        return

    amount = int(value)
    balance = await get_balance(callback.from_user.id)
    if balance < amount:
        await callback.answer("❌ Недостатньо коштів", show_alert=True)
        return

    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer()
    await issue_champion_check(callback.message, callback.from_user, amount)


@router.message(CheckFSM.waiting_for_custom_amount)
async def process_custom_amount(message: Message, state: FSMContext):
    try:
        amount = int(message.text)
        if amount < 50:
            await message.answer("❌ Мінімальна сума — 50 грн")
            return
    except (TypeError, ValueError):
        await message.answer("❌ Введіть тільки число")
        return

    balance = await get_balance(message.from_user.id)
    if balance < amount:
        await message.answer("❌ Недостатньо коштів")
        return

    await state.clear()
    await issue_champion_check(message, message.from_user, amount)


@router.callback_query(F.data == "champ_cancel")
async def champion_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Скасовано")
    await callback.answer()


# ==================== ЗАКРИТТЯ ЧЕКА CHAMPION ДЛЯ ГРАВЦІВ ====================

@router.message(F.text == "🔒 Закрити чек")
async def show_my_checks(message: Message):
    """Показує ТІЛЬКИ активні чеки Champion з балансом > 0"""
    user_id = message.from_user.id
    checks = await get_issued_checks_for_user(user_id)

    champion_checks = [ch for ch in checks if "Champion" in ch.get("check_type", "")]

    if not champion_checks:
        await message.answer("❌ У вас немає виданих чеків Champion.")
        return

    text = "🔒 **Ваші активні чеки Champion**\n\nОберіть, який хочете закрити:\n\n"
    buttons = []
    active_count = 0

    for ch in champion_checks:
        code = ch["code"]

        # === Перевіряємо актуальний баланс через API ===
        status = await check_invoice(code)
        if not status or not status.get("success"):
            continue

        remaining = float(status.get("sum", 0))

        if remaining <= 0:
            continue  # пропускаємо закриті/порожні чеки

        active_count += 1
        short = code[-6:] if len(code) >= 6 else code

        text += f"🔑 <code>{code}</code> — 💰 <b>{remaining:.0f} грн</b>\n"

        buttons.append([
            InlineKeyboardButton(
                text=f"🔒 Закрити •••{short} ({remaining:.0f} грн)",
                callback_data=f"close_champ_{code}"
            )
        ])

    if active_count == 0:
        await message.answer("❌ У вас немає активних чеків Champion з балансом більше 0 грн.")
        return

    buttons.append([
        InlineKeyboardButton(text="❌ Скасувати", callback_data="close_cancel")
    ])

    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )


@router.callback_query(F.data.startswith("close_champ_"))
async def process_close_check(callback: CallbackQuery):
    invoice = callback.data.removeprefix("close_champ_")
    user_id = callback.from_user.id

    # Перевірка власності
    user_checks = await get_issued_checks_for_user(user_id)
    if not any(ch["code"] == invoice for ch in user_checks):
        await callback.answer("❌ Цей чек вам не належить!", show_alert=True)
        return

    await callback.answer("🔄 Закриваємо чек...")

    result = await close_invoice(invoice)

    if not result or not result.get("success"):
        await callback.message.edit_text("❌ Не вдалося закрити чек. Спробуйте пізніше.")
        return

    remaining = int(result.get("sum", 0))

    if remaining > 0:
        await add_to_balance(user_id, remaining)

    await callback.message.edit_text(
        f"✅ Чек <code>{invoice}</code> успішно закрито!\n\n"
        f"💰 Повернено на баланс: <b>{remaining} грн</b>",
        parse_mode="HTML"
    )

    # Повідомлення адміну
    await callback.bot.send_message(
        ADMIN_ID,
        f"🔒 Користувач закрив чек Champion\n\n"
        f"👤 {callback.from_user.full_name} (@{callback.from_user.username or '—'})\n"
        f"🔑 Чек: <code>{invoice}</code>\n"
        f"💰 Повернено: <b>{remaining} грн</b>",
        parse_mode="HTML"
    )


@router.callback_query(F.data == "close_cancel")
async def close_cancel(callback: CallbackQuery):
    await callback.message.edit_text("❌ Закриття чека скасовано.")
    await callback.answer()


# ==================== ПОПОВНЕННЯ ЧЕКА CHAMPION ====================

@router.message(F.text == "💵 Поповнити чек")
async def show_checks_to_topup(message: Message, state: FSMContext):
    user_id = message.from_user.id
    checks = await get_issued_checks_for_user(user_id)

    champion_checks = [ch for ch in checks if "Champion" in ch.get("check_type", "")]

    if not champion_checks:
        await message.answer("❌ У вас немає виданих чеків Champion.")
        return

    text = "💵 **Оберіть чек для поповнення**\n\n"
    buttons = []
    active_count = 0

    for ch in champion_checks:
        code = ch["code"]
        status = await check_invoice(code)

        if not status or not status.get("success"):
            continue

        remaining = float(status.get("sum", 0))
        active_count += 1
        short = code[-6:]

        text += f"🔑 <code>{code}</code> — 💰 {remaining:.0f} грн\n"
        buttons.append([
            InlineKeyboardButton(
                text=f"Поповнити •••{short} ({remaining:.0f} грн)",
                callback_data=f"topup_champ_{code}"
            )
        ])

    if active_count == 0:
        await message.answer("❌ Немає доступних чеків для поповнення.")
        return

    buttons.append([InlineKeyboardButton(text="❌ Скасувати", callback_data="topup_cancel")])

    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )


@router.callback_query(F.data.startswith("topup_champ_"))
async def start_topup_check(callback: CallbackQuery, state: FSMContext):
    invoice = callback.data.removeprefix("topup_champ_")

    await state.update_data(invoice=invoice)
    await state.set_state(AddToCheckFSM.waiting_for_amount)

    await callback.message.edit_text(
        f"💵 Введіть суму поповнення для чека <code>{invoice}</code>\n"
        f"(від 10 грн)",
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(AddToCheckFSM.waiting_for_amount)
async def process_topup_amount(message: Message, state: FSMContext):
    try:
        amount = int(message.text)
        if amount < 10:
            await message.answer("❌ Мінімальна сума поповнення — 10 грн")
            return
    except (TypeError, ValueError):
        await message.answer("❌ Введіть число")
        return

    data = await state.get_data()
    invoice = data.get("invoice")

    user_id = message.from_user.id
    balance = await get_balance(user_id)

    if balance < amount:
        await message.answer("❌ Недостатньо коштів на балансі.")
        await state.clear()
        return

    # Поповнюємо чек
    result = await add_to_invoice(invoice, amount)

    if not result or not result.get("success"):
        await message.answer("❌ Не вдалося поповнити чек. Спробуйте пізніше.")
        await state.clear()
        return

    # Списуємо з балансу користувача
    await add_to_balance(user_id, -amount)

    new_sum = result.get("new_sum", amount)

    await message.answer(
        f"✅ Чек <code>{invoice}</code> успішно поповнено на <b>{amount} грн</b>\n\n"
        f"Новий баланс чека: <b>{new_sum:.0f} грн</b>",
        parse_mode="HTML"
    )

    # Повідомлення адміну
    await message.bot.send_message(
        ADMIN_ID,
        f"💵 Користувач поповнив чек\n\n"
        f"👤 {message.from_user.full_name} (@{message.from_user.username or '—'})\n"
        f"🔑 Чек: <code>{invoice}</code>\n"
        f"💰 Поповнено: <b>{amount} грн</b>",
        parse_mode="HTML"
    )

    await state.clear()


@router.callback_query(F.data == "topup_cancel")
async def topup_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Поповнення скасовано.")
    await callback.answer()











