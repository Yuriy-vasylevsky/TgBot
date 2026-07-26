import aiosqlite
from datetime import datetime, timedelta
from typing import Optional, List

from .core import DB_PATH


# ===================== ВНУТРІШНЯ ФУНКЦІЯ =====================
async def ensure_ban_table():
    """Створює таблицю banned_users, якщо її немає"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS banned_users (
                user_id INTEGER PRIMARY KEY,
                reason TEXT,
                banned_by INTEGER,
                ts DATETIME DEFAULT (DATETIME('now', '+3 hours'))
            )
        """)
        await db.commit()


# ===================== ОСНОВНІ ФУНКЦІЇ =====================
async def ban_user(user_id: int, banned_by: Optional[int] = None, reason: str = "Без причини"):
    await ensure_ban_table()                    # ← гарантуємо, що таблиця є
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT OR REPLACE INTO banned_users (user_id, reason, banned_by)
            VALUES (?, ?, ?)
            """,
            (user_id, reason, banned_by)
        )
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


async def get_cards():
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            SELECT COALESCE(NULLIF(TRIM(display_name), ''), bank_name), card_number
            FROM cards
            ORDER BY id
            """
        )
        return await cursor.fetchall()


async def update_card(bank_name: str, display_name: str, new_number: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            UPDATE cards
            SET display_name = ?, card_number = ?
            WHERE bank_name = ?
            """,
            (display_name, new_number, bank_name)
        )
        await db.commit()


async def save_notification(user_id: int, username: str, full_name: str, type_: str, message: str):
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            username_display = f"@{username}" if username and username != "-" else full_name
            profile_link = f"<a href='tg://user?id={user_id}'>Профіль</a>"
            formatted_message = f"{message}\n👤 {username_display}\n🔗 {profile_link}"

            await db.execute(
                """
                INSERT INTO notifications 
                (user_id, username, full_name, type, message)
                VALUES (?, ?, ?, ?, ?)
                """,
                (user_id, username, full_name, type_, formatted_message)
            )
            await db.commit()
    except Exception as e:
        print(f"⚠️ Error saving notification: {e}")


async def get_notifications(page: int = 1, limit: int = 10, filter_type: Optional[str] = None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM notifications WHERE created_at < DATETIME('now', '-2 days')")

        offset = (page - 1) * limit
        where = "WHERE type = ?" if filter_type else ""
        params = [filter_type] if filter_type else []

        cursor = await db.execute(
            f"SELECT username, full_name, type, message, created_at "
            f"FROM notifications {where} ORDER BY id DESC LIMIT ? OFFSET ?",
            params + [limit, offset]
        )
        rows = await cursor.fetchall()

        cursor = await db.execute(f"SELECT COUNT(*) FROM notifications {where}", params)
        total = (await cursor.fetchone())[0]

    formatted = []
    now = datetime.now()
    for username, full_name, type_, message, created_at in rows:
        try:
            dt = datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S")
            if dt.date() == now.date():
                time_str = "сьогодні о " + dt.strftime('%H:%M')
            elif dt.date() == (now - timedelta(days=1)).date():
                time_str = "вчора о " + dt.strftime('%H:%M')
            else:
                time_str = dt.strftime("%d.%m о %H:%M")
        except:
            time_str = created_at
        formatted.append(f"{message}\n🕒 {time_str}")

    total_pages = max(1, (total + limit - 1) // limit)
    return formatted, total_pages


async def add_weekly_task(title: str, description: str, reward: str, duration: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO weekly_tasks (title, description, reward, duration) VALUES (?, ?, ?, ?)",
            (title, description, reward, duration)
        )
        await db.commit()


async def get_active_tasks():
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT id, title, description, reward, duration FROM weekly_tasks WHERE is_active = 1"
        )
        rows = await cursor.fetchall()
        return [
            {"id": r[0], "title": r[1], "description": r[2],
             "reward": r[3], "duration": r[4]} for r in rows
        ]


async def get_user_task_progress(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            SELECT t.id, t.title, t.description, t.reward, 
                   COALESCE(t.duration, '') as duration, 
                   COALESCE(ut.is_completed, 0) 
            FROM weekly_tasks t 
            LEFT JOIN user_tasks ut ON t.id = ut.task_id AND ut.user_id = ? 
            WHERE t.is_active = 1
            """,
            (user_id,)
        )
        rows = await cursor.fetchall()
        return [
            {
                "id": r[0], "title": r[1], "description": r[2],
                "reward": r[3], "duration": r[4], "is_completed": bool(r[5])
            }
            for r in rows
        ]
    

async def get_daily_winnings_summary() -> dict:
    import re
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            SELECT type, message FROM notifications
            WHERE type IN ('slots', 'fortune', 'one_of_three', 'blackjack')
            AND DATE(created_at) = DATE('now', '+3 hours')
            """
        )
        rows = await cursor.fetchall()

    totals = {"slots": 0, "fortune": 0, "one_of_three": 0, "blackjack": 0}

    for (type_, msg) in rows:
        # Програш — завжди пропускаємо
        if "❌" in msg:
            continue

        if type_ == "slots" and "✅" in msg:
            totals["slots"] += 30

        elif type_ == "fortune":
            # Формат: "Колесо фортуни: +50 грн (50 грн)"
            match = re.search(r'\+(\d+)\s*грн', msg)
            if match:
                totals["fortune"] += int(match.group(1))

        elif type_ == "one_of_three" and "✅" in msg:
            totals["one_of_three"] += 30  # вкажи правильну суму якщо інша

        elif type_ == "blackjack" and "✅" in msg:
            totals["blackjack"] += 30  # вкажи правильну суму якщо інша

    grand_total = sum(totals.values())
    return {**totals, "grand_total": grand_total}


async def ensure_profile_ban_table():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""CREATE TABLE IF NOT EXISTS banned_profile_users (
            user_id INTEGER PRIMARY KEY,
            reason TEXT,
            banned_by INTEGER,
            ts DATETIME DEFAULT (DATETIME('now', '+3 hours'))
        )""")
        await db.commit()


async def ban_profile_user(user_id: int, banned_by: int, reason: str | None = None):
    await ensure_profile_ban_table()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO banned_profile_users (user_id, reason, banned_by) VALUES (?, ?, ?)",
            (user_id, reason, banned_by)
        )
        await db.commit()


async def unban_profile_user(user_id: int):
    await ensure_profile_ban_table()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM banned_profile_users WHERE user_id=?", (user_id,))
        await db.commit()


async def is_profile_banned(user_id: int) -> bool:
    await ensure_profile_ban_table()
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT 1 FROM banned_profile_users WHERE user_id=?", (user_id,)
        ) as cur:
            row = await cur.fetchone()
            return bool(row)


async def list_banned_profile() -> list[tuple]:
    await ensure_profile_ban_table()
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            """
            SELECT b.user_id, u.full_name, b.reason, b.banned_by, b.ts
            FROM banned_profile_users b
            LEFT JOIN users u ON u.user_id = b.user_id
            ORDER BY b.ts DESC
            """
        ) as cur:
            return await cur.fetchall()
