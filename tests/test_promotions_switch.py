import unittest
from uuid import uuid4
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch

import aiosqlite
from aiogram import types

from handlers.menu import main_menu, actions_menu, admin_menu2
from middlewares.promotions import PromotionsMiddleware
from services import promotions


class PromotionsSwitchTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.path = Path(__file__).resolve().parent.parent / ".tmp" / f"promotions-{uuid4().hex}.db"
        self.patch = patch.object(promotions, "DB_PATH", self.path)
        self.patch.start()
        self.previous = promotions._enabled
        self.previous_piggy = promotions._piggy_enabled
        promotions._piggy_enabled = True
        async with aiosqlite.connect(self.path) as db:
            await db.execute("CREATE TABLE settings(key TEXT PRIMARY KEY, value REAL)")
            await db.commit()

    async def asyncTearDown(self):
        promotions._enabled = self.previous
        promotions._piggy_enabled = self.previous_piggy
        self.patch.stop()
        self.path.unlink(missing_ok=True)

    async def test_persistence_and_restore_all_keyboard_entries(self):
        self.assertTrue(await promotions.load_promotions())
        menus = [main_menu, actions_menu, admin_menu2]
        originals = [make().model_dump() for make in menus]
        await promotions.set_promotions(False)
        promotions._enabled = True
        self.assertFalse(await promotions.load_promotions())
        for make in menus:
            for row in make().keyboard:
                self.assertTrue(row)
                self.assertFalse(any(b.text in promotions.PROMO_BUTTONS for b in row))
        await promotions.set_promotions(True)
        self.assertEqual([make().model_dump() for make in menus], originals)

    async def test_pending_redemption_blocked_and_state_cleared(self):
        await promotions.set_promotions(False)
        event = types.Message(
            message_id=1, date=datetime.now(), chat=types.Chat(id=1, type="private"),
            from_user=types.User(id=1, is_bot=False, first_name="Test"), text="OLD-CODE",
        )
        state = AsyncMock()
        state.get_state.return_value = "EnterPromoFSM:waiting_for_code"
        handler = AsyncMock()
        with patch.object(types.Message, "answer", new_callable=AsyncMock) as answer:
            await PromotionsMiddleware()(handler, event, {"state": state})
        handler.assert_not_awaited()
        state.clear.assert_awaited_once()
        answer.assert_awaited_once()

    async def test_stale_spin_blocked_but_cashback_allowed(self):
        await promotions.set_promotions(False)
        middleware = PromotionsMiddleware()
        for value, blocked in [("fortune:spin", True), ("profile:claim_cashback", False)]:
            event = types.CallbackQuery(
                id="test", from_user=types.User(id=1, is_bot=False, first_name="Test"),
                chat_instance="test", data=value,
            )
            handler = AsyncMock()
            with patch.object(types.CallbackQuery, "answer", new_callable=AsyncMock):
                await middleware(handler, event, {})
            self.assertEqual(handler.await_count, 0 if blocked else 1)

    async def test_profile_and_fortune_buttons_hidden(self):
        from handlers.profile import profile_keyboard
        from games.fortune import fortune_keyboard
        await promotions.set_promotions(False)
        callbacks = [b.callback_data for row in profile_keyboard().inline_keyboard for b in row]
        self.assertEqual(callbacks, ["profile:claim_cashback"])
        self.assertEqual(fortune_keyboard().inline_keyboard, [])
        await promotions.set_promotions(True)
        self.assertEqual(len(profile_keyboard().inline_keyboard), 3)
        self.assertEqual(len(fortune_keyboard().inline_keyboard), 3)

    async def test_switch_rejects_non_admin(self):
        from admin.promotions import toggle_promotions, ADMIN_ID
        event = types.CallbackQuery(
            id="test", from_user=types.User(id=ADMIN_ID + 1, is_bot=False, first_name="Test"),
            chat_instance="test", data="promotions:set:0",
        )
        await promotions.set_promotions(True)
        with patch.object(types.CallbackQuery, "answer", new_callable=AsyncMock):
            await toggle_promotions(event)
        self.assertTrue(promotions.promotions_enabled())

    async def test_piggy_switch_persists_independently_and_hides_buttons(self):
        from handlers.piggy_bank import piggy_bank_keyboard
        await promotions.set_promotions(True)
        await promotions.set_piggy_bank(False)
        promotions._piggy_enabled = True
        await promotions.load_promotions()
        self.assertFalse(promotions.piggy_bank_enabled())
        self.assertTrue(promotions.promotions_enabled())
        buttons = [b.text for row in main_menu().keyboard for b in row]
        self.assertNotIn("🐷 Скарбничка", buttons)
        self.assertIn("🎟 Ввести промокод", buttons)
        self.assertEqual(piggy_bank_keyboard({}).inline_keyboard, [])
        await promotions.set_promotions(False)
        await promotions.set_piggy_bank(True)
        buttons = [b.text for row in main_menu().keyboard for b in row]
        self.assertIn("🐷 Скарбничка", buttons)
        self.assertNotIn("🎟 Ввести промокод", buttons)
        self.assertTrue(piggy_bank_keyboard({}).inline_keyboard)

    async def test_disabled_piggy_blocks_old_contribution_and_allows_admin_settings(self):
        await promotions.set_promotions(True)
        await promotions.set_piggy_bank(False)
        for value, blocked in [("piggy:add:10", True), ("piggy:refresh", True),
                               ("piggy_admin:refresh", False), ("fortune:spin", False)]:
            event = types.CallbackQuery(
                id="test", from_user=types.User(id=1, is_bot=False, first_name="Test"),
                chat_instance="test", data=value,
            )
            handler = AsyncMock()
            with patch.object(types.CallbackQuery, "answer", new_callable=AsyncMock):
                await PromotionsMiddleware()(handler, event, {})
            self.assertEqual(handler.await_count, 0 if blocked else 1)
