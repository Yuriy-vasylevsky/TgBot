import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from group_games import group_wordle as wordle


def make_message(user_id, message_id):
    user = SimpleNamespace(
        id=user_id,
        username=f"user{user_id}",
        full_name=f"User {user_id}",
        mention_html=lambda: f"User {user_id}",
    )
    next_message_id = iter(range(message_id + 100, message_id + 110))

    async def answer(*args, **kwargs):
        return SimpleNamespace(message_id=next(next_message_id))

    return SimpleNamespace(
        text="слово",
        message_id=message_id,
        chat=SimpleNamespace(id=-1001),
        from_user=user,
        bot=SimpleNamespace(
            send_message=AsyncMock(),
            delete_message=AsyncMock(),
        ),
        answer=AsyncMock(side_effect=answer),
    )


class WordleConcurrencyTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        wordle.active_wordle_games.clear()
        wordle.winners_cooldown.clear()

    async def asyncTearDown(self):
        wordle.active_wordle_games.clear()
        wordle.winners_cooldown.clear()

    async def test_only_first_simultaneous_correct_answer_wins(self):
        chat_id = -1001
        wordle.active_wordle_games[chat_id] = {
            "secret": "слово",
            "revealed": ["❓"] * 5,
            "messages": [1],
            "winner_id": None,
            "lock": asyncio.Lock(),
        }
        first_message = make_message(101, 10)
        second_message = make_message(202, 20)
        first_check_started = asyncio.Event()
        release_first_check = asyncio.Event()
        cooldown_checks = 0

        async def controlled_cooldown_check(user_id):
            nonlocal cooldown_checks
            cooldown_checks += 1
            if user_id == 101:
                first_check_started.set()
                await release_first_check.wait()
            return False

        payout = AsyncMock(return_value=50)
        with (
            patch.object(
                wordle,
                "is_game_on_cooldown",
                side_effect=controlled_cooldown_check,
            ),
            patch.object(wordle, "_payout_winner", payout),
        ):
            first = asyncio.create_task(wordle.handle_wordle(first_message))
            await first_check_started.wait()
            second = asyncio.create_task(wordle.handle_wordle(second_message))
            await asyncio.sleep(0)
            release_first_check.set()
            await asyncio.gather(first, second)

        self.assertEqual(cooldown_checks, 1)
        payout.assert_awaited_once()
        self.assertEqual(payout.await_args.args[2], 101)
        self.assertEqual(first_message.answer.await_count, 2)
        self.assertEqual(second_message.answer.await_count, 0)
        self.assertNotIn(chat_id, wordle.active_wordle_games)


if __name__ == "__main__":
    unittest.main()
