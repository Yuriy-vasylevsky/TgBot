import unittest
from unittest.mock import AsyncMock, patch

from db import game_cooldown


class GroupGameCooldownPolicyTests(unittest.IsolatedAsyncioTestCase):
    def test_shared_policy_values(self):
        self.assertEqual(game_cooldown.GAME_COOLDOWN_HOURS, 12)
        self.assertEqual(game_cooldown.GAME_COOLDOWN_MIN_WIN, 50)

    async def test_win_below_50_does_not_start_cooldown(self):
        with patch.object(
            game_cooldown, "set_game_cooldown", new_callable=AsyncMock
        ) as set_cooldown:
            applied = await game_cooldown.set_game_cooldown_for_win(101, 49)

        self.assertFalse(applied)
        set_cooldown.assert_not_awaited()

    async def test_win_of_50_starts_12_hour_cooldown(self):
        with patch.object(
            game_cooldown, "set_game_cooldown", new_callable=AsyncMock
        ) as set_cooldown:
            applied = await game_cooldown.set_game_cooldown_for_win(101, 50)

        self.assertTrue(applied)
        set_cooldown.assert_awaited_once_with(101, hours=12)


if __name__ == "__main__":
    unittest.main()
