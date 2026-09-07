"""Durable reservations around external money operations.

An interrupted/ambiguous operation stays pending for reconciliation: never
automatically refund or repeat a request that the provider may have executed.
"""
import json
from uuid import uuid4
import aiosqlite
from .core import DB_PATH


async def ensure_check_operations(db):
    await db.execute("""CREATE TABLE IF NOT EXISTS check_operations (
        id TEXT PRIMARY KEY, user_id INTEGER NOT NULL,
        kind TEXT NOT NULL, provider TEXT NOT NULL, code TEXT,
        amount INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
        response_json TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        completed_at TEXT
    )""")
    await db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_pending_check_user "
                     "ON check_operations(user_id) WHERE status='pending'")


async def owns_check(user_id: int, code: str, provider: str) -> bool:
    if provider not in {"champion", "matic"} or not code:
        return False
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT 1 FROM issued_checks WHERE user_id=? AND code=? "
            "AND LOWER(check_type) LIKE ?",
            (user_id, code, f"%{provider}%"),
        )
        return await cur.fetchone() is not None


async def reserve_operation(user_id: int, kind: str, provider: str,
                            amount: int = 0, code: str | None = None) -> dict:
    if (kind not in {"purchase", "topup", "close"}
            or provider not in {"champion", "matic"}
            or type(amount) is not int or amount < 0
            or (kind != "close" and amount <= 0)
            or (kind == "close" and amount != 0)):
        return {"ok": False, "reason": "invalid_operation"}
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("BEGIN IMMEDIATE")
        cur = await db.execute(
            "SELECT 1 FROM check_operations WHERE user_id=? AND status='pending'", (user_id,)
        )
        if await cur.fetchone():
            return {"ok": False, "reason": "pending_operation"}
        if kind != "purchase":
            cur = await db.execute(
                "SELECT 1 FROM issued_checks WHERE user_id=? AND code=? "
                "AND LOWER(check_type) LIKE ?", (user_id, code, f"%{provider}%")
            )
            if not await cur.fetchone():
                return {"ok": False, "reason": "not_owner"}
        if amount:
            cur = await db.execute(
                "UPDATE users SET balance=balance-? WHERE user_id=? AND balance>=?",
                (amount, user_id, amount),
            )
            if cur.rowcount != 1:
                return {"ok": False, "reason": "insufficient_funds"}
        operation_id = uuid4().hex
        await db.execute(
            "INSERT INTO check_operations(id,user_id,kind,provider,code,amount) "
            "VALUES (?,?,?,?,?,?)", (operation_id,user_id,kind,provider,code,amount)
        )
        await db.commit()
        return {"ok": True, "id": operation_id}


async def finish_operation(operation_id: str, *, success: bool,
                           response: dict, code: str | None = None,
                           returned_amount: int = 0) -> bool:
    if type(returned_amount) is not int or returned_amount < 0:
        raise ValueError("Invalid returned amount")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("BEGIN IMMEDIATE")
        cur = await db.execute(
            "SELECT user_id,kind,provider,code,amount,status FROM check_operations WHERE id=?",
            (operation_id,),
        )
        row = await cur.fetchone()
        if not row or row[5] != "pending":
            return False
        user_id,kind,provider,original_code,amount,_ = row
        if success and kind == "purchase":
            if not code:
                raise ValueError("Missing purchased code")
            await db.execute(
                "INSERT INTO issued_checks(user_id,check_type,code,price) VALUES (?,?,?,?)",
                (user_id, f"{provider.title()} {amount}", code, amount),
            )
        if success and kind == "close":
            cur = await db.execute(
                "DELETE FROM issued_checks WHERE user_id=? AND code=? "
                "AND LOWER(check_type) LIKE ?", (user_id, original_code, f"%{provider}%")
            )
            if not cur.rowcount:
                raise ValueError("Check ownership changed during closure")
        credit = returned_amount if success and kind == "close" else (amount if not success else 0)
        if credit:
            await db.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (credit,user_id))
        await db.execute(
            "UPDATE check_operations SET status=?,response_json=?,code=COALESCE(?,code),"
            "completed_at=CURRENT_TIMESTAMP WHERE id=?",
            ("completed" if success else "failed",json.dumps(response),code,operation_id),
        )
        await db.commit()
        return True
