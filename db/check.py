import aiosqlite
from .core import DB_PATH


async def get_issued_checks_with_owners(platform=None):
    """All bot-issued checks for the selected platform, with their owners."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT DISTINCT c.user_id, c.code, "
            "'Matic' AS platform, u.full_name, u.username "
            "FROM issued_checks c LEFT JOIN users u ON u.user_id = c.user_id "
            "WHERE (? IS NULL OR ?='Matic') "
            "AND (LOWER(c.check_type) LIKE '%matic%' "
            "OR LOWER(c.check_type) LIKE '%superomatic%') "
            "ORDER BY c.id DESC", (platform, platform)
        ) as cursor:
            return [dict(row) for row in await cursor.fetchall()]


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


async def get_checks_total_balance():
    stats = await get_checks_stats()

    total = (
        stats.get("🏆 Чек 100 Champion", 0) * 100 +
        stats.get("🏆 Чек 200 Champion", 0) * 200 +
        stats.get("🎰 Чек 100 Matic", 0) * 100 +
        stats.get("🎰 Чек 200 Matic", 0) * 200
    )

    return total
