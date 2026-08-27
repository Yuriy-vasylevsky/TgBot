import asyncio
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from db import wallet


class PlayerBalancesTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = Path(self.temp_dir.name) / "users.db"
        with sqlite3.connect(self.db_path) as db:
            db.execute(
                """
                CREATE TABLE users (
                    user_id INTEGER PRIMARY KEY,
                    balance INTEGER DEFAULT 0,
                    frozen_balance INTEGER DEFAULT 0,
                    full_name TEXT,
                    username TEXT
                )
                """
            )
            db.executemany(
                """
                INSERT INTO users (user_id, balance, frozen_balance, full_name, username)
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (1, 100, 0, "Available", "available"),
                    (2, 0, 200, "Frozen", "frozen"),
                    (3, 50, 75, "Both", "both"),
                    (4, 0, 0, "Empty", "empty"),
                ],
            )

        self.db_path_patch = patch.object(wallet, "DB_PATH", self.db_path)
        self.db_path_patch.start()

    def tearDown(self):
        self.db_path_patch.stop()
        self.temp_dir.cleanup()

    def test_includes_frozen_funds_in_player_balances(self):
        balances = asyncio.run(wallet.get_all_balances())

        self.assertEqual(
            balances,
            [
                {
                    "user_id": 2,
                    "balance": 200,
                    "full_name": "Frozen",
                    "username": "frozen",
                },
                {
                    "user_id": 3,
                    "balance": 125,
                    "full_name": "Both",
                    "username": "both",
                },
                {
                    "user_id": 1,
                    "balance": 100,
                    "full_name": "Available",
                    "username": "available",
                },
            ],
        )


if __name__ == "__main__":
    unittest.main()
