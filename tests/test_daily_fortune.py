import asyncio
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4
from unittest.mock import AsyncMock, patch

import aiosqlite
from db import daily_fortune as fortune
from db import winlog


class DailyFortuneTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        folder = Path(__file__).resolve().parent.parent / '.tmp'
        folder.mkdir(exist_ok=True)
        self.path = folder / f'daily-fortune-{uuid4().hex}.db'
        self.patch = patch.object(fortune, 'DB_PATH', self.path)
        self.patch.start()
        self.now = datetime(2026, 11, 9, 15, 0, tzinfo=fortune.KYIV).timestamp()
        await fortune.init_daily_fortune()
        with patch.object(winlog, 'DB_PATH', self.path):
            await winlog.ensure_win_log_table()
        async with aiosqlite.connect(self.path) as db:
            await db.execute('CREATE TABLE users(user_id INTEGER PRIMARY KEY, balance INTEGER)')
            await db.execute('INSERT INTO users VALUES (1, 100)')
            await db.execute('''CREATE TABLE payment_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, amount INTEGER,
                comment TEXT, created_at TEXT)''')
            await db.commit()

    async def asyncTearDown(self):
        self.patch.stop()
        self.path.unlink(missing_ok=True)

    async def deposit(self, amount=200, at=None, comment='payment'):
        timestamp = datetime.fromtimestamp(self.now if at is None else at, timezone(timedelta(hours=3)))
        async with aiosqlite.connect(self.path) as db:
            await db.execute('INSERT INTO payment_logs(user_id, amount, comment, created_at) VALUES (1,?,?,?)',
                             (amount, comment, timestamp.strftime('%Y-%m-%d %H:%M:%S')))
            await db.commit()

    async def test_requires_real_deposit_today_kyiv_midnight(self):
        midnight = datetime(2026, 11, 9, tzinfo=fortune.KYIV).timestamp()
        await self.deposit(at=midnight - 1)
        await self.deposit(500, comment='SAFE_TOP_5')
        self.assertEqual((await fortune.reserve_fortune(1, now=self.now))['reason'], 'no_deposit')
        await self.deposit(300, at=midnight)
        status = await fortune.reserve_fortune(1, now=self.now)
        self.assertTrue(status['success'])
        self.assertEqual(status['deposit_amount'], 300)

    async def test_user_card_winnings_follow_kyiv_day(self):
        await self.deposit(200)
        attempt = await fortune.reserve_fortune(1, now=self.now)
        self.assertEqual(await fortune.get_fortune_winnings(1, now=self.now), (0, 0))
        await fortune.settle_fortune(attempt['attempt_id'], 3, 123)
        self.assertEqual(await fortune.get_fortune_winnings(1, now=self.now), (60, 0))
        self.assertEqual(await fortune.get_fortune_winnings(2, now=self.now), (0, 0))
        tomorrow = datetime(2026, 11, 10, 0, 0, tzinfo=fortune.KYIV).timestamp()
        self.assertEqual(await fortune.get_fortune_winnings(1, now=tomorrow), (0, 60))
        later = datetime(2026, 11, 11, 0, 0, tzinfo=fortune.KYIV).timestamp()
        self.assertEqual(await fortune.get_fortune_winnings(1, now=later), (0, 0))

    async def test_last_deposit_not_sum_or_safe_award(self):
        await self.deposit(1000, at=self.now - 60)
        await self.deposit(250, at=self.now - 30)
        await self.deposit(5000, comment='SAFE_TOP_5')
        attempt = await fortune.reserve_fortune(1, now=self.now)
        await self.deposit(2000)
        result = await fortune.settle_fortune(attempt['attempt_id'], 6, 123)
        self.assertEqual(result['deposit_amount'], 250)
        self.assertEqual(result['bonus'], 150)
        self.assertEqual(result['balance'], 250)

    async def test_all_faces_and_integer_rounding(self):
        for value in range(1, 7):
            with self.subTest(value=value):
                await self.deposit(101)
                attempt = await fortune.reserve_fortune(1, now=self.now)
                result = await fortune.settle_fortune(attempt['attempt_id'], value, value)
                self.assertEqual(result['bonus'], 101 * value // 10)
                async with aiosqlite.connect(self.path) as db:
                    await db.execute('DELETE FROM daily_fortune')
                    await db.commit()

    async def test_bonus_base_capped_at_500(self):
        for deposit, face, expected in [(499, 6, 299), (500, 6, 300), (501, 6, 300), (2000, 1, 50), (10000, 6, 300)]:
            with self.subTest(deposit=deposit, face=face):
                await self.deposit(deposit)
                attempt = await fortune.reserve_fortune(1, now=self.now)
                result = await fortune.settle_fortune(attempt['attempt_id'], face, 123)
                self.assertEqual(result['bonus'], expected)
                self.assertEqual(result['deposit_amount'], deposit)
                self.assertEqual(result['bonus_base'], min(deposit, 500))
                async with aiosqlite.connect(self.path) as db:
                    await db.execute('DELETE FROM daily_fortune')
                    await db.commit()

    async def test_concurrent_clicks_and_idempotent_credit(self):
        await self.deposit()
        results = await asyncio.gather(*(fortune.reserve_fortune(1, now=self.now) for _ in range(5)))
        winners = [r for r in results if r['success']]
        self.assertEqual(len(winners), 1)
        aid = winners[0]['attempt_id']
        await asyncio.gather(*(fortune.settle_fortune(aid, 4, 123) for _ in range(4)))
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute('SELECT balance FROM users WHERE user_id=1')
            self.assertEqual((await cur.fetchone())[0], 180)
            cur = await db.execute("SELECT amount, win_type FROM win_log")
            self.assertEqual(await cur.fetchall(), [(80, 'daily_fortune')])
        await fortune.init_daily_fortune()
        await self.deposit(500)
        self.assertEqual((await fortune.reserve_fortune(1, now=self.now))['reason'], 'used')

    async def test_new_calendar_day_requires_new_deposit(self):
        await self.deposit()
        attempt = await fortune.reserve_fortune(1, now=self.now)
        await fortune.settle_fortune(attempt['attempt_id'], 1, 1)
        tomorrow = datetime(2026, 11, 10, 0, 1, tzinfo=fortune.KYIV).timestamp()
        self.assertEqual((await fortune.reserve_fortune(1, now=tomorrow))['reason'], 'no_deposit')
        await self.deposit(400, at=tomorrow)
        self.assertTrue((await fortune.reserve_fortune(1, now=tomorrow))['success'])

    async def test_explicit_rejection_can_release_but_settled_cannot(self):
        await self.deposit()
        first = await fortune.reserve_fortune(1, now=self.now)
        await fortune.release_fortune(first['attempt_id'])
        second = await fortune.reserve_fortune(1, now=self.now)
        self.assertTrue(second['success'])
        await fortune.settle_fortune(second['attempt_id'], 3, 123)
        await fortune.release_fortune(second['attempt_id'])
        self.assertEqual((await fortune.reserve_fortune(1, now=self.now))['reason'], 'used')

    async def test_menu_second_row_and_independent_from_promocodes(self):
        from handlers.menu import main_menu
        from services import promotions
        with patch.object(promotions, '_enabled', False):
            self.assertEqual(main_menu().keyboard[1][0].text, '🎲 Фортуна')

    async def test_handler_credits_telegram_dice_and_blocks_second_roll(self):
        from types import SimpleNamespace
        from handlers.daily_fortune import roll_fortune
        await self.deposit(500)
        message = SimpleNamespace(
            chat=SimpleNamespace(type='private'), answer=AsyncMock(), edit_reply_markup=AsyncMock(),
            answer_dice=AsyncMock(return_value=SimpleNamespace(dice=SimpleNamespace(value=5), message_id=777)),
        )
        cb = SimpleNamespace(from_user=SimpleNamespace(id=1, username='private_player', full_name='Private Player'),
                             message=message, answer=AsyncMock(), bot=SimpleNamespace(send_message=AsyncMock()))
        with patch('db.daily_fortune.time.time', return_value=self.now):
            await roll_fortune(cb)
            await roll_fortune(cb)
        message.answer_dice.assert_awaited_once_with(emoji='🎲')
        self.assertIn('+250', message.answer.call_args.args[0])
        from handlers.daily_fortune import FORTUNE_GROUP_ID
        group_messages = [call for call in cb.bot.send_message.call_args_list if call.args[0] == FORTUNE_GROUP_ID]
        self.assertEqual(len(group_messages), 1)
        public_text = group_messages[0].args[1]
        self.assertIn('+250', public_text)
        for private_info in ('private_player', 'Private Player', 'tg://user'):
            self.assertNotIn(private_info, public_text)
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute('SELECT balance FROM users WHERE user_id=1')
            self.assertEqual((await cur.fetchone())[0], 350)
            cur = await db.execute('SELECT username,full_name,amount FROM win_log')
            self.assertEqual(await cur.fetchall(), [('private_player', 'Private Player', 250)])
