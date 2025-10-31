import aiosqlite
import asyncio
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "users.db"

async def fix_notifications():
    async with aiosqlite.connect(DB_PATH) as db:
        # видаляємо стару таблицю
        await db.execute("DROP TABLE IF EXISTS notifications")
        # створюємо заново з локальним часом
        await db.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username TEXT,
                full_name TEXT,
                type TEXT,
                message TEXT,
                created_at DATETIME DEFAULT (DATETIME('now', 'localtime'))
            )
        """)
        await db.commit()
        print("✅ Таблицю notifications оновлено (тепер localtime)")

asyncio.run(fix_notifications())

