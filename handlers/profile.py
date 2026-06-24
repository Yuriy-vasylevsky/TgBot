
import logging
from datetime import datetime, timezone, timedelta

import aiosqlite
from aiogram import Router, F, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from db import (
    get_user_data,
    add_or_update_user,
    DB_PATH,
    add_to_balance,
    get_balance,
    get_daily_net
)
# from db.wallet import get_balance, get_daily_net   # ← Важливий імпорт
from handlers.menu import main_menu
from handlers.config import ADMIN_ID

router = Router()
logging.basicConfig(level=logging.INFO)

KYIV = timezone(timedelta(hours=3))
PROMO_GOAL = 500
CASHBACK_GOAL = 1000
CASHBACK_PERCENT = 0.10


def build_balance_bar(balance: int) -> str:
    levels = [
        (5000, "👑"),
        (2000, "💎"),
        (1000, "🔥"),
        (500,  "⚡️"),
        (200,  "🌟"),
        (0,    "🌱"),
    ]
    for threshold, icon in levels:
        if balance >= threshold:
            tier_icon = icon
            break
    else:
        tier_icon = "🌱"

    filled = min(int(balance / 200), 10)
    bar = "█" * filled + "░" * (10 - filled)
    return f"{tier_icon} [{bar}]"


def build_profile_text(user_id, username, full_name, balance, weekly_coupons, today_net) -> str:
    username_line = f"@{username}" if username != "—" else "без username"

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
        # f"📊 <b>Чистий внесок сьогодні:</b> <b>{today_net} грн</b>\n"
    )


def build_progress_bars(today_net: int) -> str:
    """Прогрес на основі ЧИСТОГО ВНЕСКУ сьогодні"""
    
    # ── Промокод ──
    promo_tier = today_net // PROMO_GOAL
    promo_progress = today_net % PROMO_GOAL
    promo_blocks = min(int((promo_progress / PROMO_GOAL) * 10), 10)
    promo_bar = "█" * promo_blocks + "░" * (10 - promo_blocks)

    if promo_tier > 0:
        promo_line = (
            f"🎟 <b>Промокоди</b> \n"
            f"✅ Можна отримати у касира: {promo_tier} 🎟 \n"
            f"[{promo_bar}] {promo_progress}/{PROMO_GOAL} грн\n"
        )
    else:
        promo_line = (
            f"🎟 <b>Промокоди</b>\n\n"
            f"  [{promo_bar}] {today_net}/{PROMO_GOAL} грн\n"
        )

    # ── Відкат ──
    cashback_tier = today_net // CASHBACK_GOAL
    cashback_progress = today_net % CASHBACK_GOAL
    cashback_blocks = min(int((cashback_progress / CASHBACK_GOAL) * 10), 10)
    cashback_bar = "█" * cashback_blocks + "░" * (10 - cashback_blocks)

    if cashback_tier > 0:
        earned = int(cashback_tier * CASHBACK_GOAL * CASHBACK_PERCENT)
        cashback_line = (
            f"💸 <b>Відкат {int(CASHBACK_PERCENT * 100)}%</b>\n"
            f"✅ <b>Отримайте у касира:</b> {earned} грн  \n"
            f"[{cashback_bar}] {cashback_progress}/{CASHBACK_GOAL} грн\n"
        )
    else:
        cashback_line = (
            f"💸 <b>Відкат {int(CASHBACK_PERCENT * 100)}%</b>\n\n"
            f"  [{cashback_bar}] {today_net}/{CASHBACK_GOAL} грн\n"
        )

    return (
        f"\n━━━━━━━━━━━━\n"
        f"📊 <b>Трекер акцій  </b>\n\n"
        f"{promo_line}\n"
        f"{cashback_line}"
    )


def profile_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        # [InlineKeyboardButton(text="🔙 Назад до головного меню", callback_data="profile:main_menu")],
    ])


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

    balance = await get_balance(user_id)
    weekly_coupons = user_data.get("games_played", 0)
    today_net = await get_daily_net(user_id)   # ← Чистий внесок сьогодні

    profile_text = build_profile_text(user_id, username, full_name, balance, weekly_coupons, today_net)
    progress_text = build_progress_bars(today_net)

    await message.answer(
        profile_text + progress_text,
        parse_mode="HTML",
        reply_markup=profile_keyboard(),
    )


@router.callback_query(F.data == "profile:main_menu")
async def cb_back_to_main_menu(callback: types.CallbackQuery):
    await callback.message.delete()
    await callback.message.answer(
        "🏠 Головне меню",
        reply_markup=main_menu(),
    )
    await callback.answer()