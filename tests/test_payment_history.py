import tempfile
import unittest
import sys
from pathlib import Path

import aiosqlite

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import db.wallet as wallet
from db.core import ensure_manual_payment_daily_numbering


class PaymentHistoryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.old_db_path = wallet.DB_PATH
        wallet.DB_PATH = Path(self.temp_dir.name) / "payments.db"
        async with aiosqlite.connect(wallet.DB_PATH) as db:
            await db.executescript(
                """
                CREATE TABLE users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    full_name TEXT,
                    balance INTEGER DEFAULT 0,
                    daily_net INTEGER DEFAULT 0,
                    yesterday_net INTEGER DEFAULT 0,
                    last_net_date TEXT,
                    cashback_claimed_base INTEGER DEFAULT 0,
                    promo_claimed_base INTEGER DEFAULT 0,
                    total_losses_all_time INTEGER DEFAULT 0
                );
                CREATE TABLE manual_payment_daily_sequences (
                    payment_date TEXT PRIMARY KEY,
                    last_number INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE pending_payments (
                    user_id INTEGER PRIMARY KEY,
                    amount_kop INTEGER NOT NULL,
                    comment TEXT UNIQUE NOT NULL,
                    created_at REAL NOT NULL,
                    mono_account TEXT DEFAULT '0'
                );
                CREATE TABLE manual_payments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    username TEXT,
                    full_name TEXT,
                    amount INTEGER NOT NULL,
                    receipt_file_id TEXT NOT NULL,
                    receipt_type TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TEXT,
                    reviewed_at TEXT,
                    reviewed_by INTEGER,
                    review_source TEXT,
                    payment_date TEXT,
                    daily_number INTEGER
                );
                CREATE TABLE payment_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    username TEXT,
                    amount INTEGER,
                    comment TEXT,
                    created_at TEXT
                );
                """
            )
            await db.commit()

    async def asyncTearDown(self):
        wallet.DB_PATH = self.old_db_path
        self.temp_dir.cleanup()

    async def test_manual_daily_numbers_and_history_groups(self):
        first_id = await wallet.create_manual_payment(
            101, "first", "First User", 200, "file", "photo"
        )
        self.assertEqual(await wallet.get_manual_payment_daily_number(first_id), 1)

        await wallet.add_pending_payment(202, 30000, "PAYMENT:test", "0")

        approved = await wallet.review_manual_payment(
            first_id, 0, "approved", review_source="gpt"
        )
        self.assertTrue(approved["ok"])
        self.assertEqual(approved["daily_number"], 1)

        await wallet.add_payment_log(
            202,
            "second",
            300,
            "PAYMENT:test",
        )

        rejected_id = await wallet.create_manual_payment(
            303, "third", "Third User", 400, "file", "photo"
        )
        self.assertEqual(await wallet.get_manual_payment_daily_number(rejected_id), 2)
        rejected = await wallet.review_manual_payment(
            rejected_id, 999, "rejected"
        )
        self.assertTrue(rejected["ok"])

        summary = await wallet.get_payment_history_summary(0)
        self.assertEqual(summary["completed_count"], 2)
        self.assertEqual(summary["approved_count"], 1)
        self.assertEqual(summary["approved_total"], 200)
        self.assertEqual(summary["rejected_count"], 1)
        self.assertEqual(summary["active_count"], 0)

        entries, total_pages = await wallet.get_payment_history_page(
            0, "completed", 1, 10
        )
        self.assertEqual(total_pages, 1)
        self.assertEqual([entry["daily_number"] for entry in entries], [2, 1])
        self.assertEqual(
            [entry["status"] for entry in entries],
            ["rejected", "approved"],
        )

        async with aiosqlite.connect(wallet.DB_PATH) as db:
            await db.execute("BEGIN IMMEDIATE")
            next_day_number = await wallet._next_manual_payment_number(
                db, "2099-01-02"
            )
            await db.commit()
        self.assertEqual(next_day_number, 1)

    async def test_legacy_rows_are_numbered_without_manual_log_duplicate(self):
        legacy_path = Path(self.temp_dir.name) / "legacy.db"
        async with aiosqlite.connect(legacy_path) as db:
            await db.executescript(
                """
                CREATE TABLE manual_payments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT
                );
                CREATE TABLE payment_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    comment TEXT,
                    created_at TEXT
                );
                CREATE TABLE pending_payments (
                    user_id INTEGER PRIMARY KEY,
                    created_at REAL
                );
                INSERT INTO manual_payments(created_at)
                VALUES ('2026-08-06 10:00:00');
                INSERT INTO payment_logs(comment, created_at)
                VALUES ('MANUAL:1', '2026-08-06 10:05:00');
                INSERT INTO payment_logs(comment, created_at)
                VALUES ('PAYMENT:auto', '2026-08-06 11:00:00');
                """
            )
            await ensure_manual_payment_daily_numbering(db)
            await ensure_manual_payment_daily_numbering(db)
            await db.commit()

            manual = await (
                await db.execute(
                    "SELECT payment_date, daily_number FROM manual_payments"
                )
            ).fetchone()
            payment_log_columns = {
                row[1]
                for row in await (await db.execute("PRAGMA table_info(payment_logs)"))
                .fetchall()
            }

        self.assertEqual(manual, ("2026-08-06", 1))
        self.assertNotIn("daily_number", payment_log_columns)


if __name__ == "__main__":
    unittest.main()
