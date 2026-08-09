import aiosqlite
import json
import math
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from .core import DB_PATH


SAFE_TOP_LIMIT = 5
SAFE_PRIZE_POOL = 1000
KYIV_ZONE = ZoneInfo("Europe/Kyiv")


def calculate_safe_prizes(users: dict) -> list[dict]:
    """Match the web leaderboard's proportional top-5 prize calculation."""
    ranked = sorted(
        (
            {
                "user_id": int(user_id),
                "display_name": user.get("display_name") or str(user_id),
                "count": int(user.get("count", 0)),
            }
            for user_id, user in users.items()
            if int(user.get("count", 0)) > 0
        ),
        key=lambda user: user["count"],
        reverse=True,
    )[:SAFE_TOP_LIMIT]

    if not ranked:
        return []

    total_cells = sum(user["count"] for user in ranked)
    for user in ranked:
        # JavaScript Math.round for positive values, as used by the website.
        user["amount"] = math.floor(
            user["count"] / total_cells * SAFE_PRIZE_POOL + 0.5
        )

    difference = SAFE_PRIZE_POOL - sum(user["amount"] for user in ranked)
    ranked[-1]["amount"] += difference
    return ranked


async def get_safe_state() -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT value FROM safe_state WHERE key='state'"
        )
        row = await cursor.fetchone()
        return json.loads(row[0]) if row else {"opened": [], "win_cell": 198}


async def save_safe_state(data: dict):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO safe_state (key, value) VALUES ('state', ?)",
            (json.dumps(data),)
        )
        await db.commit()


async def close_safe_round_and_credit(win_cell: int) -> list[dict]:
    """Credit the current top five as deposits and atomically clear the round."""
    today = datetime.now(KYIV_ZONE).date()
    today_str = today.isoformat()
    yesterday_str = (today - timedelta(days=1)).isoformat()

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("BEGIN IMMEDIATE")
        try:
            cursor = await db.execute(
                "SELECT value FROM safe_state WHERE key = 'state'"
            )
            row = await cursor.fetchone()
            await cursor.close()
            state = json.loads(row[0]) if row else {}
            awards = calculate_safe_prizes(state.get("users", {}))

            for award in awards:
                user_id = award["user_id"]
                display_name = award["display_name"]
                amount = award["amount"]
                username = display_name[1:] if display_name.startswith("@") else None

                await db.execute(
                    """
                    INSERT OR IGNORE INTO users (user_id, username, full_name)
                    VALUES (?, ?, ?)
                    """,
                    (user_id, username, None if username else display_name),
                )
                cursor = await db.execute(
                    """
                    SELECT COALESCE(daily_net, 0), last_net_date
                    FROM users WHERE user_id = ?
                    """,
                    (user_id,),
                )
                daily_net, last_net_date = await cursor.fetchone()
                await cursor.close()
                if last_net_date != today_str:
                    yesterday_net = daily_net if last_net_date == yesterday_str else 0
                    await db.execute(
                        """
                        UPDATE users
                        SET yesterday_net = ?, daily_net = 0,
                            cashback_claimed_base = 0, promo_claimed_base = 0,
                            last_net_date = ?,
                            total_losses_all_time =
                                COALESCE(total_losses_all_time, 0) + ?
                        WHERE user_id = ?
                        """,
                        (yesterday_net, today_str, daily_net, user_id),
                    )

                await db.execute(
                    """
                    UPDATE users
                    SET balance = COALESCE(balance, 0) + ?,
                        daily_net = COALESCE(daily_net, 0) + ?,
                        last_net_date = ?
                    WHERE user_id = ?
                    """,
                    (amount, amount, today_str, user_id),
                )
                await db.execute(
                    """
                    INSERT INTO payment_logs (user_id, username, amount, comment)
                    VALUES (?, ?, ?, ?)
                    """,
                    (user_id, display_name, amount, "SAFE_TOP_5"),
                )

            cleared_state = {
                "opened": [],
                "win_cell": win_cell,
                "users": {},
            }
            await db.execute(
                "INSERT OR REPLACE INTO safe_state (key, value) VALUES ('state', ?)",
                (json.dumps(cleared_state),),
            )
            await db.commit()
            return awards
        except Exception:
            await db.rollback()
            raise
