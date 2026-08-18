import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from group_games import group_jackpot as jackpot


def make_user(user_id):
    return SimpleNamespace(
        id=user_id,
        username=f"user{user_id}",
        full_name=f"User {user_id}",
        mention_html=lambda: f"User {user_id}",
    )


def make_callback(game_message, user_id, chat_id):
    return SimpleNamespace(
        message=game_message,
        from_user=make_user(user_id),
        bot=SimpleNamespace(),
        answer=AsyncMock(),
    )


class JackpotConcurrencyTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        jackpot.active_jackpots.clear()
        jackpot.winners_cooldown.clear()

    async def asyncTearDown(self):
        for game in jackpot.active_jackpots.values():
            task = game.get("task")
            if task and not task.done():
                task.cancel()
        jackpot.active_jackpots.clear()
        jackpot.winners_cooldown.clear()

    async def test_press_edits_single_game_message_instead_of_duplicating(self):
        chat_id = -2001
        game_message = SimpleNamespace(
            message_id=50,
            chat=SimpleNamespace(id=chat_id),
            edit_text=AsyncMock(),
            edit_reply_markup=AsyncMock(),
            answer=AsyncMock(),
        )
        jackpot.active_jackpots[chat_id] = {
            "message": game_message,
            "max_amount": 100,
            "starters": [],
            "starter_ids": set(),
            "amount": 1,
            "task": None,
            "active": False,
            "status": "waiting",
            "required_presses": 3,
        }

        with patch.object(jackpot, "is_game_on_cooldown", AsyncMock(return_value=False)):
            await jackpot.jackpot_press(make_callback(game_message, 101, chat_id))
            await jackpot.jackpot_press(make_callback(game_message, 202, chat_id))

        self.assertEqual(game_message.edit_text.await_count, 2)
        game_message.answer.assert_not_awaited()
        self.assertEqual(
            jackpot.active_jackpots[chat_id]["starter_ids"],
            {101, 202},
        )

    async def test_simultaneous_take_pays_only_first_player(self):
        chat_id = -2002
        game_message = SimpleNamespace(
            message_id=60,
            chat=SimpleNamespace(id=chat_id),
            edit_text=AsyncMock(),
            edit_reply_markup=AsyncMock(),
            answer=AsyncMock(),
        )
        jackpot.active_jackpots[chat_id] = {
            "message": game_message,
            "max_amount": 100,
            "starters": ["@user101", "@user202"],
            "starter_ids": {101, 202},
            "amount": 50,
            "task": None,
            "active": True,
            "status": "running",
            "required_presses": 2,
        }
        first_callback = make_callback(game_message, 101, chat_id)
        second_callback = make_callback(game_message, 202, chat_id)
        payout_started = asyncio.Event()
        release_payout = asyncio.Event()

        async def slow_payout(*args, **kwargs):
            payout_started.set()
            await release_payout.wait()
            return 40

        payout = AsyncMock(side_effect=slow_payout)
        with patch.object(jackpot, "_payout_winner", payout):
            first = asyncio.create_task(jackpot.jackpot_take(first_callback))
            await payout_started.wait()
            second = asyncio.create_task(jackpot.jackpot_take(second_callback))
            await asyncio.sleep(0)
            release_payout.set()
            await asyncio.gather(first, second)

        payout.assert_awaited_once()
        self.assertEqual(payout.await_args.args[2], 101)
        game_message.answer.assert_not_awaited()
        game_message.edit_text.assert_awaited_once()
        self.assertNotIn(chat_id, jackpot.active_jackpots)


if __name__ == "__main__":
    unittest.main()
