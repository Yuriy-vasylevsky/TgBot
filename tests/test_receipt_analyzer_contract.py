import ast
import inspect
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from services.receipt_analyzer import (
    PaymentReceiptAnalysis,
    analyze_receipt_with_openai,
    evaluate_auto_approval,
)


class ReceiptAnalyzerContractTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 8, 4, 14, 30, tzinfo=ZoneInfo("Europe/Kyiv"))
        self.valid_data = {
            "is_payment_receipt": True,
            "document_type": "payment_receipt",
            "payment_status": "successful",
            "amount_found": 200,
            "recipient_card_last4": "2296",
            "payment_datetime": "2026-08-04T14:30:00+03:00",
            "payment_time_source": "operation",
            "payment_time_visible_text": "04.08.2026 14:30",
            "image_is_readable": True,
            "possible_editing": False,
            "confidence": 1.0,
            "reason": "Дані прочитано",
        }

    def evaluate(self, **changes):
        analysis = PaymentReceiptAnalysis(**(self.valid_data | changes))
        return evaluate_auto_approval(
            analysis,
            expected_amount=200,
            allowed_card_last4={"2296"},
            now_kyiv=self.now,
            max_time_difference_minutes=10,
        )

    def test_wallet_call_matches_analyzer_signature(self):
        project_root = Path(__file__).resolve().parents[1]
        wallet_tree = ast.parse(
            (project_root / "handlers" / "wallet.py").read_text(encoding="utf-8")
        )
        calls = [
            node
            for node in ast.walk(wallet_tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "analyze_receipt_with_openai"
        ]
        self.assertEqual(len(calls), 1)

        passed_keywords = {keyword.arg for keyword in calls[0].keywords if keyword.arg}
        signature = inspect.signature(analyze_receipt_with_openai)
        accepted_keywords = set(signature.parameters)
        required_keywords = {
            name
            for name, parameter in signature.parameters.items()
            if parameter.default is inspect.Parameter.empty
        }

        self.assertEqual(passed_keywords, required_keywords)
        self.assertLessEqual(passed_keywords, accepted_keywords)

    def test_valid_payment_receipt_is_approved(self):
        self.assertTrue(self.evaluate()[0])

    def test_missing_visible_time_is_sent_to_manual_review(self):
        result = self.evaluate(
            payment_datetime=None,
            payment_time_source="not_visible",
            payment_time_visible_text=None,
        )
        self.assertFalse(result[0])

    def test_datetime_must_match_visible_time_evidence(self):
        result = self.evaluate(payment_time_visible_text="04.08.2026 13:00")
        self.assertFalse(result[0])

    def test_success_screen_is_not_a_payment_receipt(self):
        result = self.evaluate(
            is_payment_receipt=False,
            document_type="transfer_success_screen",
        )
        self.assertFalse(result[0])

    def test_failed_receipt_is_not_approved(self):
        self.assertFalse(self.evaluate(payment_status="failed")[0])

    def test_phone_status_bar_time_is_allowed_on_a_receipt(self):
        result = self.evaluate(
            payment_datetime="14:30",
            payment_time_source="phone_status_bar",
            payment_time_visible_text="14:30",
        )
        self.assertTrue(result[0])


if __name__ == "__main__":
    unittest.main()
