import aiosqlite
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from db.core import DB_PATH


REFERRAL_BONUS = 50
KYIV_ZONE = ZoneInfo("Europe/Kyiv")


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






async def get_all_referrals() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            SELECT
                r.referrer_id,
                r.referred_id,
                r.was_existing_user,
                r.paid,
                r.bonus_given,
                r.created_at,

                ref.username,
                ref.full_name,

                usr.username,
                usr.full_name

            FROM referrals r
            LEFT JOIN users ref ON ref.user_id = r.referrer_id
            LEFT JOIN users usr ON usr.user_id = r.referred_id
            ORDER BY r.created_at DESC
        """)

        rows = await cur.fetchall()

    return [
        {
            "referrer_id": r[0],
            "referred_id": r[1],
            "was_existing_user": bool(r[2]),
            "paid": bool(r[3]),
            "bonus_given": bool(r[4]),
            "created_at": r[5],

            "referrer_username": r[6],
            "referrer_name": r[7],

            "referred_username": r[8],
            "referred_name": r[9],
        }
        for r in rows
    ]











async def is_referred(referred_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT 1 FROM referrals WHERE referred_id = ?", (referred_id,)
        )
        return await cur.fetchone() is not None


async def award_referral_bonus_in_transaction(
    db: aiosqlite.Connection,
    referred_id: int,
    bonus_amount: int = REFERRAL_BONUS,
) -> int | None:
    """Нараховує одноразовий бонус у вже відкритій транзакції."""
    await db.execute(
        "UPDATE referrals SET paid = 1 "
        "WHERE referred_id = ? AND was_existing_user = 0",
        (referred_id,),
    )
    cursor = await db.execute(
        """
        SELECT referrer_id
        FROM referrals
        WHERE referred_id = ?
          AND paid = 1
          AND bonus_given = 0
          AND was_existing_user = 0
          AND referrer_id != referred_id
        """,
        (referred_id,),
    )
    row = await cursor.fetchone()
    if not row:
        return None

    referrer_id = row[0]
    await db.execute(
        "INSERT OR IGNORE INTO users (user_id, balance) VALUES (?, 0)",
        (referrer_id,),
    )

    cursor = await db.execute(
        """
        SELECT COALESCE(daily_net, 0), last_net_date
        FROM users
        WHERE user_id = ?
        """,
        (referrer_id,),
    )
    daily_net, last_net_date = await cursor.fetchone()
    today = datetime.now(KYIV_ZONE).date()
    today_str = today.isoformat()
    yesterday_str = (today - timedelta(days=1)).isoformat()

    if last_net_date == today_str:
        await db.execute(
            """
            UPDATE users
            SET balance = COALESCE(balance, 0) + ?,
                daily_net = COALESCE(daily_net, 0) + ?
            WHERE user_id = ?
            """,
            (bonus_amount, bonus_amount, referrer_id),
        )
    else:
        yesterday_net = daily_net if last_net_date == yesterday_str else 0
        await db.execute(
            """
            UPDATE users
            SET balance = COALESCE(balance, 0) + ?,
                daily_net = ?,
                yesterday_net = ?,
                cashback_claimed_base = 0,
                promo_claimed_base = 0,
                last_net_date = ?,
                total_losses_all_time =
                    COALESCE(total_losses_all_time, 0) + ?
            WHERE user_id = ?
            """,
            (
                bonus_amount,
                bonus_amount,
                yesterday_net,
                today_str,
                daily_net,
                referrer_id,
            ),
        )

    await db.execute(
        """
        UPDATE referrals
        SET bonus_given = 1
        WHERE referred_id = ? AND bonus_given = 0
        """,
        (referred_id,),
    )
    return referrer_id


async def award_referral_bonus(
    referred_id: int,
    bonus_amount: int = REFERRAL_BONUS,
) -> int | None:
    """Атомарно позначає першу оплату й зараховує бонус рефереру."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("BEGIN IMMEDIATE")
        try:
            referrer_id = await award_referral_bonus_in_transaction(
                db,
                referred_id,
                bonus_amount,
            )
            await db.commit()
            return referrer_id
        except Exception:
            await db.rollback()
            raise


async def mark_referral_paid(referred_id: int) -> int | None:
    """Застаріла назва; атомарно видає реферальний бонус."""
    return await award_referral_bonus(referred_id)
    

# from db import is_referred, add_referral, get_user  # або окрема функція

async def user_exists(user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT 1 FROM users WHERE user_id = ?", (user_id,)
        )
        return await cur.fetchone() is not None
