# import logging
# from datetime import datetime, timezone, timedelta

# import aiosqlite
# from aiogram import Router, F, types
# from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# from db import (
#     get_user_data,
#     add_or_update_user,
#     get_balance,
#     get_daily_net,
#     get_cashback_status,
#     claim_cashback,
# )
# from handlers.menu import main_menu
# from handlers.config import ADMIN_ID   # ← Додано

# router = Router()
# logging.basicConfig(level=logging.INFO)

# KYIV = timezone(timedelta(hours=3))
# PROMO_GOAL = 500
# CASHBACK_GOAL = 1000
# CASHBACK_PERCENT = 0.10


# def build_balance_bar(balance: int) -> str:
#     levels = [
#         (5000, "👑"), (2000, "💎"), (1000, "🔥"),
#         (500,  "⚡️"), (200,  "🌟"), (0,    "🌱"),
#     ]
#     for threshold, icon in levels:
#         if balance >= threshold:
#             return f"{icon} [{'█' * min(int(balance / 200), 10)}{'░' * (10 - min(int(balance / 200), 10))}]"
#     return f"🌱 [{'░' * 10}]"


# def build_profile_text(user_id, username, full_name, balance, weekly_coupons) -> str:
#     return (
#         f"╔════════════╗\n"
#         f"║ 👤 <b>МІЙ КАБІНЕТ</b> \n"
#         f"╚════════════╝\n"
#         f"<b>{full_name}</b>\n"
#         f"🆔 <code>{user_id}</code>\n"
#         f"━━━━━━━━━━━━\n"
#         f"💰 <b>БАЛАНС</b>: {balance} грн\n"
#         f"{build_balance_bar(balance)}\n"
#         f"━━━━━━━━━━━━\n\n"
#         f"<b>Зібрано PROMO :</b> <code>{weekly_coupons}</code>\n"
#         f"{'🎟 ' * min(weekly_coupons, 15)}{'+' + str(weekly_coupons - 15) if weekly_coupons > 15 else ''}\n"
#     )


# def build_progress_bars(today_net: int, cashback_status: dict) -> str:
#     """Прогрес-бары"""
    
#     # Промокоди
#     promo_tier = today_net // PROMO_GOAL
#     promo_progress = today_net % PROMO_GOAL
#     promo_blocks = min(int((promo_progress / PROMO_GOAL) * 10), 10)
#     promo_bar = "█" * promo_blocks + "░" * (10 - promo_blocks)

#     promo_line = (
#         f"🎟 <b>Промокоди</b>\n"
#         f"{'✅ Можна отримати у касира: ' + str(promo_tier) + ' 🎟' if promo_tier > 0 else ''}\n"
#         f"[{promo_bar}] {promo_progress}/{PROMO_GOAL} грн\n"
#     )

#     # Кешбек
#     available_net = cashback_status["available_net"]
#     can_claim = cashback_status["can_claim"]
#     claim_amount = cashback_status["claim_amount"]
#     balance_too_high = cashback_status.get("balance_too_high", False)
#     current_balance = cashback_status.get("balance", 0)

#     cashback_blocks = min(int((min(available_net, CASHBACK_GOAL) / CASHBACK_GOAL) * 10), 10)
#     cashback_bar = "█" * cashback_blocks + "░" * (10 - cashback_blocks)

#     if can_claim:
#         cashback_line = (
#             f"💸 <b>Відкат 10%</b>\n\n"
#             f"✅ <b>Доступно до видачі: {claim_amount} грн</b>\n"
#             f"[{cashback_bar}] {available_net}/{CASHBACK_GOAL}+ грн\n"
#             f"👉 Натисніть кнопку нижче щоб отримати\n"
#         )
#     elif balance_too_high and available_net >= CASHBACK_GOAL:
#         cashback_line = (
#             f"💸 <b>Відкат 10%</b>\n\n"
#             f"✅ Доступно {claim_amount} грн\n"
#             # f"   (баланс {current_balance} грн — потрібно ≤ 50)\n"
#             f"[{cashback_bar}] {available_net}/{CASHBACK_GOAL} грн\n"
#         )
#     else:
#         cashback_line = (
#             f"💸 <b>Відкат 10%</b>\n"
#             f"  [{cashback_bar}] {available_net}/{CASHBACK_GOAL} грн\n"
#         )

#     return f"\n━━━━━━━━━━━━\n📊 <b>Трекер акцій</b>\n\n{promo_line}\n{cashback_line}"


# def profile_keyboard(can_claim: bool = False) -> InlineKeyboardMarkup:
#     keyboard = []
#     if can_claim:
#         keyboard.append([InlineKeyboardButton(
#             text="💸 Забрати кешбек", 
#             callback_data="profile:claim_cashback"
#         )])
#     return InlineKeyboardMarkup(inline_keyboard=keyboard)


# async def render_profile(user_id: int, username: str, full_name: str):
#     user_data = await get_user_data(user_id)
#     if not user_data:
#         return None, None

#     balance = await get_balance(user_id)
#     weekly_coupons = user_data.get("games_played", 0)
#     today_net = await get_daily_net(user_id)
#     cashback_status = await get_cashback_status(user_id)

#     profile_text = build_profile_text(user_id, username, full_name, balance, weekly_coupons)
#     progress_text = build_progress_bars(today_net, cashback_status)

#     text = profile_text + progress_text
#     kb = profile_keyboard(can_claim=cashback_status.get("available_net", 0) >= CASHBACK_GOAL)

#     return text, kb


# # ====================== ХЕНДЛЕРИ ======================

# @router.message(F.text == "👤 Мій кабінет")
# async def show_profile(message: types.Message):
#     user_id = message.from_user.id
#     username = message.from_user.username or "—"
#     full_name = message.from_user.full_name or "—"

#     await add_or_update_user(user_id, username, full_name)

#     text, kb = await render_profile(user_id, username, full_name)
#     if not text:
#         await message.answer("⚠️ Помилка завантаження профілю.")
#         return

#     await message.answer(text, parse_mode="HTML", reply_markup=kb)


# @router.callback_query(F.data == "profile:claim_cashback")
# async def cb_claim_cashback(callback: types.CallbackQuery):
#     user_id = callback.from_user.id
#     username = callback.from_user.username or "—"
#     full_name = callback.from_user.full_name or "—"

#     result = await claim_cashback(user_id)

#     if not result.get("success"):
#         if result.get("reason") == "not_enough":
#             await callback.answer("❌ Недостатньо коштів для кешбеку", show_alert=True)
#         elif result.get("reason") == "balance_too_high":
#             await callback.answer(
#                 f"❌ Щоб отримати кешбек на балансі не повинно бути коштів ‼️",
#                 show_alert=True
#             )
#         else:
#             await callback.answer("⚠️ Не вдалося отримати кешбек", show_alert=True)
#         return

#     # ==================== УСПІШНО ====================
#     amount = result["cashback_amount"]
#     new_balance = result.get("new_balance", 0)

#     await callback.answer(f"✅ Кешбек {amount} грн успішно нараховано!", show_alert=True)

#     # Сповіщення адміністратору
#     try:
#         admin_text = (
#             f"💸 <b>Користувач забрав кешбек</b>\n\n"
#             f"👤 <b>{full_name}</b>\n"
#             f"🆔 <a href=\"tg://user?id={user_id}\">{user_id}</a>\n"
#             f"{'@' + username if username != '—' else ''}\n\n"
#             f"💰 Отримано: <b>{amount} грн</b>\n"
#             f"📊 Новий баланс: <b>{new_balance} грн</b>"
#         )
        
#         await callback.bot.send_message(
#             ADMIN_ID, 
#             admin_text, 
#             parse_mode="HTML"
#         )
#     except Exception as e:
#         logging.error(f"Не вдалося надіслати сповіщення адміну про кешбек: {e}")

#     # Оновлюємо профіль користувачу
#     text, kb = await render_profile(user_id, username, full_name)
#     if text:
#         try:
#             await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
#         except Exception:
#             pass

import logging
from datetime import datetime, timezone, timedelta

import aiosqlite
from aiogram import Router, F, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from db import (
    get_user_data,
    add_or_update_user,
    get_balance,
    get_daily_net,
    get_cashback_status,
    claim_cashback,
    get_promo_status,
    claim_promo,
)
from handlers.menu import main_menu
from handlers.config import ADMIN_ID   # ← Додано

router = Router()
logging.basicConfig(level=logging.INFO)

KYIV = timezone(timedelta(hours=3))
PROMO_GOAL = 500
CASHBACK_GOAL = 1000
CASHBACK_PERCENT = 0.10


def build_balance_bar(balance: int) -> str:
    levels = [
        (5000, "👑"), (2000, "💎"), (1000, "🔥"),
        (500,  "⚡️"), (200,  "🌟"), (0,    "🌱"),
    ]
    for threshold, icon in levels:
        if balance >= threshold:
            return f"{icon} [{'█' * min(int(balance / 200), 10)}{'░' * (10 - min(int(balance / 200), 10))}]"
    return f"🌱 [{'░' * 10}]"


def build_profile_text(user_id, username, full_name, balance, weekly_coupons) -> str:
    return (
        f"╔════════════╗\n"
        f"║ 👤 <b>МІЙ КАБІНЕТ</b> \n"
        f"╚════════════╝\n"
        f"<b>{full_name}</b>\n"
        f"🆔 <code>{user_id}</code>\n"
        f"━━━━━━━━━━━━\n"
        f"💰 <b>БАЛАНС</b>: {balance} грн\n"
        f"{build_balance_bar(balance)}\n"
        f"━━━━━━━━━━━━\n\n"
        f"<b>Зібрано PROMO :</b> <code>{weekly_coupons}</code>\n"
        f"{'🎟 ' * min(weekly_coupons, 15)}{'+' + str(weekly_coupons - 15) if weekly_coupons > 15 else ''}\n"
    )


def build_progress_bars(today_net: int, cashback_status: dict, promo_status: dict) -> str:
    """Прогрес-бары"""

    # Промокоди (тепер як кешбек — з власною claimed_base)
    available_net_promo = promo_status["available_net"]
    available_count_promo = promo_status.get("available_count", available_net_promo // PROMO_GOAL)

    promo_progress_in_tier = available_net_promo % PROMO_GOAL
    promo_blocks = min(int((promo_progress_in_tier / PROMO_GOAL) * 10), 10)
    promo_bar = "█" * promo_blocks + "░" * (10 - promo_blocks)

    if available_count_promo > 0:
        promo_line = (
            f"🎟 <b>Промокоди</b>\n\n"
            f"✅ <b>Доступно: {available_count_promo} шт</b>\n"
            f"[{promo_bar}] {promo_progress_in_tier}/{PROMO_GOAL} грн\n"
            # f"👉 Натисніть кнопку нижче щоб отримати\n"
        )
    else:
        promo_line = (
            f"🎟 <b>Промокоди</b>\n"
            f"[{promo_bar}] {available_net_promo}/{PROMO_GOAL} грн\n"
        )

    # Кешбек
    available_net = cashback_status["available_net"]
    can_claim = cashback_status["can_claim"]
    claim_amount = cashback_status["claim_amount"]
    balance_too_high = cashback_status.get("balance_too_high", False)

    cashback_blocks = min(int((min(available_net, CASHBACK_GOAL) / CASHBACK_GOAL) * 10), 10)
    cashback_bar = "█" * cashback_blocks + "░" * (10 - cashback_blocks)

    if can_claim:
        cashback_line = (
            f"💸 <b>Відкат 10%</b>\n\n"
            f"✅ <b>Доступно до видачі: {claim_amount} грн</b>\n"
            f"[{cashback_bar}] {available_net}/{CASHBACK_GOAL}+ грн\n"
            # f"👉 Натисніть кнопку нижче щоб отримати\n"
        )
    elif balance_too_high and available_net >= CASHBACK_GOAL:
        cashback_line = (
            f"💸 <b>Відкат 10%</b>\n\n"
            f"✅ Доступно {claim_amount} грн\n"
            f"[{cashback_bar}] {available_net}/{CASHBACK_GOAL} грн\n"
        )
    else:
        cashback_line = (
            f"💸 <b>Відкат 10%</b>\n"
            f"  [{cashback_bar}] {available_net}/{CASHBACK_GOAL} грн\n"
        )

    return f"\n━━━━━━━━━━━━\n📊 <b>Трекер акцій</b>\n\n{promo_line}\n{cashback_line}"


def profile_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton(
            text="🎟 Забрати промокод",
            callback_data="profile:claim_promo"
        )],
        [InlineKeyboardButton(
            text="💸 Забрати кешбек",
            callback_data="profile:claim_cashback"
        )],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


async def render_profile(user_id: int, username: str, full_name: str):
    user_data = await get_user_data(user_id)
    if not user_data:
        return None, None

    balance = await get_balance(user_id)
    weekly_coupons = user_data.get("games_played", 0)
    today_net = await get_daily_net(user_id)
    cashback_status = await get_cashback_status(user_id)
    promo_status = await get_promo_status(user_id)

    profile_text = build_profile_text(user_id, username, full_name, balance, weekly_coupons)
    progress_text = build_progress_bars(today_net, cashback_status, promo_status)

    text = profile_text + progress_text
    kb = profile_keyboard()

    return text, kb


# ====================== ХЕНДЛЕРИ ======================

@router.message(F.text == "👤 Мій кабінет")
async def show_profile(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or "—"
    full_name = message.from_user.full_name or "—"

    await add_or_update_user(user_id, username, full_name)

    text, kb = await render_profile(user_id, username, full_name)
    if not text:
        await message.answer("⚠️ Помилка завантаження профілю.")
        return

    await message.answer(text, parse_mode="HTML", reply_markup=kb)


@router.callback_query(F.data == "profile:claim_cashback")
async def cb_claim_cashback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    username = callback.from_user.username or "—"
    full_name = callback.from_user.full_name or "—"

    result = await claim_cashback(user_id)

    if not result.get("success"):
        if result.get("reason") == "not_enough":
            await callback.answer("❌ Недостатньо коштів для кешбеку", show_alert=True)
        elif result.get("reason") == "balance_too_high":
            await callback.answer(
                f"❌ Щоб отримати кешбек на балансі не повинно бути коштів ‼️",
                show_alert=True
            )
        else:
            await callback.answer("⚠️ Не вдалося отримати кешбек", show_alert=True)
        return

    # ==================== УСПІШНО ====================
    amount = result["cashback_amount"]
    new_balance = result.get("new_balance", 0)

    await callback.answer(f"✅ Кешбек {amount} грн успішно нараховано!", show_alert=True)

    # Сповіщення адміністратору
    try:
        admin_text = (
            f"💸 <b>Користувач забрав кешбек</b>\n\n"
            f"👤 <b>{full_name}</b>\n"
            f"🆔 <a href=\"tg://user?id={user_id}\">{user_id}</a>\n"
            f"{'@' + username if username != '—' else ''}\n\n"
            f"💰 Отримано: <b>{amount} грн</b>\n"
            f"📊 Новий баланс: <b>{new_balance} грн</b>"
        )
        
        await callback.bot.send_message(
            ADMIN_ID, 
            admin_text, 
            parse_mode="HTML"
        )
    except Exception as e:
        logging.error(f"Не вдалося надіслати сповіщення адміну про кешбек: {e}")

    # Оновлюємо профіль користувачу
    text, kb = await render_profile(user_id, username, full_name)
    if text:
        try:
            await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
        except Exception:
            pass


@router.callback_query(F.data == "profile:claim_promo")
async def cb_claim_promo(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    username = callback.from_user.username or "—"
    full_name = callback.from_user.full_name or "—"

    result = await claim_promo(user_id)

    if not result.get("success"):
        if result.get("reason") == "not_enough":
            await callback.answer("❌ Недостатньо коштів для промокоду", show_alert=True)
        elif result.get("reason") == "balance_too_high":
            await callback.answer(
                "❌ Щоб отримати промокод на балансі не повинно бути коштів ‼️",
                show_alert=True
            )
        else:
            await callback.answer("⚠️ Не вдалося видати промокод", show_alert=True)
        return

    # ==================== УСПІШНО ====================
    code = result["code"]

    await callback.answer(f"✅ Промокод видано!", show_alert=True)

    # Надсилаємо код окремим повідомленням, щоб його можна було скопіювати
    try:
        await callback.message.answer(
            f"🎟 <b>Ваш промокод:</b>\n\n<code>{code}</code>",
            parse_mode="HTML",
        )
    except Exception as e:
        logging.error(f"Не вдалося надіслати промокод у чат: {e}")

    # Сповіщення адміністратору
    try:
        admin_text = (
            f"🎟 <b>Користувач забрав промокод</b>\n\n"
            f"👤 <b>{full_name}</b>\n"
            f"🆔 <a href=\"tg://user?id={user_id}\">{user_id}</a>\n"
            f"{'@' + username if username != '—' else ''}\n\n"
            f"🎁 Код: <code>{code}</code>"
        )
        await callback.bot.send_message(
            ADMIN_ID,
            admin_text,
            parse_mode="HTML"
        )
    except Exception as e:
        logging.error(f"Не вдалося надіслати сповіщення адміну про промокод: {e}")

    # Оновлюємо профіль користувачу
    text, kb = await render_profile(user_id, username, full_name)
    if text:
        try:
            await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
        except Exception:
            pass