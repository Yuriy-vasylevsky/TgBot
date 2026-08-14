import tempfile
import unittest
from pathlib import Path

import aiosqlite

import db.games as games_db


class GameStatsTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.old_db_path = games_db.DB_PATH
        games_db.DB_PATH = Path(self.temp_dir.name) / "game_stats.db"

        async with aiosqlite.connect(games_db.DB_PATH) as db:
            await db.executescript(
                """
                CREATE TABLE game_stats (
                    game_name TEXT PRIMARY KEY,
                    total_games INTEGER DEFAULT 0,
                    wins INTEGER DEFAULT 0
                );
                CREATE TABLE slot_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    result TEXT,
                    final_balance INTEGER,
                    ts DATETIME
                );
                CREATE TABLE blackjack_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    is_win INTEGER
                );
                CREATE TABLE users (
                    user_id INTEGER PRIMARY KEY,
                    money_won INTEGER DEFAULT 0
                );
                """
            )
            await db.commit()

    async def asyncTearDown(self):
        games_db.DB_PATH = self.old_db_path
        self.temp_dir.cleanup()

    async def test_each_game_counts_total_wins_and_losses(self):
        await games_db.add_game_result("Один з трьох", True)
        await games_db.add_game_result("Один з трьох", False)
        await games_db.add_game_result("Один з трьох", True)

        await games_db.add_slot_session(101, "win", 30)
        await games_db.add_slot_session(102, "loss", 0)

        await games_db.add_blackjack_session(True)
        await games_db.add_blackjack_session(False)
        await games_db.add_blackjack_session(False)

        self.assertEqual(
            await games_db.get_all_stats(),
            [("Один з трьох", 3, 2)],
        )
        self.assertEqual(await games_db.get_slot_session_stats(), (2, 1))
        self.assertEqual(await games_db.get_blackjack_session_stats(), (3, 1))

    async def test_empty_statistics_return_zeroes(self):
        self.assertEqual(await games_db.get_all_stats(), [])
        self.assertEqual(await games_db.get_slot_session_stats(), (0, 0))
        self.assertEqual(await games_db.get_blackjack_session_stats(), (0, 0))

    async def test_clear_removes_all_game_statistics(self):
        await games_db.add_game_result("Один з трьох", True)
        await games_db.add_slot_session(101, "win", 30)
        await games_db.add_blackjack_session(True)

        await games_db.clear_game_stats()

        self.assertEqual(await games_db.get_all_stats(), [])
        self.assertEqual(await games_db.get_slot_session_stats(), (0, 0))
        self.assertEqual(await games_db.get_blackjack_session_stats(), (0, 0))


if __name__ == "__main__":
    unittest.main()
