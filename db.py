# import sqlite3
# from typing import List, Tuple

# DB_NAME = "users.db"

# def init_db():
#     conn = sqlite3.connect(DB_NAME)
#     c = conn.cursor()

#     # таблиця користувачів
#     c.execute('''CREATE TABLE IF NOT EXISTS users
#                  (id INTEGER PRIMARY KEY,
#                   username TEXT,
#                   full_name TEXT,
#                   has_access INTEGER DEFAULT 0)''')

#     # таблиця промокодів
#     c.execute('''CREATE TABLE IF NOT EXISTS promocodes
#                  (code TEXT PRIMARY KEY,
#                   active INTEGER DEFAULT 1)''')

#     conn.commit()
#     conn.close()


# # ---------------------- Користувачі ----------------------
# def save_user(user_id: int, username: str | None, full_name: str | None):
#     conn = sqlite3.connect(DB_NAME)
#     c = conn.cursor()
#     c.execute(
#         "INSERT OR IGNORE INTO users (id, username, full_name) VALUES (?, ?, ?)",
#         (user_id, username or "", full_name or "")
#     )
#     conn.commit()
#     conn.close()

# def get_all_users() -> List[int]:
#     conn = sqlite3.connect(DB_NAME)
#     c = conn.cursor()
#     c.execute("SELECT id FROM users")
#     users = [row[0] for row in c.fetchall()]
#     conn.close()
#     return users

# def get_all_users_info() -> List[Tuple[int, str, str]]:
#     conn = sqlite3.connect(DB_NAME)
#     c = conn.cursor()
#     c.execute("SELECT id, username, full_name FROM users")
#     users = c.fetchall()
#     conn.close()
#     return users

# def set_user_access(user_id: int, access: bool):
#     conn = sqlite3.connect(DB_NAME)
#     c = conn.cursor()
#     c.execute("UPDATE users SET has_access=? WHERE id=?", (1 if access else 0, user_id))
#     conn.commit()
#     conn.close()

# def get_user_access(user_id: int) -> bool:
#     conn = sqlite3.connect(DB_NAME)
#     c = conn.cursor()
#     c.execute("SELECT has_access FROM users WHERE id=?", (user_id,))
#     row = c.fetchone()
#     conn.close()
#     return bool(row and row[0] == 1)


# # ---------------------- Промокоди ----------------------
# def add_promocode(code: str):
#     conn = sqlite3.connect(DB_NAME)
#     c = conn.cursor()
#     c.execute("INSERT OR REPLACE INTO promocodes (code, active) VALUES (?, 1)", (code,))
#     conn.commit()
#     conn.close()

# def list_promocodes() -> List[str]:
#     conn = sqlite3.connect(DB_NAME)
#     c = conn.cursor()
#     c.execute("SELECT code FROM promocodes WHERE active=1")
#     codes = [row[0] for row in c.fetchall()]
#     conn.close()
#     return codes

# def check_promocode(code: str) -> bool:
#     conn = sqlite3.connect(DB_NAME)
#     c = conn.cursor()
#     c.execute("SELECT active FROM promocodes WHERE code=? AND active=1", (code,))
#     row = c.fetchone()
#     if row:
#         # деактивуємо промокод
#         c.execute("UPDATE promocodes SET active=0 WHERE code=?", (code,))
#         conn.commit()
#         conn.close()
#         return True
#     conn.close()
#     return False


# db.py

# db.py
import aiosqlite
from typing import List, Tuple, Optional

DB_NAME = "users.db"

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                has_access INTEGER DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS promocodes (
                code TEXT PRIMARY KEY,
                active INTEGER DEFAULT 1
            )
        """)
        # Таблиця з агрегованою статистикою по кожній грі
        await db.execute("""
            CREATE TABLE IF NOT EXISTS game_stats (
                game_name TEXT PRIMARY KEY,
                total_games INTEGER DEFAULT 0,
                wins INTEGER DEFAULT 0
            )
        """)
        await db.commit()

# ---------------------- Користувачі ----------------------
async def save_user(user_id: int, username: Optional[str], full_name: Optional[str]):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (id, username, full_name) VALUES (?, ?, ?)",
            (user_id, username or "", full_name or "")
        )
        await db.commit()

async def get_all_users() -> List[int]:
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT id FROM users") as cur:
            rows = await cur.fetchall()
            return [r[0] for r in rows]

async def get_all_users_info() -> List[Tuple[int, str, str]]:
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT id, username, full_name FROM users") as cur:
            rows = await cur.fetchall()
            return rows

async def set_user_access(user_id: int, access: bool):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET has_access=? WHERE id=?", (1 if access else 0, user_id))
        await db.commit()

async def get_user_access(user_id: int) -> bool:
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT has_access FROM users WHERE id=?", (user_id,)) as cur:
            row = await cur.fetchone()
            return bool(row and row[0] == 1)

# ---------------------- Промокоди ----------------------
async def add_promocode(code: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR REPLACE INTO promocodes (code, active) VALUES (?, 1)", (code,))
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

# ---------------------- Статистика ігор (агрегована по кожній грі) ----------------------
async def add_game_result(game_name: str, is_win: bool):
    """Збільшує total_games, та wins якщо is_win."""
    async with aiosqlite.connect(DB_NAME) as db:
        # Спроба вставити рядок, якщо не існує
        await db.execute("""
            INSERT INTO game_stats (game_name, total_games, wins)
            VALUES (?, 1, ?)
            ON CONFLICT(game_name) DO UPDATE SET
                total_games = total_games + 1,
                wins = wins + ?
        """, (game_name, 1 if is_win else 0, 1 if is_win else 0))
        await db.commit()

async def get_all_stats():
    """Повертає список (game_name, total_games, wins)."""
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT game_name, total_games, wins FROM game_stats") as cur:
            rows = await cur.fetchall()
            return rows
