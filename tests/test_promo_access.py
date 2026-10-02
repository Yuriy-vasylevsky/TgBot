import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import aiosqlite

from db import core, wallet
from db.promo_access import KYIV, ensure_deposits, get_access, migrate_deposits, record_deposit


class PromoAccessTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.path = Path(self.temp.name) / "test.db"
        self.now = datetime(2026, 10, 2, 15, 0, tzinfo=KYIV).timestamp()
        self.patches = [patch.object(core, "DB_PATH", self.path), patch.object(wallet, "DB_PATH", self.path)]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)
        await core.ensure_users_table_and_columns()
        async with aiosqlite.connect(self.path) as db:
            await ensure_deposits(db)
            await db.execute("INSERT INTO users(user_id) VALUES (1)")
            await db.commit()

    async def asyncTearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.temp.cleanup()

    async def credit(self, timestamp, amount=500):
        async with aiosqlite.connect(self.path) as db:
            with patch("db.promo_access.time.time", return_value=timestamp):
                await record_deposit(db, 1, amount)
            await db.commit()

    async def test_exact_24_hour_boundary_and_new_deposit(self):
        self.assertFalse((await get_access(self.path, 1, now=self.now))["active"])
        await self.credit(self.now - 86400)
        self.assertTrue((await get_access(self.path, 1, now=self.now - 1))["active"])
        self.assertFalse((await get_access(self.path, 1, now=self.now))["active"])
        await self.credit(self.now, 200)
        access = await get_access(self.path, 1, now=self.now)
        self.assertEqual(access["remaining_seconds"], 86400)
        self.assertEqual(access["deposits"], 700)

    async def test_withdrawal_does_not_change_access_or_payout_limit(self):
        await self.credit(self.now - 60)
        with patch("db.promo_access.time.time", return_value=self.now):
            await wallet.add_daily_game_win(1, 50)
            before = await wallet.get_available_game_win(1)
            await wallet.update_daily_net(1, -1000)
            after = await wallet.get_available_game_win(1)
            self.assertEqual(before, 150)
            self.assertEqual(after, before)
            self.assertTrue(await wallet.has_recent_deposit(1))
            self.assertEqual((await wallet.can_receive_prize(1, 150))[0], True)
            self.assertEqual((await wallet.can_receive_prize(1, 151))[0], False)

    async def test_expired_deposit_gives_no_cash_limit(self):
        await self.credit(self.now - 86400)
        with patch("db.promo_access.time.time", return_value=self.now):
            self.assertEqual(await wallet.get_available_game_win(1), 0)
            self.assertFalse((await wallet.can_receive_prize(1, 30))[0])

    async def test_manual_credit_starts_window_but_bonus_balance_does_not(self):
        with patch("db.promo_access.time.time", return_value=self.now):
            await wallet.add_to_balance(1, 50)
            self.assertFalse(await wallet.has_recent_deposit(1))
            await wallet.update_daily_net(1, 200, deposit=True)
            self.assertTrue(await wallet.has_recent_deposit(1))
            self.assertEqual(await wallet.get_promo_deposit_base(1), 200)

    async def test_clock_window_is_86400_seconds_across_dst(self):
        timestamp = datetime(2026, 10, 24, 15, tzinfo=KYIV).timestamp()
        await self.credit(timestamp)
        self.assertTrue((await get_access(self.path, 1, now=timestamp + 86399))["active"])
        self.assertFalse((await get_access(self.path, 1, now=timestamp + 86400))["active"])

    async def test_legacy_migration_is_idempotent(self):
        path = Path(self.temp.name) / "legacy.db"
        async with aiosqlite.connect(path) as db:
            await db.execute("CREATE TABLE payment_logs(user_id INTEGER, amount INTEGER, created_at TEXT)")
            await db.execute("INSERT INTO payment_logs VALUES (1, 500, '2026-10-02 15:00:00')")
            await db.execute("INSERT INTO payment_logs VALUES (1, -200, '2026-10-02 15:01:00')")
            await migrate_deposits(db)
            await migrate_deposits(db)
            await db.commit()
        access = await get_access(path, 1, now=self.now)
        self.assertEqual(access["deposits"], 500)
        self.assertEqual(access["remaining_seconds"], 86400)
