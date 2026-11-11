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
    async def test_darts_requires_deactivation_and_persists(self):
        with patch.object(promotions, '_daily_darts_enabled', False):
            with self.assertRaises(ValueError):
                await promotions.set_daily_darts(True)
            await promotions.set_daily_fortune(False)
            await promotions.set_daily_darts(True)
            with self.assertRaises(ValueError):
                await promotions.set_daily_fortune(True)
            promotions._daily_darts_enabled = False
            await promotions.load_promotions()
            self.assertTrue(promotions.daily_darts_enabled())
            self.assertFalse(promotions.daily_fortune_enabled())
            from handlers.daily_fortune import open_daily_bonus
            message = AsyncMock()
            with patch('handlers.daily_fortune.open_darts', new_callable=AsyncMock) as darts:
                await open_daily_bonus(message)
                darts.assert_awaited_once_with(message)
            await promotions.set_daily_darts(False)
            await promotions.set_daily_fortune(True)

    async def test_daily_bonus_opens_game_directly_or_reports_unavailable(self):
        from handlers.daily_fortune import open_daily_bonus
        message = AsyncMock()
        message.from_user.id = 1
        with patch('handlers.daily_fortune.fortune_status', new_callable=AsyncMock) as status:
            status.return_value = {'success': True, 'deposit_amount': 100}
            await promotions.set_daily_fortune(True)
            await open_daily_bonus(message)
            message.answer_photo.assert_awaited_once()
            await promotions.set_daily_fortune(False)
            status.reset_mock()
            await open_daily_bonus(message)
            status.assert_not_awaited()
            message.answer.assert_awaited_once()

    async def test_fortune_toggle_does_not_broadcast_menu(self):
        from types import SimpleNamespace
        from admin import promotions as admin_promotions
        callback = SimpleNamespace(
            from_user=SimpleNamespace(id=admin_promotions.ADMIN_ID),
            data='promotions:daily_fortune:0', answer=AsyncMock(),
            message=SimpleNamespace(edit_reply_markup=AsyncMock()),
        )
        with patch.object(admin_promotions, '_update_task', None), patch.object(
            admin_promotions, 'refresh_menus', new_callable=AsyncMock
        ) as refresh:
            await admin_promotions.toggle_promotions(callback)
            refresh.assert_not_called()
        self.assertFalse(promotions.daily_fortune_enabled())

    async def asyncSetUp(self):
        self.path = Path(__file__).resolve().parent.parent / ".tmp" / f"promotions-{uuid4().hex}.db"
        self.patch = patch.object(promotions, "DB_PATH", self.path)
        self.patch.start()
        self.previous = promotions._enabled
        self.previous_piggy = promotions._piggy_enabled
        self.previous_fortune = promotions._daily_fortune_enabled
        promotions._daily_fortune_enabled = True
        promotions._piggy_enabled = True
        async with aiosqlite.connect(self.path) as db:
            await db.execute("CREATE TABLE settings(key TEXT PRIMARY KEY, value REAL)")
            await db.commit()

    async def asyncTearDown(self):
        promotions._enabled = self.previous
        promotions._piggy_enabled = self.previous_piggy
        promotions._daily_fortune_enabled = self.previous_fortune
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

    async def test_daily_fortune_switch_persists_and_blocks_stale_roll(self):
        from handlers.daily_fortune import fortune_keyboard
        from admin.promotions import promotions_keyboard
        await promotions.set_daily_fortune(False)
        promotions._daily_fortune_enabled = True
        await promotions.load_promotions()
        self.assertFalse(promotions.daily_fortune_enabled())
        self.assertTrue(promotions.promotions_enabled())
        disabled_menu = main_menu().model_dump()
        self.assertIn('🎁 Щоденний бонус', [b.text for row in main_menu().keyboard for b in row])
        self.assertEqual(fortune_keyboard().inline_keyboard, [])
        self.assertTrue(any(b.callback_data == 'promotions:daily_fortune:1'
                            for row in promotions_keyboard().inline_keyboard for b in row))
        event = types.CallbackQuery(
            id='test', from_user=types.User(id=1, is_bot=False, first_name='Test'),
            chat_instance='test', data='daily_fortune:roll',
        )
        handler = AsyncMock()
        with patch.object(types.CallbackQuery, 'answer', new_callable=AsyncMock):
            await PromotionsMiddleware()(handler, event, {})
        handler.assert_not_awaited()
        await promotions.set_daily_fortune(True)
        self.assertEqual(main_menu().model_dump(), disabled_menu)
        self.assertTrue(fortune_keyboard().inline_keyboard)

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
