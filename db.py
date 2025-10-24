import aiosqlite
from typing import List, Tuple, Optional
from datetime import datetime, timezone, timedelta
from pathlib import Path
import logging
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "users.db"


# ---------------------- Ініціалізація ----------------------


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        # ===================== Таблиця користувачів =====================
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

        # ===================== Додаткові колонки подарунків =====================
        await add_gift_columns(db)

        # ===================== Таблиця промокодів =====================
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS promocodes (
                code TEXT PRIMARY KEY,
                active INTEGER DEFAULT 1
            )
            """
        )
        await db.commit()

        # ===================== Таблиця статистики ігор =====================
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

        # ===================== Таблиця слот-сесій =====================
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

        # ===================== Таблиця кодів казино =====================
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS casino_codes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                casino_type TEXT,
                code TEXT,
                used INTEGER DEFAULT 0
            )
            """
        )
        await db.commit()

        # ===================== Таблиця очікуючих винагород =====================
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS pending_rewards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                code_id INTEGER,
                casino_type TEXT,
                status TEXT DEFAULT 'pending',
                ts DATETIME DEFAULT (DATETIME('now', '+3 hours'))
            )
            """
        )
        await db.commit()

        # ===================== Таблиця заблокованих користувачів =====================
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS banned_users (
                user_id INTEGER PRIMARY KEY,
                reason TEXT,
                banned_by INTEGER,
                ts DATETIME DEFAULT (DATETIME('now', '+3 hours'))
            )
            """
        )
        await db.commit()

        # ===================== Таблиця номерів карт =====================
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS cards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bank_name TEXT,
                card_number TEXT
            )
            """
        )
        await db.commit()

        # Якщо таблиця пуста — додати дефолтні картки
        cursor = await db.execute("SELECT COUNT(*) FROM cards")
        count = (await cursor.fetchone())[0]
        if count == 0:
            await db.executemany(
                "INSERT INTO cards (bank_name, card_number) VALUES (?, ?)",
                [
                    ("Приват", "5457 0825 1854 3470"),
                    ("Ощад", "4790 7299 2105 9994"),
                ],
            )
            await db.commit()

        # ===================== Додаткові колонки профілю =====================
        await add_profile_columns(db)


# _________________________________________________________________________________________________________________


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


# ============ Blackjack Sessions ============

import aiosqlite


# додає сесію Blackjack (по завершенню гри)
async def add_blackjack_session(is_win: bool):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS blackjack_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                is_win INTEGER
            )
            """
        )
        await db.execute(
            "INSERT INTO blackjack_sessions (is_win) VALUES (?)", (1 if is_win else 0,)
        )
        await db.commit()


# повертає статистику по сесіях Blackjack
async def get_blackjack_session_stats():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS blackjack_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                is_win INTEGER
            )
            """
        )
        cursor = await db.execute(
            "SELECT COUNT(*), SUM(is_win) FROM blackjack_sessions"
        )
        total, wins = await cursor.fetchone()
        return (total or 0, wins or 0)


# ---------------------- Очистка статистики ----------------------
async def clear_game_stats():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM game_stats")
        await db.execute("DELETE FROM slot_sessions")
        await db.execute("DELETE FROM blackjack_sessions")
        await db.commit()


# async def clear_game_stats():
#     async with aiosqlite.connect("database.db") as db:
#         # --- Статистика усіх ігор (universal stats table)
#         await db.execute("DELETE FROM game_results")

#         # --- Сесії слотів
#         await db.execute("DELETE FROM slot_sessions")

#         # --- Сесії Blackjack 🃏
#         await db.execute("DELETE FROM blackjack_sessions")

#         await db.commit()


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
# def reset_all_gifts():
#     import sqlite3

#     conn = sqlite3.connect(DB_PATH)
#     c = conn.cursor()
#     c.execute("UPDATE users SET has_claimed_gift = 0")
#     conn.commit()
#     conn.close()

import aiosqlite
from config import DB_PATH


async def reset_all_gifts():
    """Скидає статус отриманих подарунків у всіх користувачів."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, gift_claimed INTEGER DEFAULT 0)"
        )
        await db.execute("UPDATE users SET gift_claimed = 0")
        await db.commit()
    print("✅ Подарунки скинуто для всіх користувачів.")


# Отримати всіх користувачів
async def get_all_users() -> list[int]:
    import aiosqlite

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id FROM users") as cur:
            rows = await cur.fetchall()
            return [r[0] for r in rows]


# ---------------------- Коди казино ----------------------
import aiosqlite
from typing import Optional, Tuple


async def add_casino_code(code: str, casino_type: str) -> None:
    """Додає код у таблицю casino_codes."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO casino_codes (code, casino_type) VALUES (?, ?)",
            (code, casino_type),
        )
        await db.commit()


async def get_free_code(casino_type: str) -> Optional[dict]:
    """
    Повертає словник {"id": int, "code": str} для першого вільного (used=0) коду.
    Якщо немає — None.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT id, code FROM casino_codes WHERE casino_type=? AND used=0 LIMIT 1",
            (casino_type,),
        ) as cur:
            row = await cur.fetchone()
            if row:
                return {"id": row[0], "code": row[1]}
            return None


async def mark_code_used_by_id(code_id: int, user_id: int) -> None:
    """Позначає код як виданий (used=1) і записує кому і коли."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE casino_codes SET used=1, assigned_to=?, assigned_at=DATETIME('now', '+3 hours') WHERE id=?",
            (user_id, code_id),
        )
        await db.commit()


async def mark_code_unused(code_id: int) -> None:
    """Повернути код у pool (use зняти) — якщо адмін відхилив заяву."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE casino_codes SET used=0, assigned_to=NULL, assigned_at=NULL WHERE id=?",
            (code_id,),
        )
        await db.commit()


# ---------------------- Pending rewards ----------------------


async def create_pending_reward(
    user_id: int, code_id: Optional[int], casino_type: str
) -> int:
    """Створює запис pending і повертає id pending."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO pending_rewards (user_id, code_id, casino_type, status) VALUES (?, ?, ?, 'pending')",
            (user_id, code_id, casino_type),
        )
        await db.commit()
        return cur.lastrowid


async def set_pending_status(pending_id: int, status: str) -> None:
    """Оновлює статус pending записи (confirmed / rejected)."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE pending_rewards SET status=? WHERE id=?", (status, pending_id)
        )
        await db.commit()


async def get_pending_by_id(pending_id: int) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT id, user_id, code_id, casino_type, status FROM pending_rewards WHERE id=?",
            (pending_id,),
        ) as cur:
            row = await cur.fetchone()
            if not row:
                return None
            return {
                "id": row[0],
                "user_id": row[1],
                "code_id": row[2],
                "casino_type": row[3],
                "status": row[4],
            }


# ++++++++++++++++++++++++++++++++++++++++++++++++++++++++
import aiosqlite
from pathlib import Path
from typing import Optional

DB_PATH = Path(__file__).parent / "users.db"


async def ensure_ban_table():
    """Гарантує, що таблиця для банів існує"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS banned_users (
                user_id INTEGER PRIMARY KEY,
                reason TEXT,
                banned_by INTEGER,
                banned_at DATETIME DEFAULT (DATETIME('now', '+3 hours'))
            )
        """
        )
        await db.commit()


async def ban_user(
    user_id: int, banned_by: Optional[int] = None, reason: str = "Без причини"
):
    """Додає користувача в бан"""
    await ensure_ban_table()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT OR REPLACE INTO banned_users (user_id, reason, banned_by)
            VALUES (?, ?, ?)
        """,
            (user_id, reason, banned_by),
        )
        await db.commit()


async def unban_user(user_id: int):
    """Знімає бан"""
    await ensure_ban_table()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM banned_users WHERE user_id = ?", (user_id,))
        await db.commit()


async def get_all_banned():
    """Отримати всіх заблокованих користувачів"""
    await ensure_ban_table()
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT user_id, reason, banned_at FROM banned_users")
        rows = await cursor.fetchall()
        return rows


# ___________________________________________________ОСОБИСТИЙ КАБІНЕТ_________________________________________________________________
# ==========================
# Кабінет користувача
# ==========================


async def add_or_update_user(user_id: int, username: str, full_name: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO users (user_id, username, full_name, last_active)
            VALUES (?, ?, ?, DATETIME('now', '+3 hours'))
            ON CONFLICT(user_id) DO UPDATE SET
                username=excluded.username,
                full_name=excluded.full_name,
                last_active=excluded.last_active
            """,
            (user_id, username, full_name),
        )
        await db.commit()


async def get_user_data(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT username, full_name, games_played FROM users WHERE user_id = ?",
            (user_id,),
        )
        row = await cursor.fetchone()
        await cursor.close()
        if not row:
            return None
        return {"username": row[0], "full_name": row[1], "games_played": row[2]}


async def increment_games_played(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET games_played = games_played + 1 WHERE user_id = ?",
            (user_id,),
        )
        await db.commit()


async def add_profile_columns(db):
    """Додає нові колонки для профілю, якщо їх ще нема"""
    columns_to_add = {"games_played": "INTEGER DEFAULT 0"}

    async with db.execute("PRAGMA table_info(users)") as cursor:
        existing_cols = [row[1] for row in await cursor.fetchall()]

    for col, definition in columns_to_add.items():
        if col not in existing_cols:
            await db.execute(f"ALTER TABLE users ADD COLUMN {col} {definition}")
            print(f"✅ Додано колонку {col} до таблиці users")

    await db.commit()


async def increment_games_played(user_id: int):
    """Збільшує лічильник зіграних ігор у профілі"""
    async with aiosqlite.connect(DB_PATH) as db:
        # перевіримо, чи є користувач у таблиці
        await db.execute(
            """
            INSERT OR IGNORE INTO users (user_id)
            VALUES (?)
            """,
            (user_id,),
        )
        # збільшуємо games_played
        await db.execute(
            """
            UPDATE users
            SET games_played = games_played + 1
            WHERE user_id = ?
            """,
            (user_id,),
        )
        await db.commit()


async def reset_all_game_stats():
    """Скидає статистику зіграних ігор для всіх користувачів."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET games_played = 0")
        await db.commit()
    print("✅ Статистика ігор успішно очищена!")


# ______________________________________________ НОмера карт _______________________________
async def get_cards():
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT bank_name, card_number FROM cards")
        return await cursor.fetchall()


async def update_card(bank_name: str, new_number: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE cards SET card_number = ? WHERE bank_name = ?",
            (new_number, bank_name),
        )
        await db.commit()


# _____________________________________Очистка зіграних ігор _______________________________
