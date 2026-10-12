import unittest
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from admin import jackpot_rain as rain


class JackpotRainTests(unittest.IsolatedAsyncioTestCase):
    async def test_only_matic_checks_with_money_are_shown(self):
        checks = [dict(user_id=i, platform="Matic", code=f"{i:014d}",
                       full_name="Name <test>", username="player") for i in range(4)]
        message = SimpleNamespace(from_user=SimpleNamespace(id=rain.ADMIN_ID), answer=AsyncMock())
        with patch.object(rain, "get_issued_checks_with_owners", AsyncMock(return_value=checks)) as query, \
             patch.object(rain, "get_matic_api", return_value=SimpleNamespace(
                 get_balance_by_code=AsyncMock(side_effect=[Decimal("12.50"), 25, 0, None]))):
            await rain.jackpot_rain(message)
        query.assert_awaited_once_with("Matic")
        text = message.answer.call_args.args[0]
        self.assertIn("37.50 грн", text)
        self.assertIn("Активних із коштами: <b>2</b>", text)
        self.assertIn("Не вдалося перевірити: 1", text)
        self.assertIn("Name &lt;test&gt;", text)
        self.assertIn("tg://user?id=1", text)
        self.assertNotIn("<code>00000000000002</code>", text)

    async def test_denies_non_admin_without_reading_checks(self):
        message = SimpleNamespace(from_user=SimpleNamespace(id=rain.ADMIN_ID + 1), answer=AsyncMock())
        with patch.object(rain, "get_issued_checks_with_owners", AsyncMock()) as query:
            await rain.jackpot_rain(message)
            query.assert_not_awaited()

    async def test_reports_empty_local_check_database(self):
        message = SimpleNamespace(from_user=SimpleNamespace(id=rain.ADMIN_ID), answer=AsyncMock())
        with patch.object(rain, "get_issued_checks_with_owners", AsyncMock(return_value=[])), \
             patch.object(rain, "get_matic_api") as api:
            await rain.jackpot_rain(message)
        api.assert_not_called()
        self.assertIn("немає жодного", message.answer.call_args.args[0])

    async def test_invalid_balance_is_unverified(self):
        for value in ("NaN", "Infinity", None):
            with patch.object(rain, "get_matic_api", return_value=SimpleNamespace(
                    get_balance_by_code=AsyncMock(return_value=value))):
                self.assertIsNone(await rain.check_balance({"platform": "Matic", "code": "x"}))

    async def test_missing_matic_terminal_is_closed(self):
        with patch.object(rain, "get_matic_api", return_value=SimpleNamespace(
                get_balance_by_code=AsyncMock(side_effect=Exception("no such terminal")))):
            self.assertIsNone(await rain.check_balance({"platform": "Matic", "code": "12345678901234"}))

    async def test_large_list_is_split_into_telegram_messages(self):
        checks = [dict(user_id=i, platform="Matic", code=f"{i:014d}", full_name="Player", username=None)
                  for i in range(70)]
        message = SimpleNamespace(from_user=SimpleNamespace(id=rain.ADMIN_ID), answer=AsyncMock())
        with patch.object(rain, "get_issued_checks_with_owners", AsyncMock(return_value=checks)), \
             patch.object(rain, "check_balance", AsyncMock(return_value=Decimal("0.50"))):
            await rain.jackpot_rain(message)
        pages = [call.args[0] for call in message.answer.call_args_list]
        self.assertGreater(len(pages), 1)
        self.assertTrue(all(len(page) <= 3500 for page in pages))
        self.assertEqual(sum(page.count("🔑") for page in pages), 70)
