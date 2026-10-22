import json
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import handlers.wallet as wallet


class CashDeskTests(unittest.TestCase):
    def test_schedule_boundaries_in_winter_and_summer(self):
        with patch.object(wallet, "_cash_desk_mode", "auto"):
            for month in (1, 7):
                for hour, minute, expected in (
                    (0, 0, False), (8, 59, False),
                    (9, 0, True), (23, 59, True),
                ):
                    local = datetime(2026, month, 15, hour, minute,
                                     tzinfo=wallet.KYIV_ZONE)
                    with self.subTest(month=month, hour=hour, minute=minute):
                        self.assertEqual(
                            wallet.is_cash_desk_open(local.astimezone(timezone.utc)),
                            expected,
                        )

    def test_manual_modes_override_schedule(self):
        for mode, expected in (("open", True), ("closed", False)):
            with patch.object(wallet, "_cash_desk_mode", mode):
                for hour in (0, 12):
                    self.assertEqual(wallet.is_cash_desk_open(
                        datetime(2026, 1, 15, hour, tzinfo=wallet.KYIV_ZONE)
                    ), expected)

    def test_mode_saved_with_existing_payment_settings(self):
        settings_file = Mock(spec=Path)
        with patch.object(wallet, "_SETTINGS_FILE", settings_file), patch.object(
            wallet, "_cash_desk_mode", "closed"
        ):
            wallet._save_wallet_settings()
            saved = json.loads(settings_file.write_text.call_args.args[0])
            self.assertEqual(saved["cash_desk_mode"], "closed")
            self.assertIn("autopay_mode", saved)
            self.assertIn("crypto_pay_enabled", saved)


class CashDeskFlowTests(unittest.IsolatedAsyncioTestCase):
    async def test_closed_desk_blocks_every_new_payment_entry(self):
        for handler in (
            wallet.start_topup, wallet.start_crypto_topup,
            wallet.replace_pending_with_crypto, wallet.process_amount,
            wallet.continue_large_manual_topup,
        ):
            event, state = AsyncMock(), AsyncMock()
            with self.subTest(handler=handler.__name__), patch.object(
                wallet, "_cash_desk_mode", "closed"
            ):
                await handler(event, state)
                state.clear.assert_awaited_once()
                event.answer.assert_awaited_once()
                state.get_data.assert_not_awaited()
                state.set_state.assert_not_awaited()

    async def test_non_admin_cannot_change_mode(self):
        callback = AsyncMock()
        callback.from_user.id = -1
        with patch.object(wallet, "_save_wallet_settings") as save:
            await wallet.set_cash_desk_mode(callback)
            save.assert_not_called()
            callback.answer.assert_awaited_once()
