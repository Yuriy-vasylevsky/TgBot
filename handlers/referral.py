from aiogram import Router, F, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from collections import defaultdict

from db import (
    REFERRAL_BONUS,
    get_referrals,
    get_all_referrals,
    get_balance,
)

from handlers.config import ADMIN_ID

router = Router(name="referral")


def user_link(user_id: int, username: str | None, full_name: str | None):
    if username:
        return f"@{username}"
    name = full_name or f"ID {user_id}"
    return f'<a href="tg://user?id={user_id}">{name}</a>'


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


async def build_all_referrers_content() -> tuple[str, InlineKeyboardMarkup | None]:
    """Повертає (text, markup) для списку всіх реферерів."""
    all_referrals_data = await get_all_referrals()
    if not all_referrals_data:
        return "Рефералів ще немає.", None

    referrer_dict = defaultdict(list)
    for r in all_referrals_data:
        referrer_dict[r["referrer_id"]].append(r)

    keyboard = []
    for referrer_id, refs in referrer_dict.items():
        sample = refs[0]
        name = (
            sample.get("referrer_username") or
            sample.get("referrer_name") or
            f"ID {referrer_id}"
        )

        total = len(refs)
        paid = sum(1 for r in refs if r["paid"] and not r["was_existing_user"])

        button_text = f"{name} — {paid}/{total} оплачено"
        keyboard.append([InlineKeyboardButton(
            text=button_text,
            callback_data=f"referrer_detail:{referrer_id}"
        )])

    text = (
        f"<b>👥 Всі реферери: {len(referrer_dict)}</b>\n\n"
        "Натисніть на реферера, щоб переглянути його рефералів:"
    )
    return text, InlineKeyboardMarkup(inline_keyboard=keyboard)


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
    if message.from_user.id != ADMIN_ID:
        return

    text, markup = await build_all_referrers_content()
    await message.answer(text, parse_mode="HTML", reply_markup=markup)


@router.callback_query(F.data.startswith("referrer_detail:"))
async def referrer_detail(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("У вас немає доступу!", show_alert=True)
        return

    await callback.answer()

    referrer_id = int(callback.data.split(":")[1])

    all_referrals_data = await get_all_referrals()
    user_refs = [r for r in all_referrals_data if r["referrer_id"] == referrer_id]

    if not user_refs:
        await callback.answer("Рефералів не знайдено", show_alert=True)
        return

    referrer_link = user_link(
        referrer_id,
        user_refs[0].get("referrer_username"),
        user_refs[0].get("referrer_name")
    )

    text = f"<b>👤 Реферер:</b> {referrer_link}\n\n"

    for r in user_refs:
        referred_link = user_link(
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

        bonus = "🎁 Бонус виданий" if r["bonus_given"] else "❌ Бонус не виданий"

        text += (
            f"↳ {referred_link}\n"
            f"   {status}\n"
            f"   {bonus}\n"
            f"   🕒 {r['created_at']}\n\n"
        )

    back_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="← Назад до списку реферерів", callback_data="back_to_all_referrers")]
    ])

    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=back_kb
    )


@router.callback_query(F.data == "back_to_all_referrers")
async def back_to_all_referrers(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("У вас немає доступу!", show_alert=True)
        return

    await callback.answer()

    text, markup = await build_all_referrers_content()
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=markup
    )
