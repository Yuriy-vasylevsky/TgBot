import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import services.receipt_analyzer as analyzer
import tests.test_receipt_analyzer_contract as fixtures


class ReceiptAnalysisFlowTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        fixtures.ReceiptAnalyzerContractTests.setUp(self)

    async def analyze(self, initial, evidence=None):
        responses = [SimpleNamespace(output_parsed=initial)]
        if evidence is not None:
            responses.append(SimpleNamespace(output_parsed=evidence))
        client = SimpleNamespace(
            responses=SimpleNamespace(parse=AsyncMock(side_effect=responses)),
            close=AsyncMock(),
        )
        with patch.object(analyzer, "AsyncOpenAI", return_value=client), patch.object(
            analyzer, "_build_receipt_detail_crops", return_value=[]
        ):
            result = await analyzer.analyze_receipt_with_openai(
                api_key="test-key", model="test-model", timeout_seconds=5,
                image=analyzer.PreparedReceipt(b"test-image", "image/jpeg", "hash", "phash"),
                now_kyiv=self.now,
            )
        client.close.assert_awaited_once()
        return result, client.responses.parse.await_count

    def evaluate(self, analysis):
        return analyzer.evaluate_auto_approval(
            analysis, expected_amount=200, allowed_card_last4={"2296"},
            now_kyiv=self.now, max_time_difference_minutes=10,
        )

    async def test_visible_time_missing_datetime_does_not_need_second_api_call(self):
        initial = analyzer.PaymentReceiptAnalysis(**(self.valid_data | {
            "payment_datetime": None, "payment_time_source": "phone_status_bar",
            "payment_time_visible_text": "14:30",
        }))
        result, calls = await self.analyze(initial)
        self.assertEqual(calls, 1)
        self.assertTrue(self.evaluate(result)[0])

    async def test_missed_time_is_rechecked_and_accepted_with_visible_evidence(self):
        initial = analyzer.PaymentReceiptAnalysis(**(self.valid_data | {
            "payment_datetime": None, "payment_time_source": "not_visible",
            "payment_time_visible_text": None,
        }))
        evidence = analyzer.PaymentTimeEvidence(
            time_is_visible=True, source="phone_status_bar",
            payment_datetime=None, visible_text="14:30", confidence=1,
            reason="Час чітко видно",
        )
        result, calls = await self.analyze(initial, evidence)
        self.assertEqual(calls, 2)
        self.assertTrue(self.evaluate(result)[0])

    async def test_no_time_after_recheck_is_not_approved(self):
        initial = analyzer.PaymentReceiptAnalysis(**(self.valid_data | {
            "payment_time_source": "not_visible", "payment_time_visible_text": None,
        }))
        evidence = analyzer.PaymentTimeEvidence(
            time_is_visible=False, source="not_visible", payment_datetime=None,
            visible_text=None, confidence=1, reason="Час відсутній",
        )
        result, calls = await self.analyze(initial, evidence)
        self.assertEqual(calls, 2)
        self.assertFalse(self.evaluate(result)[0])
        self.assertIsNone(result.payment_datetime)
