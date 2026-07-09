

import re

from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from handlers.config import ADMIN_ID
# from handlers.profile import notify_reward_progress
from db.check import get_checks_stats, clear_all_checks, get_checks_total_balance
from db import get_balance, add_to_balance, log_check_issued, delete_issued_check
from db import get_issued_checks_for_user
from handlers.menu import checks_menu
from handlers.casino_api import create_invoice, create_matic_checks, close_invoice, check_invoice, add_to_invoice
from admin.bans import is_banned

router = Router(name="admin_checks")

MATIC_BLOCKED_TEXT = "😔 Вибачте, SuperMatic тимчасово не працює."


async def _matic_blocked(target) -> bool:
    """
    Перевіряє, чи забанений користувач.
    Якщо так — надсилає повідомлення про тимчасову недоступність Matic і повертає True.
    Використовувати на початку кожного Matic-хендлера: `if await _matic_blocked(message): return`
    """
    user_id = target.from_user.id
    if await is_banned(user_id):
        if isinstance(target, CallbackQuery):
            await target.answer(MATIC_BLOCKED_TEXT, show_alert=True)
            try:
                await target.message.edit_text(MATIC_BLOCKED_TEXT)
            except Exception:
                pass
        else:
            await target.answer(MATIC_BLOCKED_TEXT)
        return True
    return False


class CheckFSM(StatesGroup):
    waiting_for_custom_amount = State()      # Champion
    waiting_for_custom_matic_amount = State()
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
            [KeyboardButton(text="📋 Мої чеки Champion")],
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
            [KeyboardButton(text="📋 Мої коди Matic")],
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
                InlineKeyboardButton(text="250 грн", callback_data="matic_amt_250"),
            ],
            [
                InlineKeyboardButton(text="✏️ Інша сума", callback_data="matic_amt_custom"),
                InlineKeyboardButton(text="❌ Скасувати", callback_data="matic_cancel")
            ]
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
    balance = await get_balance(message.from_user.id)
    await message.answer(
        f"🏆 <b>Champion</b>\n\n"
        f"💰 <b>Ваш баланс: {balance:,} грн</b>",
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
    if await _matic_blocked(message):
        return
    balance = await get_balance(message.from_user.id)
    await message.answer(
        f"🎰 <b>Matic</b>\n\n"
        f"💰 <b>Ваш баланс: {balance:,} грн</b>",
        parse_mode="HTML",
        reply_markup=matic_main_kb()
    )


@router.message(F.text == "💰 Купити чек Matic")
async def buy_matic(message: Message):
    if await _matic_blocked(message):
        return
    await message.answer(
        "🎰 Оберіть суму Matic:",
        reply_markup=matic_amount_kb()
    )





@router.message(F.text == "📋 Мої коди Matic")
async def matic_my_codes(message: Message):
    if await _matic_blocked(message):
        return
    user_id = message.from_user.id
    checks = await get_issued_checks_for_user(user_id)
    matic_checks = [ch for ch in checks if "Matic" in ch.get("check_type", "")]

    if not matic_checks:
        await message.answer("❌ У вас немає активних Matic кодів")
        return

    text = "📋 <b>Ваші активні Matic коди:</b>\n\n"
    found = 0

    for ch in matic_checks:
        code = ch["code"]
        try:
            remaining = await matic_api.get_balance_by_code(code)

            if remaining < 0:
                await delete_issued_check(code)
                continue
            if remaining <= 0:
                continue

            found += 1
            text += (
                f"🔑 <code>{code}</code>\n"
                f"💰 Баланс: <b>{remaining:.0f} грн</b>\n"
                f"🔗 https://code.greenhost.pw/?c={code}\n\n"
            )
        except Exception as e:
            print(f"[matic_my_codes] code={code} error={e}")
            continue

    if found == 0:
        await message.answer("❌ Немає активних кодів з балансом > 0")
        return

    await message.answer(text, parse_mode="HTML", disable_web_page_preview=True)





@router.message(F.text == "📋 Мої чеки Champion")
async def champion_my_checks(message: Message):
    user_id = message.from_user.id
    checks = await get_issued_checks_for_user(user_id)
    champion_checks = [ch for ch in checks if "Champion" in ch.get("check_type", "")]

    if not champion_checks:
        await message.answer("❌ У вас немає активних чеків Champion")
        return

    text = "📋 <b>Ваші активні чеки Champion:</b>\n\n"
    found = 0

    for ch in champion_checks:
        code = ch["code"]
        try:
            status = await check_invoice(code)
            if not status or not status.get("success"):
                continue
            remaining = float(status.get("sum", 0))
            if remaining <= 0:
                continue

            found += 1
            text += (
                f"🔑 <code>{code}</code>\n"
                f"💰 Баланс: <b>{remaining:.0f} грн</b>\n"
                f"🔗 https://spinplanet.net/?login_code={code}\n\n"
)
        except Exception as e:
            print(f"[champion_my_checks] code={code} error={e}")
            continue

    if found == 0:
        await message.answer("❌ Немає активних чеків з балансом > 0")
        return

    await message.answer(text, parse_mode="HTML", disable_web_page_preview=True)






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
    # await notify_reward_progress(target_message.bot, user_id, user.username, user.full_name or "")

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
    # await notify_reward_progress(target_message.bot, user_id, user.username, user.full_name or "")

    name = f"@{user.username}" if user.username else user.full_name or f"#{user_id}"
    await target_message.bot.send_message(
        ADMIN_ID,
        f"🎁 Видано Matic {amount} грн\n👤 {name}\n🔑 <code>{code}</code>",
        parse_mode="HTML"
    )

    # await target_message.answer(
    #     f"✅ <b>Чек Matic видано!</b>\n\n"
    #     f"🔑 Код: <code>{code}</code>\n"
    #     f"💰 Залишок: {await get_balance(user_id)} грн",
    #     parse_mode="HTML"
    # )

    await target_message.answer(
        f"✅ <b>Чек Matic видано!</b>\n\n"
        # f"🔑 Код: <code>{code}</code>\n"
        f"🔗 https://code.greenhost.pw/?c={code}\n\n"
        f"💰 Залишок: {await get_balance(user_id)} грн",
        parse_mode="HTML",
        disable_web_page_preview=True
)

    await target_message.answer("🎰 Matic меню:", reply_markup=matic_main_kb())


# ==================== CALLBACKS КУПІВЛІ ====================

@router.callback_query(F.data.startswith("champ_amt_"))
async def champion_pick_amount(callback: CallbackQuery, state: FSMContext):
    value = callback.data.removeprefix("champ_amt_")
    if value == "custom":
        await state.set_state(CheckFSM.waiting_for_custom_amount)
        await callback.message.edit_text("🏆 Введіть суму Champion (від 30 грн):")
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
        if amount < 30:
            await message.answer("❌ Мінімум 30 грн")
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






@router.message(CheckFSM.waiting_for_custom_matic_amount)
async def process_custom_matic(message: Message, state: FSMContext):
    if await _matic_blocked(message):
        await state.clear()
        return

    try:
        amount = int(message.text)
        if amount < 30:
            await message.answer("❌ Мінімум 30 грн")
            return
    except:
        await message.answer("❌ Введіть число")
        return

    if await get_balance(message.from_user.id) < amount:
        await message.answer("❌ Недостатньо коштів")
        await state.clear()
        return

    await state.clear()
    await message.answer("🔄 Генеруємо...")
    try:
        result = await create_matic_checks(amount=amount, count=1)
        if result.get("created", 0) > 0 and result.get("codes"):
            code_info = result["codes"][0]
            code = code_info.get("code") or code_info.get("login") or code_info.get("key") or str(code_info)
            await issue_matic_check(message, message.from_user, amount, code)
        else:
            await message.answer("❌ Не вдалося створити Matic чек")
    except Exception as e:
        await message.answer(f"❌ Помилка: {e}")







@router.callback_query(F.data == "champ_cancel")
async def champion_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Скасовано")
    await callback.answer()


@router.callback_query(F.data.startswith("matic_amt_"))
async def matic_pick_amount(callback: CallbackQuery, state: FSMContext):
    if await _matic_blocked(callback):
        return

    value = callback.data.removeprefix("matic_amt_")

    if value == "custom":
        await state.set_state(CheckFSM.waiting_for_custom_matic_amount)
        await callback.message.edit_text("🎰 Введіть суму Matic (від 30 грн):")
        await callback.answer()
        return

    amount = int(value)
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
    if await _matic_blocked(message):
        return

    user_id = message.from_user.id
    checks = await get_issued_checks_for_user(user_id)
    matic_checks = [ch for ch in checks if "Matic" in ch.get("check_type", "")]

    if not matic_checks:
        await message.answer("❌ У вас немає виданих чеків Matic.")
        return

    text = "🔒 **Ваші активні чеки Matic**\n\nОберіть чек для закриття:\n\n"
    buttons = []
    active_count = 0

    for ch in matic_checks:
        code = ch["code"]

        try:
            remaining = await matic_api.get_balance_by_code(code)

            if remaining < 0:
                await delete_issued_check(code)  # чек вже неактивний — прибираємо з бази
                continue

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
            print(f"[Matic Check Error] code={code} error={e}")
            continue

    if active_count == 0:
        await message.answer("❌ Немає активних Matic чеків з балансом > 0 грн.")
        return

    buttons.append([InlineKeyboardButton(text="❌ Скасувати", callback_data="close_cancel")])

    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )

    
@router.message(F.text == "💵 Поповнити чек Matic")
async def show_matic_to_topup(message: Message, state: FSMContext):
    if await _matic_blocked(message):
        return

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
            remaining = await matic_api.get_balance_by_code(code)

            if remaining < 0:
                await delete_issued_check(code)  # чек вже неактивний — прибираємо з бази
                continue

            short = code[-6:]
            text += f"🔑 <code>{code}</code> — 💰 {remaining:.0f} грн\n"
            buttons.append([
                InlineKeyboardButton(
                    text=f"💵 Поповнити •••{short}",
                    callback_data=f"topup_matic_{code}"
                )
            ])
        except Exception as e:
            print(f"[Matic Topup List Error] code={code} error={e}")
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
    if await _matic_blocked(callback):
        return

    code = callback.data.removeprefix("close_matic_")
    user_id = callback.from_user.id

    await callback.answer("🔄 Закриваємо Matic чек...")

    try:
        result = await matic_api.close_check_by_code(code)
        remaining = result.get("balance", 0)

        if remaining > 0:
            await add_to_balance(user_id, int(remaining))

        await delete_issued_check(code)  # прибираємо з бази, щоб не висів у списках

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
    if await _matic_blocked(callback):
        return

    code = callback.data.removeprefix("topup_matic_")
    await state.update_data(matic_code=code, check_type="matic")
    await state.set_state(CheckFSM.waiting_for_amount_topup)
    await callback.message.edit_text(
        f"💵 Введіть суму поповнення для Matic чека <code>{code}</code>\n(від 10 грн)",
        parse_mode="HTML"
    )


@router.message(CheckFSM.waiting_for_amount_topup)
async def process_topup_amount(message: Message, state: FSMContext):
    data = await state.get_data()
    check_type = data.get("check_type")

    if check_type == "matic" and await _matic_blocked(message):
        await state.clear()
        return

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

    try:
        if check_type == "champion":
            invoice = data.get("invoice")
            result = await add_to_invoice(invoice, amount)
            success = result and result.get("success")
            new_sum = result.get("new_sum", amount) if result else amount
        else:  # matic
            matic_code = data.get("matic_code")
            result = await matic_api.add_to_check_by_code(matic_code, amount)
            success = bool(result and "id" in result)  # успіх = повернувся id транзакції
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