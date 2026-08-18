import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from games import blackjack


class FakeState:
    def __init__(self, current_state, data):
        self.current_state = current_state
        self.data = data

    async def get_state(self):
        return self.current_state

    async def set_state(self, state):
        self.current_state = state.state if hasattr(state, "state") else state

    async def get_data(self):
        return self.data.copy()

    async def update_data(self, **kwargs):
        self.data.update(kwargs)


def make_message(text, user_id):
    return SimpleNamespace(
        text=text,
        chat=SimpleNamespace(id=user_id),
        from_user=SimpleNamespace(id=user_id),
        answer=AsyncMock(),
    )


class BlackjackConcurrencyTests(unittest.IsolatedAsyncioTestCase):
    async def test_repeated_bet_only_deals_one_round(self):
        state = FakeState(
            blackjack.BlackjackFSM.choosing_bet.state,
            {
                "deck": [
                    "2♠️",
                    "3♥️",
                    "4♦️",
                    "5♣️",
                    "6♠️",
                    "7♥️",
                ],
                "balance": 10,
            },
        )
        first_message = make_message("💵 5 купонів", 100)
        second_message = make_message("💵 5 купонів", 100)
        started = asyncio.Event()
        release = asyncio.Event()

        async def slow_answer(*args, **kwargs):
            started.set()
            await release.wait()

        first_message.answer.side_effect = slow_answer
        first = asyncio.create_task(
            blackjack.handle_bet_choice(first_message, state)
        )
        await started.wait()
        second = asyncio.create_task(
            blackjack.handle_bet_choice(second_message, state)
        )
        await asyncio.sleep(0)
        release.set()
        await asyncio.gather(first, second)

        self.assertEqual(len(state.data["deck"]), 2)
        self.assertEqual(len(state.data["user_cards"]), 2)
        self.assertEqual(len(state.data["dealer_cards"]), 2)
        self.assertEqual(
            state.current_state,
            blackjack.BlackjackFSM.in_round.state,
        )

    async def test_repeated_stand_only_finishes_round_once(self):
        state = FakeState(
            blackjack.BlackjackFSM.in_round.state,
            {
                "deck": ["2♠️"],
                "user_cards": ["10♠️", "8♥️"],
                "dealer_cards": ["10♦️", "7♣️"],
                "bet": 5,
                "balance": 10,
            },
        )
        first_message = make_message("🛑 Досить", 101)
        second_message = make_message("🛑 Досить", 101)
        started = asyncio.Event()
        release = asyncio.Event()
        calls = 0

        async def fake_finish(message, current_state, busted):
            nonlocal calls
            calls += 1
            started.set()
            await release.wait()
            await current_state.set_state(blackjack.BlackjackFSM.choosing_bet)

        with patch.object(blackjack, "finish_round", side_effect=fake_finish):
            first = asyncio.create_task(
                blackjack.in_round_handler(first_message, state)
            )
            await started.wait()
            second = asyncio.create_task(
                blackjack.in_round_handler(second_message, state)
            )
            await asyncio.sleep(0)
            release.set()
            await asyncio.gather(first, second)

        self.assertEqual(calls, 1)

    async def test_repeated_hit_only_draws_one_card(self):
        state = FakeState(
            blackjack.BlackjackFSM.in_round.state,
            {
                "deck": ["2♠️", "3♥️"],
                "user_cards": ["10♠️", "4♥️"],
                "dealer_cards": ["10♦️", "7♣️"],
                "bet": 5,
                "balance": 10,
            },
        )
        first_message = make_message("➕ Взяти ще", 102)
        second_message = make_message("➕ Взяти ще", 102)
        started = asyncio.Event()
        release = asyncio.Event()

        async def slow_answer(*args, **kwargs):
            started.set()
            await release.wait()

        first_message.answer.side_effect = slow_answer
        first = asyncio.create_task(blackjack.in_round_handler(first_message, state))
        await started.wait()
        second = asyncio.create_task(blackjack.in_round_handler(second_message, state))
        await asyncio.sleep(0)
        release.set()
        await asyncio.gather(first, second)

        self.assertEqual(state.data["user_cards"], ["10♠️", "4♥️", "3♥️"])
        self.assertEqual(state.data["deck"], ["2♠️"])
        self.assertEqual(
            state.current_state,
            blackjack.BlackjackFSM.in_round.state,
        )


if __name__ == "__main__":
    unittest.main()
