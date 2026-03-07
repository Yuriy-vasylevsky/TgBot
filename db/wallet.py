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