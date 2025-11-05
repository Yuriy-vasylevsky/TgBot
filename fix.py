import asyncio
import aiosqlite
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "users.db"

async def main():
    async with aiosqlite.connect(DB_PATH) as db:
        # перевіряємо чи вже є така колонка
        cur = await db.execute("PRAGMA table_info(users)")
        cols = [row[1] for row in await cur.fetchall()]

        if "money_won" not in cols:
            print("🔧 Додаю колонку money_won...")
            await db.execute("ALTER TABLE users ADD COLUMN money_won INTEGER DEFAULT 0;")
            await db.commit()
            print("✅ Готово! колонка money_won створена.")
        else:
            print("ℹ️ Колонка money_won вже існує — нічого робити не треба.")

asyncio.run(main())
