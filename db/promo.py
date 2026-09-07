import aiosqlite
from typing import List

from .core import DB_PATH


async def add_promocode(code: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO promocodes (code, active) VALUES (?, 1)",
            (code,)
        )
        await db.commit()


async def list_promocodes() -> List[str]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT code FROM promocodes WHERE active=1"
        ) as cur:
            rows = await cur.fetchall()
            return [r[0] for r in rows]


async def check_promocode(code: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "UPDATE promocodes SET active=0 WHERE code=? AND active=1", (code,)
        )
        await db.commit()
        return cur.rowcount == 1


async def redeem_promocode(user_id: int, code: str) -> bool:
    """Consume the code and grant access together, including across restarts."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "UPDATE promocodes SET active=0 WHERE code=? AND active=1", (code,)
        )
        if cur.rowcount != 1:
            return False
        await db.execute(
            "INSERT INTO users (user_id, has_access, games_played) VALUES (?, 1, 1) "
            "ON CONFLICT(user_id) DO UPDATE SET has_access=1, "
            "games_played=COALESCE(games_played, 0)+1", (user_id,)
        )
        await db.commit()
        return True


async def claim_gift(user_id: int, code: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "UPDATE users SET has_claimed_gift=1 WHERE user_id=? "
            "AND COALESCE(has_claimed_gift, 0)=0", (user_id,)
        )
        if cur.rowcount != 1:
            return False
        await db.execute("INSERT INTO promocodes(code, active) VALUES (?, 1)", (code,))
        await db.commit()
        return True


async def clear_promocodes():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM promocodes")
        await db.commit()
