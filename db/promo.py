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
        async with db.execute(
            "SELECT active FROM promocodes WHERE code=? AND active=1", (code,)
        ) as cur:
            row = await cur.fetchone()
            if row:
                await db.execute(
                    "UPDATE promocodes SET active=0 WHERE code=?", (code,)
                )
                await db.commit()
                return True
            return False


async def clear_promocodes():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM promocodes")
        await db.commit()