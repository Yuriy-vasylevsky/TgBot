"""
Глобальний кулдаун участі в групових іграх (pograb, skarb, тощо).
Одна людина може виграти приз раз на GAME_COOLDOWN_HOURS годин.
Кулдаун встановлюється після виграшу і блокує вхід у будь-яку гру.
"""

import aiosqlite
import logging
from datetime import datetime, timedelta, timezone

from .core import DB_PATH

GAME_COOLDOWN_HOURS = 1
KYIV_TZ = timezone(timedelta(hours=3))


def _now_kyiv() -> datetime:
    return datetime.now(KYIV_TZ)


async def is_game_on_cooldown(user_id: int) -> bool:
    """True — гравець ще на кулдауні і не може приєднатись до гри."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT game_cooldown_until FROM users WHERE user_id = ?",
            (user_id,)
        ) as cur:
            row = await cur.fetchone()

    if not row or not row[0]:
        return False

    try:
        cooldown_until = datetime.fromisoformat(row[0])
        # Якщо немає tzinfo — вважаємо Kyiv
        if cooldown_until.tzinfo is None:
            cooldown_until = cooldown_until.replace(tzinfo=KYIV_TZ)
    except Exception as e:
        logging.warning(f"game_cooldown parse error for user {user_id}: {e}")
        return False

    return _now_kyiv() < cooldown_until


async def get_game_cooldown_remaining(user_id: int) -> tuple[int, int] | None:
    """
    Повертає (години, хвилини) що залишилось до кінця кулдауну.
    None — кулдаун вже закінчився або не встановлений.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT game_cooldown_until FROM users WHERE user_id = ?",
            (user_id,)
        ) as cur:
            row = await cur.fetchone()

    if not row or not row[0]:
        return None

    try:
        cooldown_until = datetime.fromisoformat(row[0])
        if cooldown_until.tzinfo is None:
            cooldown_until = cooldown_until.replace(tzinfo=KYIV_TZ)
    except Exception:
        return None

    now = _now_kyiv()
    if now >= cooldown_until:
        return None

    delta = cooldown_until - now
    hours = int(delta.total_seconds() // 3600)
    minutes = int((delta.total_seconds() % 3600) // 60)
    return hours, minutes


async def set_game_cooldown(user_id: int, hours: int = GAME_COOLDOWN_HOURS):
    """Встановлює кулдаун на N годин від поточного моменту."""
    future = _now_kyiv() + timedelta(hours=hours)
    future_str = future.isoformat(timespec="seconds")

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET game_cooldown_until = ? WHERE user_id = ?",
            (future_str, user_id)
        )
        await db.commit()

    logging.info(f"🕐 Game cooldown встановлено для user {user_id} до {future_str}")


def format_cooldown(hours: int, minutes: int) -> str:
    parts = []
    if hours:
        parts.append(f"{hours} год")
    if minutes or not hours:
        parts.append(f"{minutes} хв")
    return " ".join(parts)