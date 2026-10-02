"""Promotion eligibility independent of withdrawals and accounting net losses."""
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import aiosqlite

KYIV = ZoneInfo("Europe/Kyiv")
WINDOW_SECONDS = 86400
EXPIRED_MESSAGE = "❌ Час участі в акціях закінчився. Потрібен депозит або приз із сейфа протягом останніх 24 годин."


async def ensure_deposits(db):
    await db.execute("""CREATE TABLE IF NOT EXISTS promo_deposits (
        id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL,
        amount INTEGER NOT NULL CHECK (amount > 0), credited_at REAL NOT NULL
    )""")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_promo_deposits_user_time ON promo_deposits(user_id, credited_at)")


async def migrate_deposits(db):
    """Import known credits once; legacy payment log timestamps use fixed UTC+3."""
    cur = await db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='promo_deposits'")
    if await cur.fetchone():
        return
    await ensure_deposits(db)
    await db.execute("""
        INSERT INTO promo_deposits(user_id, amount, credited_at)
        SELECT user_id, amount, CAST(strftime('%s', created_at, '-3 hours') AS REAL)
        FROM payment_logs WHERE amount > 0 AND user_id IS NOT NULL
        AND strftime('%s', created_at, '-3 hours') IS NOT NULL
    """)


async def record_deposit(db, user_id, amount):
    if amount <= 0:
        return
    await ensure_deposits(db)
    await db.execute("INSERT INTO promo_deposits(user_id, amount, credited_at) VALUES (?, ?, ?)",
                     (user_id, amount, time.time()))


async def get_access(db_path, user_id, *, now=None):
    now = time.time() if now is None else now
    local_now = datetime.fromtimestamp(now, KYIV)
    start = (local_now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)).timestamp()
    async with aiosqlite.connect(db_path) as db:
        cur = await db.execute("""
            SELECT MAX(credited_at), COALESCE(SUM(CASE WHEN credited_at >= ? THEN amount ELSE 0 END), 0)
            FROM promo_deposits WHERE user_id = ? AND credited_at <= ?
        """, (start, user_id, now))
        last, deposits = await cur.fetchone()
    remaining = max(0, last + WINDOW_SECONDS - now) if last is not None else 0
    return {"active": remaining > 0, "remaining_seconds": remaining, "deposits": deposits}


def format_remaining(access):
    if not access["active"]:
        return "⏱ Участь в акціях: час вичерпано"
    seconds = int(access["remaining_seconds"])
    hours, minutes = seconds // 3600, seconds % 3600 // 60
    return f"⏱ Залишилось на акції: {hours} год {minutes} хв" if seconds >= 60 else "⏱ Залишилось на акції: менше хвилини"
