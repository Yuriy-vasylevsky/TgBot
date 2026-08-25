import tempfile
import unittest
from pathlib import Path

import aiosqlite

import db.users as users_db


class TopPlayersTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.old_db_path = users_db.DB_PATH
        users_db.DB_PATH = Path(self.temp_dir.name) / "top_players.db"

        async with aiosqlite.connect(users_db.DB_PATH) as db:
            await db.execute(
                """
                CREATE TABLE users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    full_name TEXT,
                    total_losses_all_time INTEGER DEFAULT 0,
                    daily_net INTEGER DEFAULT 0
                )
                """
            )
            await db.executemany(
                """
                INSERT INTO users (
                    user_id, username, full_name,
                    total_losses_all_time, daily_net
                ) VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (101, "first", "Перший", 700, 50),
                    (202, "second", "Другий", 300, 100),
                    (303, None, "Переможець", -200, 50),
                    (404, "zero", "Нуль", 0, 0),
                    (505, "third", "Третій", 350, 0),
                ],
            )
            await db.commit()

    async def asyncTearDown(self):
        users_db.DB_PATH = self.old_db_path
        self.temp_dir.cleanup()

    async def test_ranks_positive_all_time_losses_including_current_day(self):
        players, count, total_loss = await users_db.get_top_players_by_losses()

        self.assertEqual([player["user_id"] for player in players], [101, 202, 505])
        self.assertEqual([player["total_loss"] for player in players], [750, 400, 350])
        self.assertEqual(count, 3)
        self.assertEqual(total_loss, 1500)

    async def test_supports_pagination(self):
        players, count, total_loss = await users_db.get_top_players_by_losses(
            limit=1,
            offset=1,
        )

        self.assertEqual([player["user_id"] for player in players], [202])
        self.assertEqual(count, 3)
        self.assertEqual(total_loss, 1500)


if __name__ == "__main__":
    unittest.main()
