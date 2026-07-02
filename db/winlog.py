import aiosqlite
from datetime import datetime, timezone, timedelta

from .core import DB_PATH

KYIV_TZ = timezone(timedelta(hours=3))


# ===================== ІНІЦІАЛІЗАЦІЯ =====================

async def ensure_win_log_table():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS win_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                username TEXT,
                full_name TEXT,
                win_type TEXT NOT NULL,     -- 'cashback' | 'promo' | 'game' | 'fortune' | 'group'
                source TEXT,                 -- назва гри / джерела
                amount INTEGER NOT NULL,
                created_at DATETIME DEFAULT (DATETIME('now', '+3 hours'))
            )
        """)
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_win_log_created ON win_log(created_at)"
        )
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_win_log_user ON win_log(user_id)"
        )
        await db.commit()


# ===================== ЗАПИС =====================

async def log_win(
    user_id: int,
    username: str | None,
    full_name: str | None,
    win_type: str,
    source: str,
    amount: int,
):
    """Записує будь-який виграш/нарахування в єдиний лог."""
    if amount <= 0:
        return
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO win_log (user_id, username, full_name, win_type, source, amount)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, username or "—", full_name or "—", win_type, source, amount),
        )
        await db.commit()


# ===================== ЧИТАННЯ =====================

def _target_date(date_offset: int) -> str:
    return (datetime.now(KYIV_TZ).date() - timedelta(days=date_offset)).isoformat()


async def get_win_summary(date_offset: int = 0) -> dict:
    """
    Зведення за день (0 = сьогодні, 1 = вчора).
    Повертає загальну суму + розбивку по типах.
    """
    target = _target_date(date_offset)

    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """
            SELECT win_type, SUM(amount), COUNT(*)
            FROM win_log
            WHERE DATE(created_at) = ?
            GROUP BY win_type
            """,
            (target,),
        )
        rows = await cur.fetchall()

    by_type = {
        r[0]: {"total": r[1], "count": r[2]}
        for r in rows
    }
    total = sum(r[1] for r in rows)

    return {"date": target, "total": total, "by_type": by_type}


async def get_win_log_page(date_offset: int = 0, page: int = 1, per_page: int = 15):
    """Список окремих виграшів за день з пагінацією (нові зверху)."""
    target = _target_date(date_offset)
    offset = (page - 1) * per_page

    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """
            SELECT user_id, username, full_name, win_type, source, amount, created_at
            FROM win_log
            WHERE DATE(created_at) = ?
            ORDER BY id DESC
            LIMIT ? OFFSET ?
            """,
            (target, per_page, offset),
        )
        rows = await cur.fetchall()

        cur = await db.execute(
            "SELECT COUNT(*) FROM win_log WHERE DATE(created_at) = ?",
            (target,),
        )
        total_rows = (await cur.fetchone())[0]

    total_pages = max(1, (total_rows + per_page - 1) // per_page)

    entries = [
        {
            "user_id": r[0], "username": r[1], "full_name": r[2],
            "win_type": r[3], "source": r[4], "amount": r[5], "created_at": r[6],
        }
        for r in rows
    ]
    return entries, total_pages


async def get_top_winners(date_offset: int = 0, limit: int = 10):
    """Топ гравців за сумою виграшу за день."""
    target = _target_date(date_offset)
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """
            SELECT user_id, full_name, username, SUM(amount) as total
            FROM win_log
            WHERE DATE(created_at) = ?
            GROUP BY user_id
            ORDER BY total DESC
            LIMIT ?
            """,
            (target, limit),
        )
        rows = await cur.fetchall()
    return [
        {"user_id": r[0], "full_name": r[1], "username": r[2], "total": r[3]}
        for r in rows
    ]