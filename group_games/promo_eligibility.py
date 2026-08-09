from db.wallet import get_daily_net, get_yesterday_net


async def has_recent_deposit(user_id: int) -> bool:
    """Return whether the user deposited today or yesterday."""
    today_net = await get_daily_net(user_id)
    yesterday_net = await get_yesterday_net(user_id)
    return today_net > 0 or yesterday_net > 0


async def reject_without_deposit(message, tracked_messages: list[int]) -> bool:
    """Reject a promo-game throw when the player has no recent deposit."""
    if await has_recent_deposit(message.from_user.id):
        return False

    try:
        await message.delete()
    except Exception:
        pass

    notice = await message.answer(
        f"{message.from_user.mention_html()}, ви не можете брати участь у цій грі.\n"
        "❌ Потрібно мати депозит сьогодні або вчора.",
        parse_mode="HTML",
    )
    tracked_messages.append(notice.message_id)
    return True
