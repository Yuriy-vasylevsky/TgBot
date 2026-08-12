import asyncio
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from db import users, wallet


class NewUserBalanceTests(unittest.TestCase):
    def setUp(self):
        # aiosqlite's worker can briefly retain the file handle on Windows.
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = Path(self.temp_dir.name) / "users.db"
        with sqlite3.connect(self.db_path) as db:
            db.execute(
                """
                CREATE TABLE users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    full_name TEXT,
                    last_active TEXT,
                    last_actions TEXT DEFAULT '',
                    balance INTEGER DEFAULT 0,
                    first_deposit_bonus_pending INTEGER DEFAULT 0
                )
                """
            )

        self.db_path_patch = patch.object(users, "DB_PATH", self.db_path)
        self.db_path_patch.start()
        self.wallet_db_path_patch = patch.object(wallet, "DB_PATH", self.db_path)
        self.wallet_db_path_patch.start()

    def tearDown(self):
        self.wallet_db_path_patch.stop()
        self.db_path_patch.stop()
        self.temp_dir.cleanup()

    def test_new_user_starts_with_pending_deposit_bonus(self):
        asyncio.run(users.save_user(123, "new_player", "New Player"))

        with sqlite3.connect(self.db_path) as db:
            first_balance = db.execute(
                "SELECT balance, first_deposit_bonus_pending FROM users WHERE user_id = 123"
            ).fetchone()

        asyncio.run(users.save_user(123, "renamed_player", "New Name"))

        with sqlite3.connect(self.db_path) as db:
            saved_user = db.execute(
                "SELECT username, full_name, balance, first_deposit_bonus_pending FROM users WHERE user_id = 123"
            ).fetchone()

        self.assertEqual(first_balance, (0, 1))
        self.assertEqual(saved_user, ("renamed_player", "New Name", 0, 1))

    def test_existing_balance_is_not_replaced(self):
        with sqlite3.connect(self.db_path) as db:
            db.execute(
                "INSERT INTO users (user_id, balance) VALUES (456, 175)"
            )

        asyncio.run(users.save_user(456, "existing", "Existing Player"))

        with sqlite3.connect(self.db_path) as db:
            balance = db.execute(
                "SELECT balance FROM users WHERE user_id = 456"
            ).fetchone()[0]

        self.assertEqual(balance, 175)

    def test_bonus_is_added_only_to_first_deposit(self):
        asyncio.run(users.save_user(789, "new_player", "New Player"))

        first = asyncio.run(wallet.credit_deposit_with_bonus(789, 100))
        second = asyncio.run(wallet.credit_deposit_with_bonus(789, 200))

        with sqlite3.connect(self.db_path) as db:
            balance, pending = db.execute(
                "SELECT balance, first_deposit_bonus_pending FROM users WHERE user_id = 789"
            ).fetchone()

        self.assertEqual(first, {"bonus": 50, "credited": 150})
        self.assertEqual(second, {"bonus": 0, "credited": 200})
        self.assertEqual((balance, pending), (350, 0))


if __name__ == "__main__":
    unittest.main()
