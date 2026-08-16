import ast
import sys
import tempfile
import unittest
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import aiosqlite

import db.admin as admin_db


class ReceiptAutoapprovalBanTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.old_db_path = admin_db.DB_PATH
        admin_db.DB_PATH = Path(self.temp_dir.name) / "bans.db"
        async with aiosqlite.connect(admin_db.DB_PATH) as db:
            await db.execute(
                """
                CREATE TABLE users (
                    user_id INTEGER PRIMARY KEY,
                    full_name TEXT
                )
                """
            )
            await db.execute(
                "INSERT INTO users(user_id, full_name) VALUES (123, 'Test User')"
            )
            await db.commit()

    async def asyncTearDown(self):
        admin_db.DB_PATH = self.old_db_path
        self.temp_dir.cleanup()

    async def test_ban_check_list_and_unban(self):
        self.assertFalse(await admin_db.is_receipt_autoapproval_banned(123))

        await admin_db.ban_receipt_autoapproval_user(
            123,
            banned_by=999,
            reason="Ручна перевірка",
        )
        self.assertTrue(await admin_db.is_receipt_autoapproval_banned(123))

        rows = await admin_db.list_banned_receipt_autoapproval()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][:4], (123, "Test User", "Ручна перевірка", 999))

        await admin_db.unban_receipt_autoapproval_user(123)
        self.assertFalse(await admin_db.is_receipt_autoapproval_banned(123))

    def test_banned_user_is_routed_before_any_receipt_analysis(self):
        wallet_path = Path(__file__).resolve().parents[1] / "handlers" / "wallet.py"
        tree = ast.parse(wallet_path.read_text(encoding="utf-8"))
        process_function = next(
            node
            for node in tree.body
            if isinstance(node, ast.AsyncFunctionDef)
            and node.name == "_process_manual_receipt"
        )

        calls = [
            (node.lineno, node.func.id)
            for node in ast.walk(process_function)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        ]
        first_line = {
            name: min(line for line, call_name in calls if call_name == name)
            for name in {
                "is_receipt_autoapproval_banned",
                "download_and_prepare_receipt",
                "analyze_receipt_with_openai",
            }
        }
        self.assertLess(
            first_line["is_receipt_autoapproval_banned"],
            first_line["download_and_prepare_receipt"],
        )
        self.assertLess(
            first_line["is_receipt_autoapproval_banned"],
            first_line["analyze_receipt_with_openai"],
        )

    def test_large_manual_payment_requires_confirmation_before_card_details(self):
        wallet_path = Path(__file__).resolve().parents[1] / "handlers" / "wallet.py"
        source = wallet_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        process_function = next(
            node
            for node in tree.body
            if isinstance(node, ast.AsyncFunctionDef)
            and node.name == "process_amount"
        )
        large_amount_checks = [
            node
            for node in ast.walk(process_function)
            if isinstance(node, ast.Compare)
            and isinstance(node.left, ast.Name)
            and node.left.id == "amount_grn"
            and any(isinstance(operator, ast.Gt) for operator in node.ops)
            and any(
                isinstance(comparator, ast.Name)
                and comparator.id == "MAX_AMOUNT_FOR_GPT_CHECK"
                for comparator in node.comparators
            )
        ]

        self.assertEqual(len(large_amount_checks), 1)
        self.assertIn('callback_data="wallet_large_topup_continue"', source)
        self.assertIn('text="❌ Скасувати платіж"', source)
        self.assertIn("async def continue_large_manual_topup", source)


if __name__ == "__main__":
    unittest.main()
