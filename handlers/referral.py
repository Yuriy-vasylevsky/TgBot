# from aiogram import Router, F, types
# from aiogram.utils.keyboard import InlineKeyboardBuilder
# from db import get_referrals, is_referred, add_referral, get_balance
# from db import get_referrals, get_all_referrals
# from handlers.config import ADMINS
# router = Router(name="referral")

# REFERRAL_BONUS = 50


# def format_referral_list(referrals: list[dict]) -> str:
#     if not referrals:
#         return "У вас ще немає рефералів"

#     lines = []
#     for r in referrals:
#         name = f"@{r['username']}" if r['username'] else r['full_name'] or f"#{r['referred_id']}"

#         if r["was_existing_user"]:
#             status = "⚠️ вже був в боті"
#         elif r["paid"]:
#             status = "✅ оплатив"
#         else:
#             status = "⏳ не оплатив"

#         lines.append(f"• {name} — {status}")

#     return "\n".join(lines)


# @router.message(F.text == "👥 Реферали")
# async def referral_menu(message: types.Message):
#     user_id = message.from_user.id
#     bot_info = await message.bot.get_me()
#     ref_link = f"https://t.me/{bot_info.username}?start=ref_{user_id}"

#     referrals = await get_referrals(user_id)
#     paid_count = sum(1 for r in referrals if r["paid"] and not r["was_existing_user"])
#     total_earned = paid_count * REFERRAL_BONUS

#     ref_list = format_referral_list(referrals)

#     text = (
#         f"👥 <b>Реферальна програма</b>\n\n"
#         f"За кожного друга який <b>поповнить баланс</b> через бот "
#         f"ви отримаєте <b>{REFERRAL_BONUS} грн</b>\n\n"
#         f"🔗 <b>Ваше посилання:</b>\n"
#         f"<code>{ref_link}</code>\n\n"
#         f"💰 Зароблено всього: <b>{total_earned} грн</b>\n"
#         f"👤 Запрошено: <b>{len(referrals)}</b>\n\n"
#         f"<b>Список рефералів:</b>\n"
#         f"{ref_list}"
#     )

#     await message.answer(text, parse_mode="HTML", disable_web_page_preview=True)



from aiogram import Router, F, types

from db import (
    get_referrals,
    get_all_referrals,
    is_referred,
    add_referral,
    get_balance,
)

# from handlers.config import ADMINS
from handlers.config import ADMIN_ID

router = Router(name="referral")

REFERRAL_BONUS = 50


def format_referral_list(referrals: list[dict]) -> str:
    if not referrals:
        return "У вас ще немає рефералів"

    lines = []

    for r in referrals:
        name = (
            f"@{r['username']}"
            if r["username"]
            else r["full_name"] or f"#{r['referred_id']}"
        )

        if r["was_existing_user"]:
            status = "⚠️ вже був в боті"
        elif r["paid"]:
            status = "✅ оплатив"
        else:
            status = "⏳ не оплатив"

        lines.append(f"• {name} — {status}")

    return "\n".join(lines)


def user_link(user_id: int, username: str | None, full_name: str | None):
    if username:
        return f"@{username}"

    name = full_name or f"ID {user_id}"

    return f'<a href="tg://user?id={user_id}">{name}</a>'


@router.message(F.text == "👥 Реферали")
async def referral_menu(message: types.Message):
    user_id = message.from_user.id

    bot_info = await message.bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start=ref_{user_id}"

    referrals = await get_referrals(user_id)

    paid_count = sum(
        1 for r in referrals
        if r["paid"] and not r["was_existing_user"]
    )

    total_earned = paid_count * REFERRAL_BONUS

    text = (
        f"👥 <b>Реферальна програма</b>\n\n"
        f"За кожного друга який <b>поповнить баланс</b> через бот "
        f"ви отримаєте <b>{REFERRAL_BONUS} грн</b>\n\n"
        f"🔗 <b>Ваше посилання:</b>\n"
        f"<code>{ref_link}</code>\n\n"
        f"💰 Зароблено всього: <b>{total_earned} грн</b>\n"
        f"👤 Запрошено: <b>{len(referrals)}</b>\n\n"
        f"<b>Список рефералів:</b>\n"
        f"{format_referral_list(referrals)}"
    )

    await message.answer(
        text,
        parse_mode="HTML",
        disable_web_page_preview=True
    )


@router.message(F.text == "👥 Всі реферали")
async def all_referrals(message: types.Message):
    
    if message.from_user.id != ADMIN_ID:   # якщо один адмін
        return

    referrals = await get_all_referrals()

    if not referrals:
        await message.answer("Рефералів ще немає.")
        return

    total = len(referrals)
    paid = sum(1 for r in referrals if r["paid"])
    existing = sum(1 for r in referrals if r["was_existing_user"])
    waiting = total - paid - existing

    text = (
        "👥 <b>Всі реферали</b>\n\n"
        f"📊 Всього: <b>{total}</b>\n"
        f"✅ Оплатили: <b>{paid}</b>\n"
        f"⏳ Не оплатили: <b>{waiting}</b>\n"
        f"⚠️ Старі користувачі: <b>{existing}</b>\n\n"
    )

    for r in referrals:

        referrer = user_link(
            r["referrer_id"],
            r["referrer_username"],
            r["referrer_name"]
        )

        referred = user_link(
            r["referred_id"],
            r["referred_username"],
            r["referred_name"]
        )

        if r["was_existing_user"]:
            status = "⚠️ Вже був у боті"
        elif r["paid"]:
            status = "✅ Оплатив"
        else:
            status = "⏳ Не оплатив"

        bonus = (
            "🎁 Бонус виданий"
            if r["bonus_given"]
            else "❌ Бонус не виданий"
        )

        text += (
            f"👤 Реферер: {referrer}\n"
            f"↳ Реферал: {referred}\n"
            f"📌 {status}\n"
            f"{bonus}\n"
            f"🕒 {r['created_at']}\n\n"
        )

    for i in range(0, len(text), 3500):
        await message.answer(
            text[i:i + 3500],
            parse_mode="HTML",
            disable_web_page_preview=True
        )