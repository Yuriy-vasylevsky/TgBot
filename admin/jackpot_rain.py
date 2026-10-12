"""Read-only overview of funded checks issued through the bot."""

import asyncio
import logging
from decimal import Decimal
from html import escape

from aiogram import F, Router
from aiogram.types import Message

from db.check import get_issued_checks_with_owners
from handlers.casino_api import get_matic_api
from handlers.config import ADMIN_ID

router = Router(name="jackpot_rain")
_scan_lock = asyncio.Lock()
logger = logging.getLogger(__name__)


async def check_balance(check):
    """None means unverified; zero/negative means no funded active check."""
    try:
        value = await asyncio.wait_for(
            get_matic_api().get_balance_by_code(check["code"]), 20
        )
        balance = Decimal(str(value))
        return balance if balance.is_finite() else None
    except Exception as exc:
        logger.warning(
            "Superomatic balance check failed for code ending %s: %s",
            str(check.get("code", ""))[-4:],
            exc,
        )
        return None


def format_check(check, balance):
    user_id = int(check["user_id"])
    name = escape(str(check.get("full_name") or "Без імені"))
    username = check.get("username")
    handle = f" (@{escape(str(username))})" if username else ""
    return (
        f"<b>{check['platform']}</b> · <b>{balance:.2f} грн</b>\n"
        f"🔑 <code>{escape(str(check['code']))}</code>\n"
        f'👤 <a href="tg://user?id={user_id}">{name}</a>{handle}\n'
        f"🆔 <code>{user_id}</code>\n\n"
    )


@router.message(F.text == "🌠 Зорепад джекпотів")
async def jackpot_rain(message: Message):
    if not message.from_user or message.from_user.id != ADMIN_ID:
        await message.answer("⛔ У вас немає доступу")
        return
    if _scan_lock.locked():
        await message.answer("⏳ Перевірка чеків уже триває. Дочекайтеся результату.")
        return

    async with _scan_lock:
        await message.answer("⏳ Перевіряю баланси чеків Matic…")
        checks = await get_issued_checks_with_owners("Matic")
        if not checks:
            await message.answer(
                "❌ У поточній базі бота немає жодного збереженого "
                "Matic/Superomatic-коду.\n\n"
                "Перевірка API не запускалась."
            )
            return
        funded = []
        failed = 0
        for offset in range(0, len(checks), 5):
            batch = checks[offset:offset + 5]
            balances = await asyncio.gather(*(check_balance(ch) for ch in batch))
            for check, balance in zip(batch, balances):
                if balance is None:
                    failed += 1
                elif balance > 0:
                    funded.append((check, balance))

        funded.sort(key=lambda item: item[1], reverse=True)
        total = sum((balance for _, balance in funded), Decimal(0))
        text = (
            "🌠 <b>Зорепад джекпотів</b>\n"
            "Активні чеки Superomatic із коштами\n\n"
            f"Активних із коштами: <b>{len(funded)}</b>\n"
            f"Загалом: <b>{total:.2f} грн</b>\n\n"
        )
        if failed:
            text += f"⚠️ Не вдалося перевірити: {failed}. Список може бути неповним.\n\n"
        if not funded:
            text += "Чеків із підтвердженим додатним балансом не знайдено."
        for check, balance in funded:
            block = format_check(check, balance)
            if len(text) + len(block) > 3500:
                await message.answer(text, parse_mode="HTML")
                text = "🌠 <b>Зорепад джекпотів — продовження</b>\n\n"
            text += block
        await message.answer(text, parse_mode="HTML")
