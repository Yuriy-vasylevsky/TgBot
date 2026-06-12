import aiosqlite
from .core import DB_PATH


async def add_check_code(table: str, code: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            f"INSERT OR IGNORE INTO {table} (code) VALUES (?)",
            (code,)
        )
        await db.commit()

import aiosqlite
from .core import DB_PATH


async def delete_check_code(table: str, code: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            f"DELETE FROM {table} WHERE code = ?",
            (code,)
        )
        await db.commit()


import aiosqlite
from .core import DB_PATH


async def get_checks_stats():
    tables = {
        "🏆 Чек 100 Champion": "champion_checks_100",
        "🏆 Чек 200 Champion": "champion_checks_200",
        "🎰 Чек 100 Matic": "matic_checks_100",
        "🎰 Чек 200 Matic": "matic_checks_200",
    }

    result = {}

    async with aiosqlite.connect(DB_PATH) as db:
        for name, table in tables.items():
            async with db.execute(f"SELECT COUNT(*) FROM {table}") as cur:
                count = await cur.fetchone()
                result[name] = count[0]

    return result


import aiosqlite
from .core import DB_PATH


async def clear_all_checks():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM champion_checks_100")
        await db.execute("DELETE FROM champion_checks_200")
        await db.execute("DELETE FROM matic_checks_100")
        await db.execute("DELETE FROM matic_checks_200")
        await db.commit()



import aiosqlite
from .core import DB_PATH


async def get_checks_count():
    async with aiosqlite.connect(DB_PATH) as db:
        result = {}

        tables = {
            "champion_100": "champion_checks_100",
            "champion_200": "champion_checks_200",
            "matic_100": "matic_checks_100",
            "matic_200": "matic_checks_200",
        }

        for name, table in tables.items():
            async with db.execute(f"SELECT COUNT(*) FROM {table}") as cur:
                row = await cur.fetchone()
                result[name] = row[0] if row else 0

        return result


async def get_free_check(table: str):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            f"SELECT code FROM {table} LIMIT 1"
        ) as cur:
            row = await cur.fetchone()
            return row[0] if row else None


async def remove_check(table: str, code: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            f"DELETE FROM {table} WHERE code=?",
            (code,)
        )
        await db.commit()