import asyncio
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from db import piggy_bank


class PiggyBankTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = Path(self.temp_dir.name) / "users.db"
        with sqlite3.connect(self.db_path) as db:
            db.execute(
                """
                CREATE TABLE users (
                    user_id INTEGER PRIMARY KEY,
                    balance INTEGER DEFAULT 0
                )
                """
            )
            db.executemany(
                "INSERT INTO users (user_id, balance) VALUES (?, ?)",
                [(101, 100), (202, 100), (999, 0)],
            )

        self.db_path_patch = patch.object(piggy_bank, "DB_PATH", self.db_path)
        self.db_path_patch.start()

    def tearDown(self):
        self.db_path_patch.stop()
        self.temp_dir.cleanup()

    def test_defaults_and_regular_contribution(self):
        initial = asyncio.run(piggy_bank.get_piggy_bank_state())
        self.assertEqual(
            initial,
            {
                "balance": 0,
                "limit": 60,
                "player_prize": 50,
                "admin_prize": 10,
                "round_number": 1,
            },
        )

        result = asyncio.run(piggy_bank.contribute_to_piggy_bank(101, 20, 999))

        self.assertTrue(result["success"])
        self.assertFalse(result["triggered"])
        self.assertEqual(result["balance"], 80)
        self.assertEqual(result["state"]["balance"], 20)

    def test_last_contributor_receives_prize_and_admin_share(self):
        asyncio.run(piggy_bank.contribute_to_piggy_bank(101, 30, 999))
        result = asyncio.run(piggy_bank.contribute_to_piggy_bank(202, 30, 999))

        self.assertTrue(result["triggered"])
        self.assertEqual(result["balance"], 120)
        self.assertEqual(result["state"]["balance"], 0)
        self.assertEqual(result["state"]["round_number"], 2)

        with sqlite3.connect(self.db_path) as db:
            balances = dict(db.execute("SELECT user_id, balance FROM users"))
            event = db.execute(
                """
                SELECT amount, triggered, player_prize, admin_prize
                FROM piggy_bank_events ORDER BY id DESC LIMIT 1
                """
            ).fetchone()

        self.assertEqual(balances[101], 70)
        self.assertEqual(balances[202], 120)
        self.assertEqual(balances[999], 10)
        self.assertEqual(event, (30, 1, 50, 10))

    def test_insufficient_contribution_does_not_change_balances(self):
        asyncio.run(piggy_bank.contribute_to_piggy_bank(101, 30, 999))
        asyncio.run(piggy_bank.contribute_to_piggy_bank(101, 20, 999))

        insufficient = asyncio.run(
            piggy_bank.contribute_to_piggy_bank(999, 10, 999)
        )

        self.assertEqual(insufficient["reason"], "insufficient_funds")
        self.assertEqual(asyncio.run(piggy_bank.get_piggy_bank_state())["balance"], 50)

        with sqlite3.connect(self.db_path) as db:
            balances = dict(db.execute("SELECT user_id, balance FROM users"))
        self.assertEqual(balances[101], 50)
        self.assertEqual(balances[999], 0)

    def test_over_limit_remainder_is_paid_to_admin(self):
        asyncio.run(piggy_bank.contribute_to_piggy_bank(101, 30, 999))
        asyncio.run(piggy_bank.contribute_to_piggy_bank(101, 20, 999))

        result = asyncio.run(piggy_bank.contribute_to_piggy_bank(202, 20, 999))

        self.assertTrue(result["triggered"])
        self.assertEqual(result["admin_payout"], 20)
        self.assertEqual(result["state"]["balance"], 0)
        with sqlite3.connect(self.db_path) as db:
            balances = dict(db.execute("SELECT user_id, balance FROM users"))
        self.assertEqual(balances[202], 130)
        self.assertEqual(balances[999], 20)

    def test_admin_settings_are_validated(self):
        updated = asyncio.run(
            piggy_bank.update_piggy_bank_setting("limit", 100)
        )
        player = asyncio.run(
            piggy_bank.update_piggy_bank_setting("player_prize", 80)
        )
        too_much = asyncio.run(
            piggy_bank.update_piggy_bank_setting("admin_prize", 30)
        )
        not_multiple = asyncio.run(
            piggy_bank.update_piggy_bank_setting("admin_prize", 15)
        )

        self.assertTrue(updated["success"])
        self.assertTrue(player["success"])
        self.assertEqual(too_much["reason"], "invalid_prize_total")
        self.assertEqual(not_multiple["reason"], "invalid_value")
        state = asyncio.run(piggy_bank.get_piggy_bank_state())
        self.assertEqual(
            (state["limit"], state["player_prize"], state["admin_prize"]),
            (100, 80, 10),
        )

    def test_simultaneous_final_contributions_pay_only_one_winner(self):
        asyncio.run(piggy_bank.contribute_to_piggy_bank(101, 30, 999))
        asyncio.run(piggy_bank.contribute_to_piggy_bank(101, 20, 999))

        async def contribute_together():
            return await asyncio.gather(
                piggy_bank.contribute_to_piggy_bank(101, 10, 999),
                piggy_bank.contribute_to_piggy_bank(202, 10, 999),
            )

        results = asyncio.run(contribute_together())

        self.assertEqual(sum(result["triggered"] for result in results), 1)
        self.assertEqual(asyncio.run(piggy_bank.get_piggy_bank_state())["balance"], 10)
        with sqlite3.connect(self.db_path) as db:
            admin_balance = db.execute(
                "SELECT balance FROM users WHERE user_id = 999"
            ).fetchone()[0]
        self.assertEqual(admin_balance, 10)


if __name__ == "__main__":
    unittest.main()
