import logging
from aiogram import Router, F, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from datetime import datetime, timezone, timedelta
from db import (
    get_user_data,
    add_or_update_user,
    has_claimed_gift,
    get_issued_checks_for_user,
)
from db.wallet import get_balance
from handlers.menu import main_menu

router = Router()
logging.basicConfig(level=logging.INFO)


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


def build_profile_text(user_id, username, full_name, balance, weekly_coupons) -> str:
    username_line = f"@{username}" if username != "—" else "без username"
    balance_bar = build_balance_bar(balance)

    if weekly_coupons == 0:
        promo_icons = "😔"
    else:
        promo_icons = "🎟 " * min(weekly_coupons, 15)
        if weekly_coupons > 15:
            promo_icons += f"+{weekly_coupons - 15}"

    return (
        f"╔════════════╗\n"
        f"║ 👤 <b>МІЙ КАБІНЕТ</b> \n"
        f"╚════════════╝\n"
        f"<b>{full_name}</b>\n"
        f"🆔 <code>{user_id}</code>\n"
        f"━━━━━━━━━━━━\n"
        f"💰 <b>БАЛАНС</b> : {balance}\n"
        # f"   {balance_bar}\n"
        # f"   <b>{balance} грн</b>\n"
        f"━━━━━━━━━━━━\n\n"
        f"🎟 <b>Зібрано PROMO :</b> <code>{weekly_coupons}</code>\n"
        f"{promo_icons}\n"
    )


async def build_checks_text(user_id: int) -> str:
    all_checks = await get_issued_checks_for_user(user_id)

    KYIV = timezone(timedelta(hours=3))
    now = datetime.now(KYIV)
    today = now.date()
    yesterday = (now - timedelta(days=1)).date()

    buckets = {
        "сьогодні": [],
        "вчора": [],
    }

    for ch in all_checks:
        try:
            dt = datetime.fromisoformat(ch["issued_at"])
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            d = dt.astimezone(KYIV).date()
            if d == today:
                buckets["сьогодні"].append((ch, dt))
            elif d == yesterday:
                buckets["вчора"].append((ch, dt))
        except Exception:
            pass

    if not any(buckets.values()):
        return "\n\n🔑 <b>Мої чеки:</b>\n😔 За останні 2 дні чеків немає"

    result = "\n\n━━━━━━━━━━━━\n🔑 <b>МОЇ ЧЕКИ</b>\n"

    for label, items in buckets.items():
        if not items:
            result += f"\n📅 <b>{label.capitalize()}:</b> немає\n"
            continue

        total = sum(ch["price"] for ch, _ in items)
        result += f"\n📅 <b>{label.capitalize()}</b> ({len(items)} шт · {total} грн):\n\n"

        for ch, dt in items:
            time_str = dt.astimezone(KYIV).strftime("%H:%M")
            result += (
                f"┌ {ch['check_type']}\n"
                f"├ 🔑 <code>{ch['code']}</code>\n"
                f"└ 💰 {ch['price']} грн · ⏰ {time_str}\n\n"
            )

    total_all = sum(ch["price"] for items in buckets.values() for ch, _ in items)
    result += f"━━━━━━━━━━━━\n💵 Всього витрачено: <b>{total_all} грн</b>"

    return result


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

    profile_text = build_profile_text(user_id, username, full_name, balance, weekly_coupons)
    checks_text = await build_checks_text(user_id)

    await message.answer(
        profile_text + checks_text,
        parse_mode="HTML",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="🔙 Назад до головного меню")]],
            resize_keyboard=True,
        )
    )


# @router.message(F.text == "🏠 Головне меню")
# async def back_to_main_menu(message: types.Message):
#     user_id = message.from_user.id
#     gift_claimed = await has_claimed_gift(user_id)
#     await message.answer(
#         "🏠 Повертаємось до головного меню.",
#         reply_markup=main_menu(user_has_gift=gift_claimed),
#     )