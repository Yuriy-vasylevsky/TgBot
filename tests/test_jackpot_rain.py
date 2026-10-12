import unittest
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from admin import jackpot_rain as rain


class JackpotRainTests(unittest.IsolatedAsyncioTestCase):
    async def test_both_platforms_filter_and_report_failures(self):
        checks = [
            dict(user_id=i, platform=platform, code=str(i),
                 full_name="Name <test>", username="player")
            for i, platform in enumerate(["Champion", "Matic", "Matic", "Champion"])
        ]
        message = SimpleNamespace(
            from_user=SimpleNamespace(id=rain.ADMIN_ID), answer=AsyncMock()
        )
        with patch.object(rain, "get_issued_checks_with_owners", AsyncMock(return_value=checks)), \
             patch.object(rain, "check_invoice", AsyncMock(side_effect=[{"success": True, "sum": "12.50"}, {}])), \
             patch.object(rain, "get_matic_api", return_value=SimpleNamespace(
                 get_balance_by_code=AsyncMock(side_effect=[25, -1])
             )):
            await rain.jackpot_rain(message)
        text = message.answer.call_args.args[0]
        self.assertIn("37.50 грн", text)
        self.assertIn("Активних із коштами: <b>2</b>", text)
        self.assertIn("Не вдалося перевірити: 1", text)
        self.assertIn("Name &lt;test&gt;", text)
        self.assertIn("tg://user?id=1", text)
        self.assertNotIn("<code>2</code>", text)

    async def test_denies_non_admin_without_reading_checks(self):
        message = SimpleNamespace(
            from_user=SimpleNamespace(id=rain.ADMIN_ID + 1), answer=AsyncMock()
        )
        with patch.object(rain, "get_issued_checks_with_owners", AsyncMock()) as query:
            await rain.jackpot_rain(message)
            query.assert_not_awaited()

    async def test_invalid_balance_is_unverified(self):
        for value in ("NaN", "Infinity", None):
            with patch.object(rain, "check_invoice", AsyncMock(return_value={"success": True, "sum": value})):
                self.assertIsNone(await rain.check_balance({"platform": "Champion", "code": "x"}))

    async def test_large_list_is_split_into_telegram_messages(self):
        checks = [dict(user_id=i, platform="Champion", code=str(i), full_name="Player", username=None)
                  for i in range(70)]
        message = SimpleNamespace(from_user=SimpleNamespace(id=rain.ADMIN_ID), answer=AsyncMock())
        with patch.object(rain, "get_issued_checks_with_owners", AsyncMock(return_value=checks)), \
             patch.object(rain, "check_balance", AsyncMock(return_value=Decimal("0.50"))):
            await rain.jackpot_rain(message)
        pages = [call.args[0] for call in message.answer.call_args_list[1:]]
        self.assertGreater(len(pages), 1)
        self.assertTrue(all(len(page) <= 3500 for page in pages))
        self.assertEqual(sum(page.count("🔑") for page in pages), 70)
