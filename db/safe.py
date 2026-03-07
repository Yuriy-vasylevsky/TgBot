import aiosqlite
import json

from .core import DB_PATH


async def get_safe_state() -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT value FROM safe_state WHERE key='state'"
        )
        row = await cursor.fetchone()
        return json.loads(row[0]) if row else {"opened": [], "win_cell": 198}


async def save_safe_state(data: dict):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO safe_state (key, value) VALUES ('state', ?)",
            (json.dumps(data),)
        )
        await db.commit()