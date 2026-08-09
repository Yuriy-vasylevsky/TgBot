import aiosqlite
from datetime import datetime, timezone, timedelta
from typing import List, Optional

from .core import DB_PATH


NEW_USER_STARTING_BALANCE = 50


async def save_user(
    user_id: int,
    username: str,
    full_name: str,
    action: str = None,
    chat_type: str | None = None,
):
    if chat_type and chat_type != "private":
        action = None

    kyiv_tz = timezone(timedelta(hours=3))
    now_str = datetime.now(kyiv_tz).isoformat(timespec="seconds")

    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT last_actions FROM users WHERE user_id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        old_actions = row[0] if row and row[0] else ""

        new_actions = old_actions
        if action:
            parts = old_actions.split(" | ") if old_actions else []
            parts.insert(0, action.strip())
            parts = parts[:20]
            new_actions = " | ".join(parts)

        await db.execute(
            """
            INSERT INTO users (
                user_id, username, full_name, last_active, last_actions, balance
            )
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username = excluded.username,
                full_name = excluded.full_name,
                last_active = excluded.last_active,
                last_actions = excluded.last_actions
            """,
            (
                user_id,
                username,
                full_name,
                now_str,
                new_actions,
                NEW_USER_STARTING_BALANCE,
            )
        )
        await db.commit()


async def get_all_users() -> List[int]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id FROM users") as cur:
            rows = await cur.fetchall()
            return [r[0] for r in rows]


async def get_all_users_info():
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT user_id, full_name, username, last_active, last_actions, "
            "games_played, games_won FROM users"
        )
        rows = await cur.fetchall()
    return [
        {
            "user_id": r[0], "full_name": r[1], "username": r[2],
            "last_active": r[3], "last_actions": r[4],
            "games_played": r[5], "games_won": r[6]
        } for r in rows
    ]


async def has_claimed_gift(user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT has_claimed_gift FROM users WHERE user_id=?", (user_id,)
        ) as cur:
            row = await cur.fetchone()
            return bool(row and row[0] == 1)


async def set_gift_claimed(user_id: int, claimed: bool):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET has_claimed_gift = ? WHERE user_id = ?",
            (1 if claimed else 0, user_id)
        )
        await db.commit()


async def reset_all_gifts():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET has_claimed_gift = 0")
        await db.commit()
    print("✅ Подарунки скинуто для всіх користувачів.")


async def set_user_access(user_id: int, access: bool):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET has_access=? WHERE user_id=?",
            (1 if access else 0, user_id)
        )
        await db.commit()


async def get_user_access(user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT has_access FROM users WHERE user_id=?", (user_id,)
        ) as cur:
            row = await cur.fetchone()
            return bool(row and row[0] == 1)


async def add_last_action(user_id: int, action: str, chat_type: str | None = None):
    if chat_type and chat_type != "private":
        return
    if not action or not action.strip():
        return

    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT last_actions FROM users WHERE user_id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        actions_str = row[0] if row else ""
        parts = [a.strip() for a in actions_str.split(" | ") if a.strip()]
        parts.insert(0, action.strip())
        parts = parts[:20]
        new_actions = " | ".join(parts)

        await db.execute(
            "UPDATE users SET last_actions = ? WHERE user_id = ?",
            (new_actions, user_id)
        )
        await db.commit()


async def get_user_data(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT username, full_name, games_played, games_won "
            "FROM users WHERE user_id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        return (
            {"username": row[0], "full_name": row[1],
             "games_played": row[2], "games_won": row[3]}
            if row else None
        )


async def increment_games_played(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
        await db.execute(
            "UPDATE users SET games_played = games_played + 1 WHERE user_id = ?",
            (user_id,)
        )
        await db.commit()


async def add_game_win(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET games_won = games_won + 1 WHERE user_id = ?",
            (user_id,)
        )
        await db.commit()


async def add_money_win(user_id: int, amount: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET money_won = money_won + ? WHERE user_id = ?",
            (amount, user_id)
        )
        await db.commit()


async def get_total_money_won():
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT SUM(money_won) FROM users")
        row = await cur.fetchone()
        return row[0] or 0
    

async def add_or_update_user(user_id: int, username: str, full_name: str):
    """Оновлює або створює користувача (використовується в profile.py)"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO users (user_id, username, full_name, last_active)
            VALUES (?, ?, ?, DATETIME('now', '+3 hours'))
            ON CONFLICT(user_id) DO UPDATE SET
                username = excluded.username,
                full_name = excluded.full_name,
                last_active = excluded.last_active
            """,
            (user_id, username, full_name)
        )
        await db.commit()

# ++++++++++++++++++++++++++++++++++++++++++++++++

from datetime import datetime, timedelta, timezone


KYIV_TZ = timezone(timedelta(hours=3))


async def is_promo_on_cooldown(user_id: int) -> bool:
    """Перевіряє, чи користувач ще на кулдауні промо"""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT promo_cooldown_until FROM users WHERE user_id = ?",
            (user_id,)
        ) as cur:
            row = await cur.fetchone()
            if not row or not row[0]:
                return False

            cooldown_until = datetime.fromisoformat(row[0])
            now = datetime.now(KYIV_TZ)
            return now < cooldown_until


async def get_promo_cooldown_remaining(user_id: int) -> tuple[int, int] | None:
    """Повертає (години, хвилини), що залишилось, або None якщо кулдаун минув"""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT promo_cooldown_until FROM users WHERE user_id = ?",
            (user_id,)
        ) as cur:
            row = await cur.fetchone()
            if not row or not row[0]:
                return None

            cooldown_until = datetime.fromisoformat(row[0])
            now = datetime.now(KYIV_TZ)

            if now >= cooldown_until:
                return None

            delta = cooldown_until - now
            hours = int(delta.total_seconds() // 3600)
            minutes = int((delta.total_seconds() % 3600) // 60)
            return hours, minutes


async def set_promo_cooldown(user_id: int, hours: int = 12):
    """Встановлює кулдаун на N годин від поточного моменту"""
    future = datetime.now(KYIV_TZ) + timedelta(hours=hours)
    future_str = future.isoformat(timespec="seconds")

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            UPDATE users 
            SET promo_cooldown_until = ? 
            WHERE user_id = ?
            """,
            (future_str, user_id)
        )
        await db.commit()


# async def search_users(query: str) -> list[dict]:
#     async with aiosqlite.connect(DB_PATH) as db:
#         db.row_factory = aiosqlite.Row  # ← додай це
#         sql = """
#             SELECT * FROM users 
#             WHERE full_name LIKE ? 
#                OR username LIKE ? 
#                OR CAST(user_id AS TEXT) LIKE ?
#             ORDER BY last_active DESC
#         """
#         search_pattern = f"%{query}%"
#         async with db.execute(sql, (search_pattern, search_pattern, search_pattern)) as cursor:
#             rows = await cursor.fetchall()
#             return [dict(row) for row in rows] if rows else []

async def search_users(query: str) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        # Реєструємо функцію, яка коректно лоуеркейсить кирилицю
        await db.create_function("lower_unicode", 1, lambda x: x.lower() if x else x)

        sql = """
            SELECT * FROM users 
            WHERE lower_unicode(full_name) LIKE lower_unicode(?) 
               OR lower_unicode(username) LIKE lower_unicode(?)
               OR CAST(user_id AS TEXT) LIKE ?
            ORDER BY last_active DESC
        """
        search_pattern = f"%{query}%"
        async with db.execute(sql, (search_pattern, search_pattern, search_pattern)) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows] if rows else []
