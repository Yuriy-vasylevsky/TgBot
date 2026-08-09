import asyncio
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from db import users


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
                    balance INTEGER DEFAULT 0
                )
                """
            )

        self.db_path_patch = patch.object(users, "DB_PATH", self.db_path)
        self.db_path_patch.start()

    def tearDown(self):
        self.db_path_patch.stop()
        self.temp_dir.cleanup()

    def test_new_user_receives_starting_balance_only_once(self):
        asyncio.run(users.save_user(123, "new_player", "New Player"))

        with sqlite3.connect(self.db_path) as db:
            first_balance = db.execute(
                "SELECT balance FROM users WHERE user_id = 123"
            ).fetchone()[0]

        asyncio.run(users.save_user(123, "renamed_player", "New Name"))

        with sqlite3.connect(self.db_path) as db:
            saved_user = db.execute(
                "SELECT username, full_name, balance FROM users WHERE user_id = 123"
            ).fetchone()

        self.assertEqual(first_balance, 50)
        self.assertEqual(saved_user, ("renamed_player", "New Name", 50))

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


if __name__ == "__main__":
    unittest.main()
