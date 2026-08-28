import ast
import io
import inspect
import json
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from PIL import Image

from services.receipt_analyzer import (
    CARD_MISMATCH_REASON,
    CANCELLABLE_PAYMENT_REASON,
    PaymentReceiptAnalysis,
    PaymentTimeEvidence,
    _apply_verified_time_evidence,
    _build_receipt_detail_crops,
    _detail_crop_boxes,
    _needs_time_recheck,
    _parse_json_response,
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
            "payment_status_visible_text": "Виконано успішно",
            "payment_can_be_cancelled": False,
            "cancellation_visible_text": None,
            "amount_found": 200,
            "card_candidates": [
                {
                    "role": "recipient",
                    "visible_suffix": "2296",
                    "context_label": "Отримувач",
                    "evidence_text": "Отримувач **** 2296",
                }
            ],
            "visible_card_number_suffixes": [],
            "recipient_card_suffix": "2296",
            "visible_ibans": [],
            "recipient_iban": None,
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

    def test_json_fallback_parses_openai_compatible_response(self):
        response = SimpleNamespace(
            output_text=json.dumps(
                {
                    "time_is_visible": False,
                    "source": "not_visible",
                    "payment_datetime": None,
                    "visible_text": None,
                    "confidence": 1.0,
                    "reason": "Час не видно",
                }
            )
        )
        evidence = _parse_json_response(response, PaymentTimeEvidence)
        self.assertIsInstance(evidence, PaymentTimeEvidence)
        self.assertFalse(evidence.time_is_visible)

    def test_portrait_receipt_is_split_into_overlapping_detail_bands(self):
        boxes = _detail_crop_boxes(600, 1200)

        self.assertEqual(len(boxes), 4)
        self.assertEqual(boxes[0][1], 0)
        self.assertEqual(boxes[-1][3], 1200)
        self.assertLess(boxes[1][1], boxes[0][3])

    def test_landscape_receipt_is_split_into_overlapping_detail_columns(self):
        boxes = _detail_crop_boxes(1200, 600)

        self.assertEqual(len(boxes), 3)
        self.assertEqual(boxes[0][0], 0)
        self.assertEqual(boxes[-1][2], 1200)
        self.assertLess(boxes[1][0], boxes[0][2])

    def test_detail_crops_are_enlarged_jpeg_images(self):
        source = io.BytesIO()
        Image.new("RGB", (300, 600), "white").save(source, format="JPEG")

        crops = _build_receipt_detail_crops(source.getvalue())

        self.assertEqual(len(crops), 5)
        with Image.open(io.BytesIO(crops[0])) as first_crop:
            self.assertEqual(first_crop.format, "JPEG")
            self.assertGreater(first_crop.width, 300)
            self.assertGreater(first_crop.width, first_crop.height * 3)

    def test_valid_payment_receipt_is_approved(self):
        self.assertTrue(self.evaluate()[0])

    def test_missing_visible_time_is_sent_to_manual_review(self):
        result = self.evaluate(
            payment_datetime=None,
            payment_time_source="not_visible",
            payment_time_visible_text=None,
        )
        self.assertFalse(result[0])

    def test_phone_status_bar_time_builds_missing_datetime(self):
        result = self.evaluate(
            payment_datetime=None,
            payment_time_source="phone_status_bar",
            payment_time_visible_text="15:06",
        )

        # 15:06 наступного дня/попереднього дня не може випадково пройти:
        # evaluate() має now=14:30, тому різниця становить 36 хвилин.
        self.assertFalse(result[0])
        self.assertEqual(result[2], 36)

        analysis = PaymentReceiptAnalysis(
            **(
                self.valid_data
                | {
                    "payment_datetime": None,
                    "payment_time_source": "phone_status_bar",
                    "payment_time_visible_text": "14:27",
                }
            )
        )
        approved = evaluate_auto_approval(
            analysis,
            expected_amount=200,
            allowed_card_last4={"2296"},
            now_kyiv=self.now,
            max_time_difference_minutes=10,
        )

        self.assertTrue(approved[0], approved[1])
        self.assertEqual(approved[2], 3)
        self.assertEqual(analysis.payment_datetime, "2026-08-04T14:27:00+03:00")

    def test_datetime_must_match_visible_time_evidence(self):
        result = self.evaluate(payment_time_visible_text="04.08.2026 13:00")
        self.assertFalse(result[0])

    def test_contradictory_not_visible_source_triggers_time_recheck(self):
        analysis = PaymentReceiptAnalysis(
            **(
                self.valid_data
                | {
                    "payment_datetime": "2026-08-04T14:30:00+03:00",
                    "payment_time_source": "not_visible",
                    "payment_time_visible_text": None,
                }
            )
        )

        self.assertTrue(_needs_time_recheck(analysis))
        _apply_verified_time_evidence(
            analysis,
            PaymentTimeEvidence(
                time_is_visible=True,
                source="operation",
                payment_datetime="2026-08-04T14:30:00+03:00",
                visible_text="04.08.2026 14:30",
                confidence=0.99,
                reason="Дата і час операції чітко видно",
            ),
        )

        result = evaluate_auto_approval(
            analysis,
            expected_amount=200,
            allowed_card_last4={"2296"},
            now_kyiv=self.now,
            max_time_difference_minutes=10,
        )
        self.assertTrue(result[0], result[1])
        self.assertEqual(analysis.payment_time_source, "operation")
        self.assertEqual(analysis.payment_time_visible_text, "04.08.2026 14:30")

    def test_failed_time_recheck_does_not_accept_unproven_datetime(self):
        analysis = PaymentReceiptAnalysis(
            **(
                self.valid_data
                | {
                    "payment_datetime": "2026-08-04T14:30:00+03:00",
                    "payment_time_source": "not_visible",
                    "payment_time_visible_text": None,
                }
            )
        )

        _apply_verified_time_evidence(
            analysis,
            PaymentTimeEvidence(
                time_is_visible=False,
                source="not_visible",
                payment_datetime=None,
                visible_text=None,
                confidence=0.9,
                reason="Час на зображенні не читається",
            ),
        )

        self.assertIsNone(analysis.payment_datetime)
        self.assertEqual(analysis.payment_time_source, "not_visible")
        self.assertFalse(
            evaluate_auto_approval(
                analysis,
                expected_amount=200,
                allowed_card_last4={"2296"},
                now_kyiv=self.now,
                max_time_difference_minutes=10,
            )[0]
        )

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
        self.assertFalse(
            self.evaluate(
                payment_status="failed",
                payment_status_visible_text="Помилка операції",
            )[0]
        )

    def test_visible_success_status_overrides_incorrect_unknown_status(self):
        result = self.evaluate(
            payment_status="unknown",
            payment_status_visible_text="Статус операції: Виконано успішно",
        )
        self.assertTrue(result[0], result[1])

    def test_negative_status_cannot_pass_by_containing_success_words(self):
        result = self.evaluate(
            payment_status="successful",
            payment_status_visible_text="Операцію не виконано успішно",
        )
        self.assertFalse(result[0])

    def test_processing_status_is_allowed_when_other_checks_match(self):
        result = self.evaluate(
            payment_status="processing",
            payment_status_visible_text="Статус операції: Очікує обробки",
        )
        self.assertTrue(result[0], result[1])

    def test_unknown_status_without_negative_text_is_allowed(self):
        result = self.evaluate(
            payment_status="unknown",
            payment_status_visible_text=None,
        )
        self.assertTrue(result[0], result[1])

    def test_explicit_rejected_status_remains_blocked(self):
        result = self.evaluate(
            payment_status="rejected",
            payment_status_visible_text="Статус операції: Відхилено",
        )
        self.assertFalse(result[0])

    def test_cancellable_payment_is_always_sent_to_manual_review(self):
        result = self.evaluate(
            payment_can_be_cancelled=True,
            cancellation_visible_text="Скасувати платіж",
        )
        self.assertFalse(result[0])
        self.assertEqual(result[1], CANCELLABLE_PAYMENT_REASON)

    def test_cancellation_text_blocks_even_if_boolean_is_wrong(self):
        result = self.evaluate(
            payment_can_be_cancelled=False,
            cancellation_visible_text="Скасувати платіж",
        )
        self.assertFalse(result[0])
        self.assertEqual(result[1], CANCELLABLE_PAYMENT_REASON)

    def test_active_card_in_sender_field_is_accepted_by_project_policy(self):
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
        self.assertTrue(result[0], result[1])

    def test_exact_hidden_iban_is_accepted_without_card_match(self):
        iban = "UA953077700000029241827505098"
        analysis = PaymentReceiptAnalysis(
            **(
                self.valid_data
                | {
                    "recipient_card_suffix": None,
                    "visible_card_number_suffixes": [],
                    "card_candidates": [],
                    "visible_ibans": [
                        " ".join(
                            iban[index:index + 4]
                            for index in range(0, len(iban), 4)
                        )
                    ],
                    "recipient_iban": None,
                }
            )
        )

        result = evaluate_auto_approval(
            analysis,
            expected_amount=200,
            allowed_card_last4={"2296"},
            allowed_ibans={iban},
            now_kyiv=self.now,
            max_time_difference_minutes=10,
        )

        self.assertTrue(result[0], result[1])
        self.assertEqual(analysis.recipient_iban, iban)

    def test_hidden_iban_is_accepted_by_last_four_digits(self):
        iban = "UA543077700000026202061068311"
        analysis = PaymentReceiptAnalysis(
            **(
                self.valid_data
                | {
                    "recipient_card_suffix": None,
                    "visible_card_number_suffixes": [],
                    "card_candidates": [],
                    "visible_ibans": ["UA953077700000029241827508311"],
                    "recipient_iban": "UA953077700000029241827508311",
                }
            )
        )

        result = evaluate_auto_approval(
            analysis,
            expected_amount=200,
            allowed_card_last4={"2296"},
            allowed_ibans={iban},
            now_kyiv=self.now,
            max_time_difference_minutes=10,
        )

        self.assertTrue(result[0], result[1])
        self.assertEqual(analysis.recipient_iban, iban)

    def test_nonduplicated_extra_iban_digit_is_not_accepted(self):
        iban = "UA543077700000026202061068311"
        analysis = PaymentReceiptAnalysis(
            **(
                self.valid_data
                | {
                    "recipient_card_suffix": None,
                    "visible_card_number_suffixes": [],
                    "card_candidates": [],
                    "visible_ibans": ["UA5430777000000262020610683119"],
                    "recipient_iban": None,
                }
            )
        )

        result = evaluate_auto_approval(
            analysis,
            expected_amount=200,
            allowed_card_last4={"2296"},
            allowed_ibans={iban},
            now_kyiv=self.now,
            max_time_difference_minutes=10,
        )

        self.assertFalse(result[0])
        self.assertIn("не збігаються", result[1])
        self.assertNotIn("не вдалось", result[1])

    def test_partial_or_different_iban_is_not_accepted(self):
        iban = "UA953077700000029241827505098"
        for visible_iban in ("UA95307770000002924182750", "UA953077700000029241827505099"):
            with self.subTest(visible_iban=visible_iban):
                analysis = PaymentReceiptAnalysis(
                    **(
                        self.valid_data
                        | {
                            "recipient_card_suffix": None,
                            "visible_card_number_suffixes": [],
                            "card_candidates": [],
                            "visible_ibans": [visible_iban],
                            "recipient_iban": None,
                        }
                    )
                )
                result = evaluate_auto_approval(
                    analysis,
                    expected_amount=200,
                    allowed_card_last4={"2296"},
                    allowed_ibans={iban},
                    now_kyiv=self.now,
                    max_time_difference_minutes=10,
                )
                self.assertFalse(result[0])

    def test_neutral_label_can_override_incorrect_sender_role(self):
        analysis = PaymentReceiptAnalysis(
            **(
                self.valid_data
                | {
                    "recipient_card_suffix": None,
                    "card_candidates": [
                        {
                            "role": "sender",
                            "visible_suffix": "2296",
                            "context_label": "Карточка (унікальний ідентифікатор)",
                            "evidence_text": "Карточка (унікальний ідентифікатор) **** 2296",
                        }
                    ],
                }
            )
        )
        result = evaluate_auto_approval(
            analysis,
            expected_amount=200,
            allowed_card_last4={"2296", "8204"},
            now_kyiv=self.now,
            max_time_difference_minutes=10,
        )
        self.assertTrue(result[0], result[1])
        self.assertEqual(analysis.recipient_card_suffix, "2296")

    def test_active_card_passes_even_when_label_says_payer(self):
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
        self.assertTrue(result[0], result[1])

    def test_e_wallet_recipient_number_is_accepted_despite_payer_lines(self):
        analysis = PaymentReceiptAnalysis(
            **(
                self.valid_data
                | {
                    "amount_found": 300,
                    "recipient_card_suffix": None,
                    "card_candidates": [
                        {
                            "role": "unknown",
                            "visible_suffix": "4323357031732296",
                            "context_label": (
                                "Номер рахунку/унікальний (повний) номер "
                                "платіжного інструменту/номер електронного "
                                "гаманця отримувача"
                            ),
                            "evidence_text": (
                                "Платник: Олександр. Телефон платника: "
                                "380994632456. Номер електронного гаманця "
                                "отримувача: 4323357031732296"
                            ),
                        }
                    ],
                }
            )
        )
        result = evaluate_auto_approval(
            analysis,
            expected_amount=300,
            allowed_card_last4={"2296", "8204"},
            now_kyiv=self.now,
            max_time_difference_minutes=10,
        )
        self.assertTrue(result[0], result[1])
        self.assertEqual(analysis.recipient_card_suffix, "2296")

    def test_nearest_role_marker_wins_in_long_receipt_fragment(self):
        result = self.evaluate(
            recipient_card_suffix=None,
            card_candidates=[
                {
                    "role": "unknown",
                    "visible_suffix": "2296",
                    "context_label": "Номер платіжного інструменту",
                    "evidence_text": (
                        "Платник: Олександр. Код платника 123. "
                        "Номер електронного гаманця отримувача: "
                        "4323357031732296"
                    ),
                }
            ],
        )
        self.assertTrue(result[0], result[1])

    def test_sender_marker_does_not_block_an_active_card(self):
        result = self.evaluate(
            recipient_card_suffix="2296",
            card_candidates=[
                {
                    "role": "recipient",
                    "visible_suffix": "2296",
                    "context_label": "Платіжний інструмент",
                    "evidence_text": (
                        "Картка платника: 4323357031732296. "
                        "Отримувач переказу має іншу картку 5327"
                    ),
                }
            ],
        )
        self.assertTrue(result[0], result[1])

    def test_generic_masked_card_field_from_abank_receipt_is_accepted(self):
        analysis = PaymentReceiptAnalysis(
            **(
                self.valid_data
                | {
                    "amount_found": 400,
                    "recipient_card_suffix": None,
                    "card_candidates": [
                        {
                            "role": "unknown",
                            "visible_suffix": "432335******2296",
                            "context_label": "Картка",
                            "evidence_text": "Картка: 432335******2296",
                        }
                    ],
                }
            )
        )
        result = evaluate_auto_approval(
            analysis,
            expected_amount=400,
            allowed_card_last4={"2296", "8204"},
            now_kyiv=self.now,
            max_time_difference_minutes=10,
        )
        self.assertTrue(result[0], result[1])
        self.assertEqual(analysis.recipient_card_suffix, "2296")

    def test_card_number_in_payment_purpose_is_accepted_when_gpt_mislabels_iban(self):
        analysis = PaymentReceiptAnalysis(
            **(
                self.valid_data
                | {
                    "amount_found": 300,
                    "recipient_card_suffix": "5098",
                    "visible_card_number_suffixes": ["2296"],
                    "card_candidates": [
                        {
                            "role": "sender",
                            "visible_suffix": "3296",
                            "context_label": "Картка платника",
                            "evidence_text": "Картка платника: ****3296",
                        },
                        {
                            "role": "recipient",
                            "visible_suffix": "5098",
                            "context_label": "IBAN отримувача",
                            "evidence_text": "IBAN: UA...5098",
                        },
                    ],
                }
            )
        )
        result = evaluate_auto_approval(
            analysis,
            expected_amount=300,
            allowed_card_last4={"2296", "8204"},
            now_kyiv=self.now,
            max_time_difference_minutes=10,
        )
        self.assertTrue(result[0], result[1])
        self.assertEqual(analysis.recipient_card_suffix, "2296")

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
