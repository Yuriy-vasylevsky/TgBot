import aiosqlite

from .core import DB_PATH


ALLOWED_CONTRIBUTIONS = (10, 20, 30)
DEFAULT_LIMIT = 60
DEFAULT_PLAYER_PRIZE = 50
DEFAULT_ADMIN_PRIZE = 10


async def _ensure_schema(db: aiosqlite.Connection) -> None:
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS piggy_bank_state (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            balance INTEGER NOT NULL DEFAULT 0 CHECK (balance >= 0),
            limit_amount INTEGER NOT NULL DEFAULT 60 CHECK (limit_amount > 0),
            player_prize INTEGER NOT NULL DEFAULT 50 CHECK (player_prize >= 0),
            admin_prize INTEGER NOT NULL DEFAULT 10 CHECK (admin_prize >= 0),
            round_number INTEGER NOT NULL DEFAULT 1 CHECK (round_number > 0)
        )
        """
    )
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS piggy_bank_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            round_number INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            amount INTEGER NOT NULL,
            pot_before INTEGER NOT NULL,
            pot_after INTEGER NOT NULL,
            triggered INTEGER NOT NULL DEFAULT 0,
            player_prize INTEGER NOT NULL DEFAULT 0,
            admin_prize INTEGER NOT NULL DEFAULT 0,
            created_at DATETIME DEFAULT (DATETIME('now', '+3 hours'))
        )
        """
    )
    await db.execute(
        """
        INSERT OR IGNORE INTO piggy_bank_state
            (id, balance, limit_amount, player_prize, admin_prize, round_number)
        VALUES (1, 0, ?, ?, ?, 1)
        """,
        (DEFAULT_LIMIT, DEFAULT_PLAYER_PRIZE, DEFAULT_ADMIN_PRIZE),
    )


async def ensure_piggy_bank_tables() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await _ensure_schema(db)
        await db.commit()


def _state_dict(row: tuple) -> dict:
    return {
        "balance": int(row[0]),
        "limit": int(row[1]),
        "player_prize": int(row[2]),
        "admin_prize": int(row[3]),
        "round_number": int(row[4]),
    }


async def get_piggy_bank_state() -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        await _ensure_schema(db)
        cursor = await db.execute(
            """
            SELECT balance, limit_amount, player_prize, admin_prize, round_number
            FROM piggy_bank_state WHERE id = 1
            """
        )
        row = await cursor.fetchone()
        await db.commit()
    return _state_dict(row)


async def contribute_to_piggy_bank(
    user_id: int, amount: int, admin_id: int
) -> dict:
    """Atomically debit a player, update the pot, and pay a completed round."""
    if amount not in ALLOWED_CONTRIBUTIONS:
        return {"success": False, "reason": "invalid_amount"}

    async with aiosqlite.connect(DB_PATH, timeout=30) as db:
        await _ensure_schema(db)
        await db.commit()
        await db.execute("BEGIN IMMEDIATE")
        try:
            cursor = await db.execute(
                """
                SELECT balance, limit_amount, player_prize, admin_prize, round_number
                FROM piggy_bank_state WHERE id = 1
                """
            )
            state = _state_dict(await cursor.fetchone())

            cursor = await db.execute(
                "SELECT COALESCE(balance, 0) FROM users WHERE user_id = ?",
                (user_id,),
            )
            user_row = await cursor.fetchone()
            user_balance = int(user_row[0]) if user_row else 0
            if user_balance < amount:
                await db.rollback()
                return {
                    "success": False,
                    "reason": "insufficient_funds",
                    "balance": user_balance,
                    "state": state,
                }

            await db.execute(
                "UPDATE users SET balance = COALESCE(balance, 0) - ? WHERE user_id = ?",
                (amount, user_id),
            )
            pot_before = state["balance"]
            collected = pot_before + amount
            triggered = collected >= state["limit"]
            pot_after = collected
            admin_payout = 0

            if triggered:
                total_prize = state["player_prize"] + state["admin_prize"]
                remainder = collected - total_prize
                admin_payout = state["admin_prize"] + remainder
                pot_after = 0
                await db.execute(
                    "UPDATE users SET balance = COALESCE(balance, 0) + ? "
                    "WHERE user_id = ?",
                    (state["player_prize"], user_id),
                )
                await db.execute(
                    """
                    INSERT INTO users (user_id, balance)
                    VALUES (?, ?)
                    ON CONFLICT(user_id) DO UPDATE
                    SET balance = COALESCE(balance, 0) + excluded.balance
                    """,
                    (admin_id, admin_payout),
                )
                await db.execute(
                    """
                    UPDATE piggy_bank_state
                    SET balance = ?, round_number = round_number + 1
                    WHERE id = 1
                    """,
                    (pot_after,),
                )
            else:
                await db.execute(
                    "UPDATE piggy_bank_state SET balance = ? WHERE id = 1",
                    (pot_after,),
                )

            await db.execute(
                """
                INSERT INTO piggy_bank_events (
                    round_number, user_id, amount, pot_before, pot_after,
                    triggered, player_prize, admin_prize
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    state["round_number"],
                    user_id,
                    amount,
                    pot_before,
                    pot_after,
                    int(triggered),
                    state["player_prize"] if triggered else 0,
                    admin_payout,
                ),
            )
            cursor = await db.execute(
                "SELECT COALESCE(balance, 0) FROM users WHERE user_id = ?",
                (user_id,),
            )
            new_user_balance = int((await cursor.fetchone())[0])
            await db.commit()
        except Exception:
            await db.rollback()
            raise

    state["balance"] = pot_after
    if triggered:
        state["round_number"] += 1
    return {
        "success": True,
        "triggered": triggered,
        "amount": amount,
        "balance": new_user_balance,
        "admin_payout": admin_payout,
        "state": state,
    }


async def update_piggy_bank_setting(setting: str, value: int) -> dict:
    columns = {
        "limit": "limit_amount",
        "player_prize": "player_prize",
        "admin_prize": "admin_prize",
    }
    if setting not in columns:
        return {"success": False, "reason": "unknown_setting"}
    if value < 0 or value % 10 != 0 or (setting == "limit" and value == 0):
        return {"success": False, "reason": "invalid_value"}

    async with aiosqlite.connect(DB_PATH, timeout=30) as db:
        await _ensure_schema(db)
        await db.commit()
        await db.execute("BEGIN IMMEDIATE")
        try:
            cursor = await db.execute(
                """
                SELECT balance, limit_amount, player_prize, admin_prize, round_number
                FROM piggy_bank_state WHERE id = 1
                """
            )
            current = _state_dict(await cursor.fetchone())
            updated = dict(current)
            updated[setting] = value

            if updated["limit"] < updated["balance"]:
                await db.rollback()
                return {
                    "success": False,
                    "reason": "below_balance",
                    "state": current,
                }
            total_prize = updated["player_prize"] + updated["admin_prize"]
            if total_prize <= 0 or total_prize > updated["limit"]:
                await db.rollback()
                return {
                    "success": False,
                    "reason": "invalid_prize_total",
                    "state": current,
                }

            await db.execute(
                f"UPDATE piggy_bank_state SET {columns[setting]} = ? WHERE id = 1",
                (value,),
            )
            await db.commit()
        except Exception:
            await db.rollback()
            raise

    return {"success": True, "state": updated}
