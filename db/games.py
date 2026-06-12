# db/games.py
import aiosqlite
from typing import List, Tuple, Optional

from .core import DB_PATH


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
            (game_name, 1 if is_win else 0, 1 if is_win else 0)
        )
        await db.commit()


async def get_all_stats() -> List[Tuple[str, int, int]]:
    """Використовується в handlers/stats.py"""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT game_name, total_games, wins FROM game_stats"
        ) as cur:
            return await cur.fetchall()


async def reset_all_game_stats():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET games_played = 0, games_won = 0")
        await db.commit()
    print("✅ Статистика ігор очищена!")


async def add_slot_session(user_id: int, result: str, final_balance: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO slot_sessions (user_id, result, final_balance, ts)
            VALUES (?, ?, ?, DATETIME('now', '+3 hours'))
            """,
            (user_id, result, final_balance)
        )
        await db.commit()


async def get_slot_session_stats() -> Tuple[int, int]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            """
            SELECT COUNT(*), 
                   SUM(CASE WHEN result='win' THEN 1 ELSE 0 END)
            FROM slot_sessions
            """
        ) as cur:
            row = await cur.fetchone()
            return (row[0] or 0, row[1] or 0)


async def add_blackjack_session(is_win: bool):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO blackjack_sessions (is_win) VALUES (?)",
            (1 if is_win else 0,)
        )
        await db.commit()


async def get_blackjack_session_stats():
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT COUNT(*), SUM(is_win) FROM blackjack_sessions"
        )
        total, wins = await cursor.fetchone()
        return (total or 0, wins or 0)


async def clear_game_stats():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM game_stats")
        await db.execute("DELETE FROM slot_sessions")
        await db.execute("DELETE FROM blackjack_sessions")
        await db.execute("UPDATE users SET money_won = 0")
        await db.commit()


async def add_casino_code(code: str, casino_type: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO casino_codes (code, casino_type) VALUES (?, ?)",
            (code, casino_type)
        )
        await db.commit()


async def get_free_code(casino_type: str) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT id, code FROM casino_codes WHERE casino_type=? AND used=0 LIMIT 1",
            (casino_type,)
        ) as cur:
            row = await cur.fetchone()
            return {"id": row[0], "code": row[1]} if row else None


async def mark_code_used_by_id(code_id: int, user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE casino_codes SET used=1, assigned_to=?, assigned_at=DATETIME('now', '+3 hours') WHERE id=?",
            (user_id, code_id)
        )
        await db.commit()


async def mark_code_unused(code_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE casino_codes SET used=0, assigned_to=NULL, assigned_at=NULL WHERE id=?",
            (code_id,)
        )
        await db.commit()


async def create_pending_reward(user_id: int, code_id: Optional[int], casino_type: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO pending_rewards (user_id, code_id, casino_type, status) VALUES (?, ?, ?, 'pending')",
            (user_id, code_id, casino_type)
        )
        await db.commit()
        return cur.lastrowid


async def set_pending_status(pending_id: int, status: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE pending_rewards SET status=? WHERE id=?", (status, pending_id))
        await db.commit()


async def get_pending_by_id(pending_id: int) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT id, user_id, code_id, casino_type, status FROM pending_rewards WHERE id=?",
            (pending_id,)
        ) as cur:
            row = await cur.fetchone()
            return {"id": row[0], "user_id": row[1], "code_id": row[2], "casino_type": row[3], "status": row[4]} if row else None


async def get_winrate() -> float:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT value FROM settings WHERE key='winrate'") as cur:
            row = await cur.fetchone()
            return float(row[0]) if row else 0.33


async def set_winrate(value: float):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO settings (key, value) VALUES ('winrate', ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (value,)
        )
        await db.commit()


async def spend_promo_for_fortune(user_id: int, cost: int = 3) -> bool:
    if await get_promo(user_id) < cost:
        return False
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET games_played = games_played - ? WHERE user_id = ?", (cost, user_id))
        await db.commit()
    return True


async def add_promo(user_id: int, amount: int = 1):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO users (user_id, games_played) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET games_played = games_played + ?",
            (user_id, amount, amount)
        )
        await db.commit()


async def get_promo(user_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT games_played FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0
        





# Код для додавання чеків


