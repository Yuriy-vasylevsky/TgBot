

import os
from pathlib import Path
import logging
from typing import List, Tuple, Optional
from datetime import datetime, timezone, timedelta
import json

import aiosqlite

# ==================== ЄДИНИЙ DB_PATH ====================
DATA_DIR = os.environ.get("DATA_DIR", "/data")
DB_PATH = Path(DATA_DIR) / "users.db"

print(f"💾 Final DB path: {DB_PATH}")
print(f"📍 File exists: {DB_PATH.exists()}, size: {DB_PATH.stat().st_size if DB_PATH.exists() else 0} bytes")

logging.basicConfig(level=logging.INFO)

# ===================== ІНІЦІАЛІЗАЦІЯ БД =====================
# async def init_db():
#     print("🔧 init_db() started...")
#     try:
#         async with aiosqlite.connect(DB_PATH) as db:
#             # Таблиця users
#             await db.execute("""
#                 CREATE TABLE IF NOT EXISTS users (
#                     user_id INTEGER PRIMARY KEY,
#                     username TEXT,
#                     full_name TEXT,
#                     has_access INTEGER DEFAULT 0,
#                     last_active DATETIME DEFAULT (DATETIME('now', '+3 hours')),
#                     last_actions TEXT DEFAULT '',
#                     games_played INTEGER DEFAULT 0,
#                     games_won INTEGER DEFAULT 0,
#                     money_won INTEGER DEFAULT 0,
#                     gift_claimed INTEGER DEFAULT 0,
#                     has_claimed_gift INTEGER DEFAULT 0
#                 )
#             """)
#             await db.commit()

#             await add_gift_columns(db)
#             await add_profile_columns(db)
#             await add_user_column_last_actions()
#             # await add_user_column_last_actions(db)

#             # Інші таблиці
#             await db.execute("CREATE TABLE IF NOT EXISTS promocodes (code TEXT PRIMARY KEY, active INTEGER DEFAULT 1)")
#             await db.execute("CREATE TABLE IF NOT EXISTS game_stats (game_name TEXT PRIMARY KEY, total_games INTEGER DEFAULT 0, wins INTEGER DEFAULT 0)")
#             await db.execute("CREATE TABLE IF NOT EXISTS slot_sessions (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, result TEXT, final_balance INTEGER, ts DATETIME DEFAULT (DATETIME('now', '+3 hours')))")
#             await db.execute("CREATE TABLE IF NOT EXISTS casino_codes (id INTEGER PRIMARY KEY AUTOINCREMENT, casino_type TEXT, code TEXT, used INTEGER DEFAULT 0, assigned_to INTEGER, assigned_at DATETIME)")
#             await db.execute("CREATE TABLE IF NOT EXISTS pending_rewards (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, code_id INTEGER, casino_type TEXT, status TEXT DEFAULT 'pending', ts DATETIME DEFAULT (DATETIME('now', '+3 hours')))")
#             await db.execute("CREATE TABLE IF NOT EXISTS banned_users (user_id INTEGER PRIMARY KEY, reason TEXT, banned_by INTEGER, ts DATETIME DEFAULT (DATETIME('now', '+3 hours')))")
#             await db.execute("CREATE TABLE IF NOT EXISTS cards (id INTEGER PRIMARY KEY AUTOINCREMENT, bank_name TEXT, card_number TEXT)")
#             await db.execute("CREATE TABLE IF NOT EXISTS weekly_tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, description TEXT, reward TEXT, duration TEXT, is_active INTEGER DEFAULT 1, created_at DATETIME DEFAULT (DATETIME('now', '+3 hours')))")
#             await db.execute("CREATE TABLE IF NOT EXISTS user_tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, task_id INTEGER NOT NULL, is_completed INTEGER DEFAULT 0, completed_at DATETIME, FOREIGN KEY (task_id) REFERENCES weekly_tasks (id))")
#             await db.execute("CREATE TABLE IF NOT EXISTS safe_state (key TEXT PRIMARY KEY, value TEXT)")
#             await db.execute("CREATE TABLE IF NOT EXISTS notifications (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, username TEXT, full_name TEXT, type TEXT, message TEXT, created_at DATETIME DEFAULT (DATETIME('now', '+3 hours')))")
#             await db.execute("CREATE TABLE IF NOT EXISTS broadcast_templates (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, text TEXT)")
#             await db.execute("CREATE TABLE IF NOT EXISTS blackjack_sessions (id INTEGER PRIMARY KEY AUTOINCREMENT, is_win INTEGER)")
#             await db.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value REAL)")

#             # Дефолтні картки
#             cursor = await db.execute("SELECT COUNT(*) FROM cards")
#             if (await cursor.fetchone())[0] == 0:
#                 await db.executemany(
#                     "INSERT INTO cards (bank_name, card_number) VALUES (?, ?)",
#                     [("Приват", "5457 0825 1854 3470"), ("Ощад", "4790 7299 2105 9994")]
#                 )
#                 await db.commit()
#                 print("✅ Default cards added")

#             print("🎉 init_db() finished successfully!")
#             await db.commit()

#     except Exception as e:
#         print(f"❌ CRITICAL ERROR in init_db: {e}")
#         import traceback
#         traceback.print_exc()

# ===================== ІНІЦІАЛІЗАЦІЯ БД =====================
async def ensure_users_table_and_columns():
    """ОДНА функція, яка створює таблицю + ВСІ колонки (включаючи daily_bonus і fortune)"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                has_access INTEGER DEFAULT 0,
                last_active DATETIME DEFAULT (DATETIME('now', '+3 hours')),
                last_actions TEXT DEFAULT '',
                games_played INTEGER DEFAULT 0,
                games_won INTEGER DEFAULT 0,
                money_won INTEGER DEFAULT 0,
                gift_claimed INTEGER DEFAULT 0,
                has_claimed_gift INTEGER DEFAULT 0,
                last_daily_bonus_date TEXT,
                last_fortune_date TEXT
            )
        """)

        # Перевіряємо і додаємо колонки, якщо їх немає
        async with db.execute("PRAGMA table_info(users)") as cursor:
            columns = {row[1] for row in await cursor.fetchall()}

        if "last_daily_bonus_date" not in columns:
            await db.execute("ALTER TABLE users ADD COLUMN last_daily_bonus_date TEXT")
            print("✅ Додано колонку: last_daily_bonus_date")

        if "last_fortune_date" not in columns:
            await db.execute("ALTER TABLE users ADD COLUMN last_fortune_date TEXT")
            print("✅ Додано колонку: last_fortune_date")

        await db.commit()


async def init_db():
    print("🔧 init_db() запущено...")
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            # Головна таблиця з усіма колонками
            await ensure_users_table_and_columns()

            # Інші таблиці (залишаються без змін)
            await db.execute("CREATE TABLE IF NOT EXISTS promocodes (code TEXT PRIMARY KEY, active INTEGER DEFAULT 1)")
            await db.execute("CREATE TABLE IF NOT EXISTS game_stats (game_name TEXT PRIMARY KEY, total_games INTEGER DEFAULT 0, wins INTEGER DEFAULT 0)")
            await db.execute("CREATE TABLE IF NOT EXISTS slot_sessions (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, result TEXT, final_balance INTEGER, ts DATETIME DEFAULT (DATETIME('now', '+3 hours')))")
            await db.execute("CREATE TABLE IF NOT EXISTS casino_codes (id INTEGER PRIMARY KEY AUTOINCREMENT, casino_type TEXT, code TEXT, used INTEGER DEFAULT 0, assigned_to INTEGER, assigned_at DATETIME)")
            await db.execute("CREATE TABLE IF NOT EXISTS pending_rewards (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, code_id INTEGER, casino_type TEXT, status TEXT DEFAULT 'pending', ts DATETIME DEFAULT (DATETIME('now', '+3 hours')))")
            await db.execute("CREATE TABLE IF NOT EXISTS banned_users (user_id INTEGER PRIMARY KEY, reason TEXT, banned_by INTEGER, ts DATETIME DEFAULT (DATETIME('now', '+3 hours')))")
            await db.execute("CREATE TABLE IF NOT EXISTS cards (id INTEGER PRIMARY KEY AUTOINCREMENT, bank_name TEXT, card_number TEXT)")
            await db.execute("CREATE TABLE IF NOT EXISTS weekly_tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, description TEXT, reward TEXT, duration TEXT, is_active INTEGER DEFAULT 1, created_at DATETIME DEFAULT (DATETIME('now', '+3 hours')))")
            await db.execute("CREATE TABLE IF NOT EXISTS user_tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, task_id INTEGER NOT NULL, is_completed INTEGER DEFAULT 0, completed_at DATETIME, FOREIGN KEY (task_id) REFERENCES weekly_tasks (id))")
            await db.execute("CREATE TABLE IF NOT EXISTS safe_state (key TEXT PRIMARY KEY, value TEXT)")
            await db.execute("CREATE TABLE IF NOT EXISTS notifications (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, username TEXT, full_name TEXT, type TEXT, message TEXT, created_at DATETIME DEFAULT (DATETIME('now', '+3 hours')))")
            await db.execute("CREATE TABLE IF NOT EXISTS broadcast_templates (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, text TEXT)")
            await db.execute("CREATE TABLE IF NOT EXISTS blackjack_sessions (id INTEGER PRIMARY KEY AUTOINCREMENT, is_win INTEGER)")
            await db.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value REAL)")

            # Дефолтні картки
            cursor = await db.execute("SELECT COUNT(*) FROM cards")
            if (await cursor.fetchone())[0] == 0:
                await db.executemany(
                    "INSERT INTO cards (bank_name, card_number) VALUES (?, ?)",
                    [("Приват", "5457 0825 1854 3470"), ("Ощад", "4790 7299 2105 9994")]
                )
                await db.commit()
                print("✅ Default cards added")

            print("🎉 init_db() завершено успішно!")
            await db.commit()

    except Exception as e:
        print(f"❌ CRITICAL ERROR in init_db: {e}")
        import traceback
        traceback.print_exc()


async def add_gift_columns(db: aiosqlite.Connection):
    async with db.execute("PRAGMA table_info(users)") as cursor:
        columns = [row[1] async for row in cursor]
    if "gift_claimed" not in columns:
        await db.execute("ALTER TABLE users ADD COLUMN gift_claimed INTEGER DEFAULT 0")
    if "has_claimed_gift" not in columns:
        await db.execute("ALTER TABLE users ADD COLUMN has_claimed_gift INTEGER DEFAULT 0")
    await db.commit()


async def add_profile_columns(db: aiosqlite.Connection):
    columns_to_add = {"games_played": "INTEGER DEFAULT 0"}
    async with db.execute("PRAGMA table_info(users)") as cursor:
        existing_cols = [row[1] for row in await cursor.fetchall()]
    for col, definition in columns_to_add.items():
        if col not in existing_cols:
            await db.execute(f"ALTER TABLE users ADD COLUMN {col} {definition}")
            print(f"✅ Додано колонку {col}")
    await db.commit()


async def add_user_column_last_actions():
    """Додає колонку last_actions у таблицю users, якщо її ще немає."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("PRAGMA table_info(users)") as cursor:
            columns = [row[1] for row in await cursor.fetchall()]
        if "last_actions" not in columns:
            await db.execute("ALTER TABLE users ADD COLUMN last_actions TEXT DEFAULT ''")
            await db.commit()
            print("✅ Колонку last_actions додано!")
        else:
            print("ℹ️ Колонка last_actions уже існує.")


# ===================== ВСІ ТВОЇ ФУНКЦІЇ =====================

async def save_user(user_id: int, username: str, full_name: str, action: str = None):
    kyiv_tz = timezone(timedelta(hours=3))
    now_str = datetime.now(kyiv_tz).isoformat(timespec="seconds")

    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT last_actions FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        old_actions = row[0] if row and row[0] else ""
        await cursor.close()

        if action:
            parts = old_actions.split(" | ") if old_actions else []
            parts = (parts + [action])[-5:]
            new_actions = " | ".join(parts)
        else:
            new_actions = old_actions

        await db.execute(
            """
            INSERT INTO users (user_id, username, full_name, last_active, last_actions)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username = excluded.username,
                full_name = excluded.full_name,
                last_active = excluded.last_active,
                last_actions = excluded.last_actions
            """,
            (user_id, username, full_name, now_str, new_actions)
        )
        await db.commit()


async def get_all_users() -> List[int]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id FROM users") as cur:
            rows = await cur.fetchall()
            return [r[0] for r in rows]


async def get_all_users_info():
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT user_id, full_name, username, last_active, last_actions, games_played, games_won FROM users")
        rows = await cur.fetchall()
    return [
        {
            "user_id": r[0], "full_name": r[1], "username": r[2],
            "last_active": r[3], "last_actions": r[4],
            "games_played": r[5], "games_won": r[6]
        } for r in rows
    ]


async def reset_all_game_stats():
    """Скидає статистику зіграних та виграних ігор для всіх користувачів."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET games_played = 0, games_won = 0")
        await db.commit()
    print("✅ Статистика ігор успішно очищена (played + won)!")


async def set_user_access(user_id: int, access: bool):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET has_access=? WHERE user_id=?", (1 if access else 0, user_id))
        await db.commit()


async def get_user_access(user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT has_access FROM users WHERE user_id=?", (user_id,)) as cur:
            row = await cur.fetchone()
            return bool(row and row[0] == 1)


async def add_promocode(code: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR REPLACE INTO promocodes (code, active) VALUES (?, 1)", (code,))
        await db.commit()


async def list_promocodes() -> List[str]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT code FROM promocodes WHERE active=1") as cur:
            rows = await cur.fetchall()
            return [r[0] for r in rows]


async def check_promocode(code: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT active FROM promocodes WHERE code=? AND active=1", (code,)) as cur:
            row = await cur.fetchone()
            if row:
                await db.execute("UPDATE promocodes SET active=0 WHERE code=?", (code,))
                await db.commit()
                return True
            return False


async def add_game_result(game_name: str, is_win: bool):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO game_stats (game_name, total_games, wins) VALUES (?, 1, ?) ON CONFLICT(game_name) DO UPDATE SET total_games = total_games + 1, wins = wins + ?",
            (game_name, 1 if is_win else 0, 1 if is_win else 0)
        )
        await db.commit()


async def get_all_stats() -> List[Tuple[str, int, int]]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT game_name, total_games, wins FROM game_stats") as cur:
            return await cur.fetchall()


async def add_slot_session(user_id: int, result: str, final_balance: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO slot_sessions (user_id, result, final_balance, ts) VALUES (?, ?, ?, DATETIME('now', '+3 hours'))",
            (user_id, result, final_balance)
        )
        await db.commit()


async def get_slot_session_stats() -> Tuple[int, int]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*), SUM(CASE WHEN result='win' THEN 1 ELSE 0 END) FROM slot_sessions") as cur:
            row = await cur.fetchone()
            return (row[0] or 0, row[1] or 0)


async def add_blackjack_session(is_win: bool):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("CREATE TABLE IF NOT EXISTS blackjack_sessions (id INTEGER PRIMARY KEY AUTOINCREMENT, is_win INTEGER)")
        await db.execute("INSERT INTO blackjack_sessions (is_win) VALUES (?)", (1 if is_win else 0,))
        await db.commit()


async def get_blackjack_session_stats():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("CREATE TABLE IF NOT EXISTS blackjack_sessions (id INTEGER PRIMARY KEY AUTOINCREMENT, is_win INTEGER)")
        cursor = await db.execute("SELECT COUNT(*), SUM(is_win) FROM blackjack_sessions")
        total, wins = await cursor.fetchone()
        return (total or 0, wins or 0)


async def clear_game_stats():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM game_stats")
        await db.execute("DELETE FROM slot_sessions")
        await db.execute("DELETE FROM blackjack_sessions")
        await db.execute("UPDATE users SET money_won = 0")
        await db.commit()


async def clear_promocodes():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM promocodes")
        await db.commit()


async def get_winrate() -> float:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value REAL)")
        async with db.execute("SELECT value FROM settings WHERE key='winrate'") as cur:
            row = await cur.fetchone()
            return float(row[0]) if row else 0.33


async def set_winrate(value: float):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO settings (key, value) VALUES ('winrate', ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (value,))
        await db.commit()


async def has_claimed_gift(user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT has_claimed_gift FROM users WHERE user_id=?", (user_id,)) as cur:
            row = await cur.fetchone()
            return bool(row and row[0] == 1)


async def set_gift_claimed(user_id: int, claimed: bool):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET has_claimed_gift = ? WHERE user_id = ?", (1 if claimed else 0, user_id))
        await db.commit()


async def reset_all_gifts():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET has_claimed_gift = 0")
        await db.commit()
    print("✅ Подарунки скинуто для всіх користувачів.")


async def add_casino_code(code: str, casino_type: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO casino_codes (code, casino_type) VALUES (?, ?)", (code, casino_type))
        await db.commit()


async def get_free_code(casino_type: str) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id, code FROM casino_codes WHERE casino_type=? AND used=0 LIMIT 1", (casino_type,)) as cur:
            row = await cur.fetchone()
            return {"id": row[0], "code": row[1]} if row else None


async def mark_code_used_by_id(code_id: int, user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE casino_codes SET used=1, assigned_to=?, assigned_at=DATETIME('now', '+3 hours') WHERE id=?", (user_id, code_id))
        await db.commit()


async def mark_code_unused(code_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE casino_codes SET used=0, assigned_to=NULL, assigned_at=NULL WHERE id=?", (code_id,))
        await db.commit()


async def create_pending_reward(user_id: int, code_id: Optional[int], casino_type: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("INSERT INTO pending_rewards (user_id, code_id, casino_type, status) VALUES (?, ?, ?, 'pending')", (user_id, code_id, casino_type))
        await db.commit()
        return cur.lastrowid


async def set_pending_status(pending_id: int, status: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE pending_rewards SET status=? WHERE id=?", (status, pending_id))
        await db.commit()


async def get_pending_by_id(pending_id: int) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id, user_id, code_id, casino_type, status FROM pending_rewards WHERE id=?", (pending_id,)) as cur:
            row = await cur.fetchone()
            return {"id": row[0], "user_id": row[1], "code_id": row[2], "casino_type": row[3], "status": row[4]} if row else None


async def ensure_ban_table():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("CREATE TABLE IF NOT EXISTS banned_users (user_id INTEGER PRIMARY KEY, reason TEXT, banned_by INTEGER, ts DATETIME DEFAULT (DATETIME('now', '+3 hours')))")
        await db.commit()


async def ban_user(user_id: int, banned_by: Optional[int] = None, reason: str = "Без причини"):
    await ensure_ban_table()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR REPLACE INTO banned_users (user_id, reason, banned_by) VALUES (?, ?, ?)", (user_id, reason, banned_by))
        await db.commit()


async def unban_user(user_id: int):
    await ensure_ban_table()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM banned_users WHERE user_id = ?", (user_id,))
        await db.commit()


async def get_all_banned():
    await ensure_ban_table()
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT user_id, reason, ts FROM banned_users")
        return await cursor.fetchall()


async def add_or_update_user(user_id: int, username: str, full_name: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO users (user_id, username, full_name, last_active) VALUES (?, ?, ?, DATETIME('now')) ON CONFLICT(user_id) DO UPDATE SET username=excluded.username, full_name=excluded.full_name, last_active=excluded.last_active",
            (user_id, username, full_name)
        )
        await db.commit()


async def get_user_data(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT username, full_name, games_played, games_won FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        return {"username": row[0], "full_name": row[1], "games_played": row[2], "games_won": row[3]} if row else None


async def increment_games_played(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
        await db.execute("UPDATE users SET games_played = games_played + 1 WHERE user_id = ?", (user_id,))
        await db.commit()


async def get_cards():
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT bank_name, card_number FROM cards")
        return await cursor.fetchall()


async def update_card(bank_name: str, new_number: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE cards SET card_number = ? WHERE bank_name = ?", (new_number, bank_name))
        await db.commit()


async def add_last_action(user_id: int, action: str):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT last_actions FROM users WHERE user_id = ?", (user_id,))
        row = await cur.fetchone()
        old_actions = row[0].split(" | ") if row and row[0] else []
        old_actions.insert(0, action.strip())
        old_actions = old_actions[:2]
        actions_str = " | ".join(old_actions)
        await db.execute("UPDATE users SET last_actions = ? WHERE user_id = ?", (actions_str, user_id))
        await db.commit()


async def add_weekly_task(title: str, description: str, reward: str, duration: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("CREATE TABLE IF NOT EXISTS weekly_tasks (...)")  # вже є в init_db
        await db.execute("CREATE TABLE IF NOT EXISTS user_tasks (...)")
        await db.execute("INSERT INTO weekly_tasks (title, description, reward, duration) VALUES (?, ?, ?, ?)", (title, description, reward, duration))
        await db.commit()


async def get_active_tasks():
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT id, title, description, reward, duration FROM weekly_tasks WHERE is_active = 1")
        rows = await cursor.fetchall()
        return [{"id": r[0], "title": r[1], "description": r[2], "reward": r[3], "duration": r[4]} for r in rows]


async def get_user_task_progress(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT t.id, t.title, t.description, t.reward, COALESCE(t.duration, '') as duration, ut.is_completed FROM weekly_tasks t LEFT JOIN user_tasks ut ON t.id = ut.task_id AND ut.user_id = ? WHERE t.is_active = 1",
            (user_id,)
        )
        rows = await cursor.fetchall()
        return [{"id": r[0], "title": r[1], "description": r[2], "reward": r[3], "duration": r[4], "is_completed": bool(r[5])} for r in rows]


async def save_notification(user_id: int, username: str, full_name: str, type_: str, message: str):
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            username_display = f"@{username}" if username and username != "-" else full_name
            profile_link = f"<a href='tg://user?id={user_id}'>Профіль</a>"
            formatted_message = f"{message}\n👤 {username_display}\n🔗 {profile_link}"
            await db.execute(
                "INSERT INTO notifications (user_id, username, full_name, type, message) VALUES (?, ?, ?, ?, ?)",
                (user_id, username, full_name, type_, formatted_message)
            )
            await db.commit()
            print(f"✅ Notification saved for {username_display}")
    except Exception as e:
        print(f"⚠️ Error saving notification: {e}")


async def cleanup_old_notifications():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM notifications WHERE created_at < DATETIME('now', '-2 days', 'localtime')")
        await db.commit()


async def get_notifications(page: int = 1, limit: int = 10, filter_type: Optional[str] = None):
    await cleanup_old_notifications()
    offset = (page - 1) * limit
    base_query = "FROM notifications"
    params = []
    if filter_type:
        base_query += " WHERE type = ?"
        params.append(filter_type)

    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(f"SELECT username, full_name, type, message, created_at {base_query} ORDER BY id DESC LIMIT ? OFFSET ?", params + [limit, offset])
        rows = await cursor.fetchall()
        cursor = await db.execute(f"SELECT COUNT(*) {base_query}", params)
        total = (await cursor.fetchone())[0]

    formatted = []
    now = datetime.now()
    for username, full_name, type_, message, created_at in rows:
        try:
            dt = datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S")
            time_str = "сьогодні о " + dt.strftime('%H:%M') if dt.date() == now.date() else "вчора о " + dt.strftime('%H:%M') if dt.date() == (now - timedelta(days=1)).date() else dt.strftime("%d.%m о %H:%M")
        except:
            time_str = created_at
        formatted.append(f"{message}\n🕒 {time_str}")

    total_pages = max(1, (total + limit - 1) // limit)
    return formatted, total_pages


async def add_game_win(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET games_won = games_won + 1 WHERE user_id = ?", (user_id,))
        await db.commit()


async def get_total_money_won():
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT SUM(money_won) FROM users")
        row = await cur.fetchone()
        return row[0] or 0


async def add_money_win(user_id: int, amount: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET money_won = money_won + ? WHERE user_id = ?", (amount, user_id))
        await db.commit()


async def get_safe_state() -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT value FROM safe_state WHERE key='state'")
        row = await cursor.fetchone()
        return json.loads(row[0]) if row else {"opened": [], "win_cell": 198}





async def save_safe_state(data: dict):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR REPLACE INTO safe_state (key, value) VALUES ('state', ?)", (json.dumps(data),))
        await db.commit()