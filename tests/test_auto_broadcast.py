import asyncio
import unittest
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from unittest.mock import AsyncMock, patch

import aiosqlite
from aiogram import types
from db import auto_broadcast as store
from services import auto_broadcast as worker


class AutoBroadcastTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        folder = Path(__file__).resolve().parent.parent / '.tmp'
        folder.mkdir(exist_ok=True)
        self.path = folder / f'auto-broadcast-{uuid4().hex}.db'
        self.patch = patch.object(store, 'DB_PATH', self.path)
        self.patch.start()
        await store.init_auto_broadcast()
        async with aiosqlite.connect(self.path) as db:
            await db.execute('CREATE TABLE users(user_id INTEGER PRIMARY KEY)')
            await db.executemany('INSERT INTO users VALUES (?)', [(101,), (102,), (-123,)])
            await db.commit()

    async def asyncTearDown(self):
        self.patch.stop()
        self.path.unlink(missing_ok=True)

    async def due(self, bid):
        async with aiosqlite.connect(self.path) as db:
            await db.execute('UPDATE auto_broadcasts SET next_run=1 WHERE id=?', (bid,))
            await db.commit()

    async def test_daily_kyiv_time_and_dst(self):
        winter = datetime(2026, 1, 5, 10, tzinfo=timezone.utc)
        summer = datetime(2026, 7, 5, 10, tzinfo=timezone.utc)
        self.assertEqual(datetime.fromtimestamp(store.next_daily('18:30', winter), timezone.utc).hour, 16)
        self.assertEqual(datetime.fromtimestamp(store.next_daily('18:30', summer), timezone.utc).hour, 15)
        exact = datetime(2026, 1, 5, 16, 30, tzinfo=timezone.utc)
        self.assertEqual(datetime.fromtimestamp(store.next_daily('18:30', exact), store.KYIV).day, 6)
        for value in ['24:00', '12:60', '9:00', 'oops']:
            with self.assertRaises(ValueError):
                store.next_daily(value, winter)

    async def test_persist_and_enqueue_once_after_restart(self):
        bid = await store.save_broadcast('photo-id', None, '18:30')
        await self.due(bid)
        await store.enqueue_due()
        await store.enqueue_due()
        await store.init_auto_broadcast()
        row = (await store.list_broadcasts())[0]
        self.assertIsNone(row['caption'])
        self.assertEqual(row['clock'], '18:30')
        first, second = await asyncio.gather(store.claim_delivery(), store.claim_delivery())
        self.assertEqual({first['user_id'], second['user_id']}, {101, 102})
        self.assertNotEqual(first['id'], second['id'])
        self.assertIsNone(await store.claim_delivery())
        await store.finish_delivery(first['id'], 'sent')
        await store.init_auto_broadcast()
        self.assertIsNone(await store.claim_delivery())

    async def test_pause_cancels_queue_and_resume_sets_future_time(self):
        bid = await store.save_broadcast('photo', 'caption', '18:30')
        await self.due(bid)
        await store.enqueue_due()
        await store.change_broadcast(bid, 'toggle')
        self.assertIsNone(await store.claim_delivery())
        await store.change_broadcast(bid, 'toggle')
        await store.enqueue_due()
        self.assertIsNone(await store.claim_delivery())
        self.assertTrue((await store.list_broadcasts())[0]['enabled'])

    async def test_edit_time_and_delete(self):
        bid = await store.save_broadcast('photo', 'caption', '18:30')
        await store.change_broadcast(bid, 'time', '09:15')
        self.assertEqual((await store.list_broadcasts())[0]['clock'], '09:15')
        await self.due(bid)
        await store.enqueue_due()
        await store.change_broadcast(bid, 'delete')
        self.assertEqual(await store.list_broadcasts(), [])
        self.assertIsNone(await store.claim_delivery())

    async def test_worker_sends_photo_optional_caption_and_play_button(self):
        bid = await store.save_broadcast('photo-id', None, '18:30')
        await self.due(bid)
        bot = AsyncMock()

        async def stop_after_batch(seconds):
            if seconds == 1:
                raise asyncio.CancelledError()

        with patch.object(worker.asyncio, 'sleep', side_effect=stop_after_batch):
            with self.assertRaises(asyncio.CancelledError):
                await worker.run_auto_broadcast(bot)
        self.assertEqual(bot.send_photo.await_count, 2)
        call = bot.send_photo.call_args
        self.assertIsNone(call.kwargs['caption'])
        self.assertEqual(call.args[1], 'photo-id')
        self.assertEqual(call.kwargs['reply_markup'].inline_keyboard[0][0].callback_data, 'auto_broadcast:play')
        self.assertIsNone(await store.claim_delivery())

    async def test_play_button_uses_player_balance_and_opens_same_menu(self):
        from admin.checks import broadcast_play, play_menu_kb
        message = types.Message(
            message_id=1, date=datetime.now(timezone.utc), chat=types.Chat(id=101, type='private'),
            from_user=types.User(id=999, is_bot=True, first_name='Bot'),
        )
        callback = types.CallbackQuery(
            id='test', from_user=types.User(id=101, is_bot=False, first_name='Player'),
            chat_instance='test', message=message, data='auto_broadcast:play',
        )
        state = AsyncMock()
        with patch('admin.checks.get_balance', new_callable=AsyncMock, return_value=123) as balance:
            with patch.object(types.Message, 'answer', new_callable=AsyncMock) as answer:
                with patch.object(types.CallbackQuery, 'answer', new_callable=AsyncMock):
                    await broadcast_play(callback, state)
        balance.assert_awaited_once_with(101)
        state.clear.assert_awaited_once()
        self.assertEqual(answer.call_args.kwargs['reply_markup'], play_menu_kb())

    async def test_rate_limit_keeps_delivery_queued(self):
        from aiogram.exceptions import TelegramRetryAfter
        from aiogram.methods import SendPhoto
        await store.save_broadcast('photo-id', None, '18:30')
        await self.due(1)
        bot = AsyncMock()
        bot.send_photo.side_effect = TelegramRetryAfter(
            method=SendPhoto(chat_id=101, photo='photo-id'), message='Slow down', retry_after=2,
        )

        async def stop_after_wait(seconds):
            raise asyncio.CancelledError()

        with patch.object(worker.asyncio, 'sleep', side_effect=stop_after_wait):
            with self.assertRaises(asyncio.CancelledError):
                await worker.run_auto_broadcast(bot)
        self.assertIsNotNone(await store.claim_delivery())
