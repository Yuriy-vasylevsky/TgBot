from aiogram import Router, F, types
from aiogram.utils.keyboard import InlineKeyboardBuilder
from db import get_referrals, is_referred, add_referral, get_balance

router = Router(name="referral")

REFERRAL_BONUS = 50


def format_referral_list(referrals: list[dict]) -> str:
    if not referrals:
        return "У вас ще немає рефералів"

    lines = []
    for r in referrals:
        name = f"@{r['username']}" if r['username'] else r['full_name'] or f"#{r['referred_id']}"

        if r["was_existing_user"]:
            status = "⚠️ вже був в боті"
        elif r["paid"]:
            status = "✅ оплатив"
        else:
            status = "⏳ не оплатив"

        lines.append(f"• {name} — {status}")

    return "\n".join(lines)


@router.message(F.text == "👥 Реферали")
async def referral_menu(message: types.Message):
    user_id = message.from_user.id
    bot_info = await message.bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start=ref_{user_id}"

    referrals = await get_referrals(user_id)
    paid_count = sum(1 for r in referrals if r["paid"] and not r["was_existing_user"])
    total_earned = paid_count * REFERRAL_BONUS

    ref_list = format_referral_list(referrals)

    text = (
        f"👥 <b>Реферальна програма</b>\n\n"
        f"За кожного друга який <b>поповнить баланс</b> через бот "
        f"ви отримаєте <b>{REFERRAL_BONUS} грн</b>\n\n"
        f"🔗 <b>Ваше посилання:</b>\n"
        f"<code>{ref_link}</code>\n\n"
        f"💰 Зароблено всього: <b>{total_earned} грн</b>\n"
        f"👤 Запрошено: <b>{len(referrals)}</b>\n\n"
        f"<b>Список рефералів:</b>\n"
        f"{ref_list}"
    )

    await message.answer(text, parse_mode="HTML", disable_web_page_preview=True)