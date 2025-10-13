import aiosqlite
from typing import List, Tuple, Optional
from datetime import datetime, timezone, timedelta
from pathlib import Path
import logging
import sqlite3

DB_PATH = Path(__file__).parent / "users.db"


# ---------------------- Ініціалізація ----------------------
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        # Таблиця користувачів
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                has_access INTEGER DEFAULT 0,
                last_active DATETIME DEFAULT (DATETIME('now', '+3 hours'))
            )
        """
        )
        await db.commit()

        # Додаткові колонки подарунків
        await add_gift_columns(db)

        # Таблиця промокодів
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS promocodes (
                code TEXT PRIMARY KEY,
                active INTEGER DEFAULT 1
            )
        """
        )
        await db.commit()

        # Таблиця статистики ігор
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS game_stats (
                game_name TEXT PRIMARY KEY,
                total_games INTEGER DEFAULT 0,
                wins INTEGER DEFAULT 0
            )
        """
        )
        await db.commit()

        # Таблиця слот-сесій
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS slot_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                result TEXT,
                final_balance INTEGER,
                ts DATETIME DEFAULT (DATETIME('now', '+3 hours'))
            )
        """
        )
        await db.commit()


async def add_gift_columns(db: aiosqlite.Connection):
    """Додає колонки gift_claimed та has_claimed_gift, якщо їх немає."""
    async with db.execute("PRAGMA table_info(users)") as cursor:
        columns = [row[1] async for row in cursor]
    if "gift_claimed" not in columns:
        await db.execute("ALTER TABLE users ADD COLUMN gift_claimed INTEGER DEFAULT 0")
    if "has_claimed_gift" not in columns:
        await db.execute(
            "ALTER TABLE users ADD COLUMN has_claimed_gift INTEGER DEFAULT 0"
        )
    await db.commit()


# ---------------------- Користувачі ----------------------
import aiosqlite
from datetime import datetime, timedelta
import logging
from pathlib import Path

DB_PATH = Path(__file__).parent / "users.db"


async def save_user(user_id: int, username: str, full_name: str):
    """
    Зберігає або оновлює користувача у базі з часом по Києву (+3 години).
    """
    try:
        # Поточний час +3 години (Київ)
        kyiv_time = datetime.utcnow() + timedelta(hours=3)
        last_active = kyiv_time.strftime("%Y-%m-%d %H:%M:%S")

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """
                INSERT INTO users (user_id, username, full_name, last_active)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    username=excluded.username,
                    full_name=excluded.full_name,
                    last_active=excluded.last_active
                """,
                (user_id, username, full_name, last_active),
            )
            await db.commit()
    except Exception as e:
        logging.error("Save user error: %s", e)


async def get_all_users() -> List[int]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id FROM users") as cur:
            rows = await cur.fetchall()
            return [r[0] for r in rows]


async def get_all_users_info() -> List[Tuple[int, str, str, str]]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            """
            SELECT user_id, username, full_name, last_active
            FROM users ORDER BY last_active ASC
        """
        ) as cur:
            rows = await cur.fetchall()
            return rows


async def set_user_access(user_id: int, access: bool):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET has_access=? WHERE user_id=?",
            (1 if access else 0, user_id),
        )
        await db.commit()


async def get_user_access(user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT has_access FROM users WHERE user_id=?", (user_id,)
        ) as cur:
            row = await cur.fetchone()
            return bool(row and row[0] == 1)


# ---------------------- Промокоди ----------------------
async def add_promocode(code: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO promocodes (code, active) VALUES (?, 1)", (code,)
        )
        await db.commit()


async def list_promocodes() -> List[str]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT code FROM promocodes WHERE active=1") as cur:
            rows = await cur.fetchall()
            return [r[0] for r in rows]


async def check_promocode(code: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT active FROM promocodes WHERE code=? AND active=1", (code,)
        ) as cur:
            row = await cur.fetchone()
            if row:
                await db.execute("UPDATE promocodes SET active=0 WHERE code=?", (code,))
                await db.commit()
                return True
            return False


# ---------------------- Статистика ігор ----------------------
async def add_game_result(game_name: str, is_win: bool):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO game_stats (game_name, total_games, wins)
            VALUES (?, 1, ?)
            ON CONFLICT(game_name) DO UPDATE SET
                total_games = total_games + 1,
                wins = wins + ?
        """,
            (game_name, 1 if is_win else 0, 1 if is_win else 0),
        )
        await db.commit()


async def get_all_stats() -> List[Tuple[str, int, int]]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT game_name, total_games, wins FROM game_stats"
        ) as cur:
            rows = await cur.fetchall()
            return rows


# ---------------------- Сесії слотів ----------------------
async def add_slot_session(user_id: int, result: str, final_balance: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO slot_sessions (user_id, result, final_balance, ts)
            VALUES (?, ?, ?, DATETIME('now', '+3 hours'))
        """,
            (user_id, result, final_balance),
        )
        await db.commit()


async def get_slot_session_stats() -> Tuple[int, int]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            """
            SELECT COUNT(*), SUM(CASE WHEN result='win' THEN 1 ELSE 0 END)
            FROM slot_sessions
        """
        ) as cur:
            row = await cur.fetchone()
            total = row[0] or 0
            wins = row[1] or 0
            return total, wins


# ---------------------- Очистка статистики ----------------------
async def clear_game_stats():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM game_stats")
        await db.execute("DELETE FROM slot_sessions")
        await db.commit()


# ---------------------- Очистка промокодів ----------------------
async def clear_promocodes():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM promocodes")
        await db.commit()


# ---------------------- Winrate ----------------------
async def get_winrate() -> float:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value REAL
            )
        """
        )
        await db.commit()
        async with db.execute("SELECT value FROM settings WHERE key='winrate'") as cur:
            row = await cur.fetchone()
            return float(row[0]) if row else 0.33


async def set_winrate(value: float):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO settings (key, value)
            VALUES ('winrate', ?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value
        """,
            (value,),
        )
        await db.commit()


# ---------------------- Подарунки ----------------------
import aiosqlite
from pathlib import Path

DB_PATH = Path(__file__).parent / "users.db"


# Перевірка подарунка
async def has_claimed_gift(user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT has_claimed_gift FROM users WHERE user_id=?", (user_id,)
        ) as cur:
            row = await cur.fetchone()
            return bool(row and row[0] == 1)


# Позначаємо, що користувач отримав подарунок
async def set_gift_claimed(user_id: int, claimed: bool):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET has_claimed_gift = ? WHERE user_id = ?",
            (1 if claimed else 0, user_id),
        )
        await db.commit()


# Скидання подарунків для всіх
def reset_all_gifts():
    import sqlite3

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE users SET has_claimed_gift = 0")
    conn.commit()
    conn.close()


# Отримати всіх користувачів
async def get_all_users() -> list[int]:
    import aiosqlite

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id FROM users") as cur:
            rows = await cur.fetchall()
            return [r[0] for r in rows]
