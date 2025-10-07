import aiosqlite
from typing import List, Tuple, Optional

DB_NAME = "users.db"


# ---------------------- Ініціалізація ----------------------
async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        # Таблиця користувачів
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                has_access INTEGER DEFAULT 0,
                last_active DATETIME DEFAULT (DATETIME('now', '+3 hours'))
            )
        """)
        # Додаємо колонку last_active, якщо її ще немає
        try:
            await db.execute("ALTER TABLE users ADD COLUMN last_active DATETIME DEFAULT (DATETIME('now', '+3 hours'))")
        except aiosqlite.OperationalError:
            pass

        # Таблиця промокодів
        await db.execute("""
            CREATE TABLE IF NOT EXISTS promocodes (
                code TEXT PRIMARY KEY,
                active INTEGER DEFAULT 1
            )
        """)

        # Таблиця статистики ігор
        await db.execute("""
            CREATE TABLE IF NOT EXISTS game_stats (
                game_name TEXT PRIMARY KEY,
                total_games INTEGER DEFAULT 0,
                wins INTEGER DEFAULT 0
            )
        """)

        # Таблиця слот-сесій
        await db.execute("""
            CREATE TABLE IF NOT EXISTS slot_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                result TEXT,
                final_balance INTEGER,
                ts DATETIME DEFAULT (DATETIME('now', '+3 hours'))
            )
        """)

        await db.commit()


# ---------------------- Користувачі ----------------------
async def save_user(user_id: int, username: Optional[str], full_name: Optional[str]):
    """Додає нового користувача або оновлює дані з поточним часом по Києву."""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            INSERT INTO users (id, username, full_name, has_access, last_active)
            VALUES (?, ?, ?, 0, DATETIME('now', '+3 hours'))
            ON CONFLICT(id) DO UPDATE SET
                username = excluded.username,
                full_name = excluded.full_name,
                last_active = DATETIME('now', '+3 hours')
        """, (user_id, username or "", full_name or ""))
        await db.commit()


async def get_all_users() -> List[int]:
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT id FROM users") as cur:
            rows = await cur.fetchall()
            return [r[0] for r in rows]


async def get_all_users_info() -> List[Tuple[int, str, str, str]]:
    """Повертає список користувачів (id, username, full_name, last_active)."""
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT id, username, full_name, last_active FROM users ORDER BY last_active ASC"
        ) as cur:
            rows = await cur.fetchall()
            return rows


async def set_user_access(user_id: int, access: bool):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "UPDATE users SET has_access=? WHERE id=?",
            (1 if access else 0, user_id)
        )
        await db.commit()


async def get_user_access(user_id: int) -> bool:
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT has_access FROM users WHERE id=?", (user_id,)) as cur:
            row = await cur.fetchone()
            return bool(row and row[0] == 1)


# ---------------------- Промокоди ----------------------
async def add_promocode(code: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT OR REPLACE INTO promocodes (code, active) VALUES (?, 1)",
            (code,)
        )
        await db.commit()


async def list_promocodes() -> List[str]:
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT code FROM promocodes WHERE active=1") as cur:
            rows = await cur.fetchall()
            return [r[0] for r in rows]


async def check_promocode(code: str) -> bool:
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT active FROM promocodes WHERE code=? AND active=1", (code,)) as cur:
            row = await cur.fetchone()
            if row:
                await db.execute("UPDATE promocodes SET active=0 WHERE code=?", (code,))
                await db.commit()
                return True
            return False


# ---------------------- Статистика ігор ----------------------
async def add_game_result(game_name: str, is_win: bool):
    """Додає результат гри до статистики."""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            INSERT INTO game_stats (game_name, total_games, wins)
            VALUES (?, 1, ?)
            ON CONFLICT(game_name) DO UPDATE SET
                total_games = total_games + 1,
                wins = wins + ?
        """, (game_name, 1 if is_win else 0, 1 if is_win else 0))
        await db.commit()


async def get_all_stats() -> List[Tuple[str, int, int]]:
    """Повертає статистику (гра, загальні ігри, перемоги)."""
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT game_name, total_games, wins FROM game_stats") as cur:
            rows = await cur.fetchall()
            return rows


# ---------------------- Сесії слотів ----------------------
async def add_slot_session(user_id: int, result: str, final_balance: int):
    """Записує результат сесії слотів (з часом по Києву)."""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT INTO slot_sessions (user_id, result, final_balance, ts) VALUES (?, ?, ?, DATETIME('now', '+3 hours'))",
            (user_id, result, final_balance)
        )
        await db.commit()


async def get_slot_session_stats() -> Tuple[int, int]:
    """Повертає (загальна кількість, кількість перемог)."""
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("""
            SELECT COUNT(*), SUM(CASE WHEN result='win' THEN 1 ELSE 0 END)
            FROM slot_sessions
        """) as cur:
            row = await cur.fetchone()
            if not row:
                return (0, 0)
            total = row[0] or 0
            wins = row[1] or 0
            return (total, wins)


# ---------------------- Очистка статистики ----------------------
async def clear_game_stats():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM game_stats")
        await db.execute("DELETE FROM slot_sessions")
        await db.commit()
