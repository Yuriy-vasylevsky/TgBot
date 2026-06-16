import aiosqlite
import time
import logging

from .core import DB_PATH


async def add_to_balance(user_id: int, amount_grn: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO users (user_id, balance)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET balance = balance + ?
        """, (user_id, amount_grn, amount_grn))
        await db.commit()


async def get_balance(user_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT balance FROM users WHERE user_id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        return row[0] if row else 0


async def add_pending_payment(
    user_id: int, amount_kop: int, comment: str, mono_account: str = "0"
):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR REPLACE INTO pending_payments 
            (user_id, amount_kop, comment, created_at, mono_account)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, amount_kop, comment, time.time(), mono_account))
        await db.commit()


async def get_pending_payments() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT user_id, amount_kop, comment, mono_account 
            FROM pending_payments
        """)
        rows = await cursor.fetchall()
        return [
            {"user_id": r[0], "amount_kop": r[1], "comment": r[2], "mono_account": r[3]}
            for r in rows
        ]


async def remove_pending_payment(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM pending_payments WHERE user_id = ?", (user_id,))
        await db.commit()


async def mark_tx_used(tx_id: str, user_id: int, amount_kop: int, payment_id: str = None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT OR IGNORE INTO used_monobank_txs 
            (tx_id, user_id, amount_kop, payment_id)
            VALUES (?, ?, ?, ?)
            """,
            (tx_id, user_id, amount_kop, payment_id)
        )
        await db.commit()
    logging.info(f"🔐 TX помечена як використована: tx_id='{tx_id}'")


async def is_tx_used(tx_id: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        result = await db.execute(
            "SELECT 1 FROM used_monobank_txs WHERE tx_id = ?", (tx_id,)
        )
        row = await result.fetchone()
        return row is not None
    

# Історія поповнень через бот 

async def add_payment_log(
    user_id: int,
    username: str | None,
    amount: int,
    comment: str = ""
):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO payment_logs
            (user_id, username, amount, comment)
            VALUES (?, ?, ?, ?)
            """,
            (
                user_id,
                username,
                amount,
                comment
            )
        )
        await db.commit()

async def get_payment_logs(page=1, per_page=20):
    offset = (page - 1) * per_page

    async with aiosqlite.connect(DB_PATH) as db:

        cur = await db.execute(
            """
            SELECT
                user_id,
                username,
                amount,
                comment,
                created_at
            FROM payment_logs
            ORDER BY id DESC
            LIMIT ? OFFSET ?
            """,
            (per_page, offset)
        )

        rows = await cur.fetchall()

        cur = await db.execute(
            "SELECT COUNT(*) FROM payment_logs"
        )

        total = (await cur.fetchone())[0]

    total_pages = max(1, (total + per_page - 1) // per_page)

    return rows, total_pages


async def cleanup_old_payment_logs():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            DELETE FROM payment_logs
            WHERE created_at < DATETIME('now', '+3 hours', '-2 days')
        """)
        await db.commit()

async def get_payment_logs_by_date(date_offset=0, page=1, per_page=10):
    offset = (page - 1) * per_page

    from datetime import datetime, timedelta, timezone

    KYIV_OFFSET = timezone(timedelta(hours=3))
    kyiv_now = datetime.now(KYIV_OFFSET)
    target_date = (kyiv_now - timedelta(days=date_offset)).strftime("%Y-%m-%d")

    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """
            SELECT user_id, username, amount, comment, created_at
            FROM payment_logs
            WHERE DATE(created_at) = ?
            ORDER BY id ASC
            LIMIT ? OFFSET ?
            """,
            (target_date, per_page, offset)
        )
        rows = await cur.fetchall()

        cur = await db.execute(
            """
            SELECT COUNT(*), COALESCE(SUM(amount), 0)
            FROM payment_logs
            WHERE DATE(created_at) = ?
            """,
            (target_date,)
        )
        total, day_total = await cur.fetchone()

    total_pages = max(1, (total + per_page - 1) // per_page)
    return rows, total_pages, day_total

async def log_check_issued(user_id: int, check_type: str, code: str, price: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO issued_checks (user_id, check_type, code, price, issued_at)
            VALUES (?, ?, ?, ?, DATETIME('now'))
            """,
            (user_id, check_type, code, price)
        )
        await db.commit()


async def get_issued_checks_for_user(user_id: int) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """
            SELECT check_type, code, price, issued_at
            FROM issued_checks
            WHERE user_id = ?
              AND issued_at >= DATETIME('now', '-2 days')
            ORDER BY issued_at DESC
            """,
            (user_id,)
        )
        rows = await cur.fetchall()
    return [
        {"check_type": r[0], "code": r[1], "price": r[2], "issued_at": r[3]}
        for r in rows
    ]


async def get_all_balances() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            SELECT u.user_id, u.balance, u.full_name, u.username
            FROM users u
            WHERE u.balance > 0
            ORDER BY u.balance DESC
            """
        )
        rows = await cursor.fetchall()
    return [
        {"user_id": r[0], "balance": r[1], "full_name": r[2], "username": r[3]}
        for r in rows
    ]