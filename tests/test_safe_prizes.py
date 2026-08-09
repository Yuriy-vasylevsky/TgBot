import asyncio
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from db.safe import calculate_safe_prizes, close_safe_round_and_credit


class SafePrizeCalculationTests(unittest.TestCase):
    def test_distributes_full_pool_proportionally_between_top_five(self):
        users = {
            "1": {"display_name": "one", "count": 50},
            "2": {"display_name": "two", "count": 25},
            "3": {"display_name": "three", "count": 15},
            "4": {"display_name": "four", "count": 5},
            "5": {"display_name": "five", "count": 5},
            "6": {"display_name": "six", "count": 100},
        }

        awards = calculate_safe_prizes(users)

        self.assertEqual([award["user_id"] for award in awards], [6, 1, 2, 3, 4])
        self.assertEqual(sum(award["amount"] for award in awards), 1000)
        self.assertEqual([award["amount"] for award in awards], [513, 256, 128, 77, 26])

    def test_empty_round_has_no_awards(self):
        self.assertEqual(calculate_safe_prizes({}), [])

    def test_closing_round_credits_deposit_log_once(self):
        # aiosqlite's worker can briefly retain the file handle on Windows.
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            db_path = Path(temp_dir) / "safe-test.db"
            with sqlite3.connect(db_path) as db:
                db.execute("CREATE TABLE safe_state (key TEXT PRIMARY KEY, value TEXT)")
                db.execute(
                    """
                    CREATE TABLE users (
                        user_id INTEGER PRIMARY KEY, username TEXT, full_name TEXT,
                        balance INTEGER DEFAULT 0, daily_net INTEGER DEFAULT 0,
                        yesterday_net INTEGER DEFAULT 0, last_net_date TEXT,
                        cashback_claimed_base INTEGER DEFAULT 0,
                        promo_claimed_base INTEGER DEFAULT 0,
                        total_losses_all_time INTEGER DEFAULT 0
                    )
                    """
                )
                db.execute(
                    """
                    CREATE TABLE payment_logs (
                        id INTEGER PRIMARY KEY, user_id INTEGER, username TEXT,
                        amount INTEGER, comment TEXT
                    )
                    """
                )
                db.execute(
                    "INSERT INTO safe_state (key, value) VALUES ('state', ?)",
                    (json.dumps({
                        "opened": [1, 2, 3], "win_cell": 198,
                        "users": {
                            "10": {"display_name": "@first", "count": 2},
                            "20": {"display_name": "Second", "count": 1},
                        },
                    }),),
                )

            with patch("db.safe.DB_PATH", str(db_path)):
                first_awards = asyncio.run(close_safe_round_and_credit(198))
                second_awards = asyncio.run(close_safe_round_and_credit(198))

            self.assertEqual([award["amount"] for award in first_awards], [667, 333])
            self.assertEqual(second_awards, [])
            with sqlite3.connect(db_path) as db:
                balances = db.execute(
                    "SELECT user_id, balance, daily_net FROM users ORDER BY user_id"
                ).fetchall()
                logs = db.execute(
                    "SELECT user_id, amount, comment FROM payment_logs ORDER BY user_id"
                ).fetchall()
            self.assertEqual(balances, [(10, 667, 667), (20, 333, 333)])
            self.assertEqual(
                logs,
                [(10, 667, "SAFE_TOP_5"), (20, 333, "SAFE_TOP_5")],
            )


if __name__ == "__main__":
    unittest.main()
