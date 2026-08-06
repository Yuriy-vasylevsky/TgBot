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
            "card_candidates": [
                {
                    "role": "recipient",
                    "visible_suffix": "2296",
                    "context_label": "Отримувач",
                    "evidence_text": "Отримувач **** 2296",
                }
            ],
            "recipient_card_suffix": "2296",
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

    def evaluate_with_cards(self, cards, **changes):
        analysis = PaymentReceiptAnalysis(**(self.valid_data | changes))
        return evaluate_auto_approval(
            analysis,
            expected_amount=200,
            allowed_card_last4=set(cards),
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

    def test_common_day_first_datetime_formats_are_supported(self):
        values = (
            "04.08.2026 14:30",
            "04.08.2026, 14:30:15",
            "04/08/2026 14:30",
            "14:30 04-08-2026",
        )
        for value in values:
            with self.subTest(value=value):
                result = self.evaluate(
                    payment_datetime=value,
                    payment_time_visible_text=value,
                )
                self.assertTrue(result[0], result[1])

    def test_success_screen_with_correct_data_is_approved(self):
        result = self.evaluate(
            is_payment_receipt=False,
            document_type="transfer_success_screen",
        )
        self.assertTrue(result[0])

    def test_payment_details_screen_with_correct_data_is_approved(self):
        result = self.evaluate(
            is_payment_receipt=False,
            document_type="payment_details_screen",
        )
        self.assertTrue(result[0])

    def test_bank_notification_is_not_approved(self):
        result = self.evaluate(
            is_payment_receipt=False,
            document_type="bank_notification",
        )
        self.assertFalse(result[0])

    def test_failed_receipt_is_not_approved(self):
        self.assertFalse(self.evaluate(payment_status="failed")[0])

    def test_sender_card_cannot_be_used_as_recipient(self):
        result = self.evaluate(
            recipient_card_suffix="2296",
            card_candidates=[
                {
                    "role": "sender",
                    "visible_suffix": "2296",
                    "context_label": "Платник",
                    "evidence_text": "Картка платника **** 2296",
                },
                {
                    "role": "recipient",
                    "visible_suffix": "5327",
                    "context_label": "Отримувач",
                    "evidence_text": "Картка отримувача **** 5327",
                },
            ],
        )
        self.assertFalse(result[0])

    def test_recipient_role_requires_recipient_label_evidence(self):
        result = self.evaluate(
            card_candidates=[
                {
                    "role": "recipient",
                    "visible_suffix": "2296",
                    "context_label": "Платник",
                    "evidence_text": "Картка платника **** 2296",
                }
            ]
        )
        self.assertFalse(result[0])

    def test_phone_status_bar_time_is_allowed_on_a_receipt(self):
        result = self.evaluate(
            payment_datetime="14:30",
            payment_time_source="phone_status_bar",
            payment_time_visible_text="14:30",
        )
        self.assertTrue(result[0])

    def test_two_visible_card_digits_are_allowed_when_unique(self):
        result = self.evaluate_with_cards(
            {"2296", "8204"},
            recipient_card_suffix="96",
            card_candidates=[
                {
                    "role": "recipient",
                    "visible_suffix": "96",
                    "context_label": "Отримувач",
                    "evidence_text": "Картка отримувача **96",
                }
            ],
        )
        self.assertTrue(result[0])

    def test_two_visible_card_digits_are_rejected_when_ambiguous(self):
        result = self.evaluate_with_cards(
            {"2296", "7496"},
            recipient_card_suffix="96",
            card_candidates=[
                {
                    "role": "recipient",
                    "visible_suffix": "96",
                    "context_label": "Отримувач",
                    "evidence_text": "Картка отримувача **96",
                }
            ],
        )
        self.assertFalse(result[0])

    def test_two_visible_card_digits_must_match_an_active_card(self):
        result = self.evaluate_with_cards(
            {"2296", "8204"},
            recipient_card_suffix="77",
            card_candidates=[
                {
                    "role": "recipient",
                    "visible_suffix": "77",
                    "context_label": "Отримувач",
                    "evidence_text": "Картка отримувача **77",
                }
            ],
        )
        self.assertFalse(result[0])


if __name__ == "__main__":
    unittest.main()
