from datetime import datetime, timedelta, timezone

import aiosqlite

from .core import DB_PATH


JACKPOT_COOLDOWN_HOURS = 12
KYIV_TZ = timezone(timedelta(hours=3))


def _now_kyiv() -> datetime:
    return datetime.now(KYIV_TZ)


async def is_jackpot_on_cooldown(user_id: int) -> bool:
    return await get_jackpot_cooldown_remaining(user_id) is not None


async def get_jackpot_cooldown_remaining(user_id: int) -> tuple[int, int] | None:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT cooldown_until FROM jackpot_cooldowns WHERE user_id = ?",
            (user_id,),
        ) as cursor:
            row = await cursor.fetchone()

    if not row or not row[0]:
        return None

    try:
        cooldown_until = datetime.fromisoformat(row[0])
        if cooldown_until.tzinfo is None:
            cooldown_until = cooldown_until.replace(tzinfo=KYIV_TZ)
    except (TypeError, ValueError):
        return None

    delta = cooldown_until - _now_kyiv()
    if delta.total_seconds() <= 0:
        return None

    total_seconds = int(delta.total_seconds())
    return total_seconds // 3600, (total_seconds % 3600) // 60


async def set_jackpot_cooldown(
    user_id: int, hours: int = JACKPOT_COOLDOWN_HOURS
) -> None:
    cooldown_until = (_now_kyiv() + timedelta(hours=hours)).isoformat(
        timespec="seconds"
    )
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO jackpot_cooldowns(user_id, cooldown_until)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET cooldown_until = excluded.cooldown_until
            """,
            (user_id, cooldown_until),
        )
        await db.commit()
