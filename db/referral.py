import aiosqlite
from db.core import DB_PATH


async def create_referral_tables():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS referrals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                referrer_id INTEGER NOT NULL,
                referred_id INTEGER NOT NULL UNIQUE,
                was_existing_user INTEGER DEFAULT 0,
                paid INTEGER DEFAULT 0,
                bonus_given INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT (DATETIME('now'))
            )
        """)
        await db.commit()


async def add_referral(referrer_id: int, referred_id: int, was_existing_user: bool = False):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT OR IGNORE INTO referrals (referrer_id, referred_id, was_existing_user)
            VALUES (?, ?, ?)
            """,
            (referrer_id, referred_id, 1 if was_existing_user else 0)
        )
        await db.commit()


async def get_referrals(referrer_id: int) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """
            SELECT r.referred_id, u.username, u.full_name,
                   r.was_existing_user, r.paid, r.bonus_given, r.created_at
            FROM referrals r
            LEFT JOIN users u ON u.user_id = r.referred_id
            WHERE r.referrer_id = ?
            ORDER BY r.created_at DESC
            """,
            (referrer_id,)
        )
        rows = await cur.fetchall()
    return [
        {
            "referred_id": r[0],
            "username": r[1],
            "full_name": r[2],
            "was_existing_user": bool(r[3]),
            "paid": bool(r[4]),
            "bonus_given": bool(r[5]),
            "created_at": r[6],
        }
        for r in rows
    ]


async def is_referred(referred_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT 1 FROM referrals WHERE referred_id = ?", (referred_id,)
        )
        return await cur.fetchone() is not None


async def mark_referral_paid(referred_id: int) -> int | None:
    """Позначає реферала як оплаченого, повертає referrer_id якщо бонус ще не давали"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE referrals SET paid = 1 WHERE referred_id = ? AND was_existing_user = 0",
            (referred_id,)
        )
        await db.commit()

        cur = await db.execute(
            """
            SELECT referrer_id FROM referrals
            WHERE referred_id = ? AND paid = 1 AND bonus_given = 0
              AND was_existing_user = 0
            """,
            (referred_id,)
        )
        row = await cur.fetchone()
        if not row:
            return None

        referrer_id = row[0]
        await db.execute(
            "UPDATE referrals SET bonus_given = 1 WHERE referred_id = ?",
            (referred_id,)
        )
        await db.commit()
        return referrer_id
    

# from db import is_referred, add_referral, get_user  # або окрема функція

async def user_exists(user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT 1 FROM users WHERE user_id = ?", (user_id,)
        )
        return await cur.fetchone() is not None