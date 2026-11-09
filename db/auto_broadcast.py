from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import aiosqlite
from db.core import DB_PATH
from handlers.config import ADMIN_ID

KYIV = ZoneInfo("Europe/Kyiv")


def next_daily(clock, now=None, days_mask=127):
    if type(days_mask) is not int or not 1 <= days_mask <= 127:
        raise ValueError("Select at least one weekday")
    hour, minute = map(int, clock.split(":"))
    if len(clock) != 5 or clock != f"{hour:02d}:{minute:02d}" or not (0 <= hour < 24 and 0 <= minute < 60):
        raise ValueError("Use HH:MM")
    now = now or datetime.now(timezone.utc)
    local = now.astimezone(KYIV)
    candidate = local.replace(hour=hour, minute=minute, second=0, microsecond=0, fold=0)
    if candidate.timestamp() <= now.timestamp():
        candidate += timedelta(days=1)
    while not days_mask & (1 << candidate.weekday()):
        candidate += timedelta(days=1)
    # Normalize a nonexistent time during the spring clock change.
    return candidate.astimezone(timezone.utc).timestamp()


async def init_auto_broadcast():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""CREATE TABLE IF NOT EXISTS auto_broadcasts (
            id INTEGER PRIMARY KEY AUTOINCREMENT, photo TEXT NOT NULL,
            caption TEXT, clock TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1,
            next_run REAL NOT NULL)""")
        cur = await db.execute("PRAGMA table_info(auto_broadcasts)")
        if 'days_mask' not in {row[1] for row in await cur.fetchall()}:
            await db.execute("ALTER TABLE auto_broadcasts ADD COLUMN days_mask INTEGER NOT NULL DEFAULT 127")
        await db.execute("""CREATE TABLE IF NOT EXISTS auto_broadcast_deliveries (
            id INTEGER PRIMARY KEY AUTOINCREMENT, broadcast_id INTEGER NOT NULL,
            run_at REAL NOT NULL, user_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            UNIQUE(broadcast_id, run_at, user_id))""")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_auto_delivery_status ON auto_broadcast_deliveries(status, id)")
        # A request interrupted by shutdown may already have reached Telegram.
        await db.execute("UPDATE auto_broadcast_deliveries SET status='uncertain' WHERE status='sending'")
        await db.commit()


async def list_broadcasts():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM auto_broadcasts ORDER BY id DESC")
        return [dict(row) for row in await cur.fetchall()]


async def save_broadcast(photo, caption, clock, days_mask=127):
    when = next_daily(clock, days_mask=days_mask)
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO auto_broadcasts(photo, caption, clock, next_run, days_mask) VALUES (?,?,?,?,?)",
            (photo, caption, clock, when, days_mask),
        )
        await db.commit()
        return cur.lastrowid


async def change_broadcast(bid, action, clock=None, days_mask=None):
    async with aiosqlite.connect(DB_PATH) as db:
        if action == "delete":
            await db.execute("DELETE FROM auto_broadcast_deliveries WHERE broadcast_id=?", (bid,))
            await db.execute("DELETE FROM auto_broadcasts WHERE id=?", (bid,))
        elif action == "toggle":
            await db.execute("UPDATE auto_broadcasts SET enabled=1-enabled WHERE id=?", (bid,))
            await db.execute("UPDATE auto_broadcast_deliveries SET status='cancelled' WHERE broadcast_id=? AND status='pending'", (bid,))
            cur = await db.execute("SELECT clock, days_mask FROM auto_broadcasts WHERE id=?", (bid,))
            row = await cur.fetchone()
            if row:
                await db.execute("UPDATE auto_broadcasts SET next_run=? WHERE id=?", (next_daily(row[0], days_mask=row[1]), bid))
        elif action in {"time", "days"}:
            cur = await db.execute("SELECT clock, days_mask FROM auto_broadcasts WHERE id=?", (bid,))
            row = await cur.fetchone()
            if not row:
                return
            clock = clock if action == 'time' else row[0]
            days_mask = days_mask if action == 'days' else row[1]
            when = next_daily(clock, days_mask=days_mask)
            await db.execute("UPDATE auto_broadcasts SET clock=?, days_mask=?, next_run=? WHERE id=?", (clock, days_mask, when, bid))
            await db.execute("UPDATE auto_broadcast_deliveries SET status='cancelled' WHERE broadcast_id=? AND status='pending'", (bid,))
        else:
            raise ValueError("Unknown action")
        await db.commit()


async def enqueue_due(now=None):
    now = now or datetime.now(timezone.utc)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("BEGIN IMMEDIATE")
        cur = await db.execute("SELECT id, clock, next_run, days_mask FROM auto_broadcasts WHERE enabled=1 AND next_run<=?", (now.timestamp(),))
        for bid, clock, run_at, days_mask in await cur.fetchall():
            if days_mask & (1 << now.astimezone(KYIV).weekday()):
                await db.execute("""INSERT OR IGNORE INTO auto_broadcast_deliveries(broadcast_id, run_at, user_id)
                    SELECT ?, ?, user_id FROM users WHERE user_id > 0 AND user_id != ?""", (bid, run_at, ADMIN_ID))
            await db.execute("UPDATE auto_broadcasts SET next_run=? WHERE id=?", (next_daily(clock, now, days_mask), bid))
        await db.commit()


async def claim_delivery():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("BEGIN IMMEDIATE")
        cur = await db.execute("""SELECT d.id, d.user_id, b.photo, b.caption
            FROM auto_broadcast_deliveries d JOIN auto_broadcasts b ON b.id=d.broadcast_id
            WHERE d.status='pending' AND b.enabled=1 ORDER BY d.id LIMIT 1""")
        row = await cur.fetchone()
        if row:
            await db.execute("UPDATE auto_broadcast_deliveries SET status='sending' WHERE id=?", (row['id'],))
        await db.commit()
        return dict(row) if row else None


async def finish_delivery(delivery_id, status):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE auto_broadcast_deliveries SET status=? WHERE id=?", (status, delivery_id))
        await db.commit()
