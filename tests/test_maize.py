import asyncio
import random
import unittest

from group_games import group_maize as maize


def make_game(path, players):
    return {
        "phase": "playing",
        "players": players,
        "path": path,
        "progress": 0,
        "correct_open": set(),
        "wrong_open": set(),
        "winner_id": None,
        "finish_reason": None,
        "last_action": "",
        "lock": asyncio.Lock(),
    }


def make_player(user_id):
    return {
        "id": user_id,
        "name": f"Player {user_id}",
        "lives": maize.START_LIVES,
        "alive": True,
        "correct_steps": 0,
    }


class MaizePathTests(unittest.TestCase):
    def test_generated_routes_follow_all_constraints(self):
        rng = random.Random(20260824)
        for _ in range(1_000):
            path = maize.generate_path(rng)
            self.assertGreaterEqual(len(path), maize.MIN_PATH_LENGTH)
            self.assertLessEqual(len(path), maize.MAX_PATH_LENGTH)
            self.assertEqual(path[0][0], maize.FIELD_SIZE - 1)
            self.assertEqual(path[-1][0], 0)
            self.assertEqual(len(path), len(set(path)))
            self.assertEqual(
                sum(row == maize.FIELD_SIZE - 1 for row, _ in path),
                1,
            )

            for current, following in zip(path, path[1:]):
                row_delta = following[0] - current[0]
                col_delta = abs(following[1] - current[1])
                self.assertIn((row_delta, col_delta), {(-1, 0), (0, 1)})

            for first_index, first in enumerate(path):
                for second_index, second in enumerate(path):
                    if abs(first_index - second_index) <= 1:
                        continue
                    distance = abs(first[0] - second[0]) + abs(first[1] - second[1])
                    self.assertNotEqual(distance, 1)

    def test_wrong_legal_moves_are_never_future_route_cells(self):
        rng = random.Random(42)
        for _ in range(500):
            path = maize.generate_path(rng)
            player = make_player(101)
            game = make_game(path, {101: player})
            for progress, expected in enumerate(path):
                game["progress"] = progress
                wrong_moves = maize.get_allowed_moves(game) - {expected}
                self.assertTrue(wrong_moves.isdisjoint(path[progress + 1 :]))

    def test_keyboard_contains_five_field_rows_and_direction_row(self):
        game = make_game([(4, 2), (3, 2), (2, 2), (1, 2), (0, 2)], {})
        keyboard = maize.build_field_keyboard(game)
        self.assertEqual(len(keyboard.inline_keyboard), 7)
        self.assertTrue(all(len(row) == 5 for row in keyboard.inline_keyboard[:6]))
        self.assertTrue(
            all(button.text == maize.DIRECTION_CELL for button in keyboard.inline_keyboard[5])
        )
        self.assertEqual(keyboard.inline_keyboard[6][0].callback_data, "maize_cancel")

    def test_join_keyboard_contains_cancel_button(self):
        keyboard = maize.build_join_keyboard()
        callbacks = [
            button.callback_data
            for row in keyboard.inline_keyboard
            for button in row
        ]
        self.assertIn("maize_cancel", callbacks)


class MaizeMoveTests(unittest.TestCase):
    def test_players_share_route_and_only_final_clicker_wins(self):
        path = [(4, 2), (3, 2), (2, 2), (1, 2), (0, 2)]
        game = make_game(path, {101: make_player(101), 202: make_player(202)})

        for index, cell in enumerate(path[:-1]):
            player_id = 101 if index % 2 == 0 else 202
            result = maize.apply_move(game, player_id, cell)
            self.assertEqual(result["status"], "correct")
        result = maize.apply_move(game, 202, path[-1])
        self.assertEqual(result["status"], "winner")
        self.assertEqual(result["winner_id"], 202)

        second_result = maize.apply_move(game, 101, path[-1])
        self.assertEqual(second_result["status"], "finished")
        self.assertEqual(game["winner_id"], 202)
        self.assertEqual(game["progress"], len(path))
        self.assertEqual(game["correct_open"], set(path))

    def test_wrong_move_costs_one_life_and_stays_visible(self):
        path = [(4, 2), (3, 2), (2, 2), (1, 2), (0, 2)]
        game = make_game(
            path,
            {101: make_player(101), 202: make_player(202), 303: make_player(303)},
        )

        result = maize.apply_move(game, 101, (4, 0))

        self.assertEqual(result["status"], "wrong")
        self.assertEqual(game["players"][101]["lives"], maize.START_LIVES - 1)
        self.assertIn((4, 0), game["wrong_open"])

    def test_non_adjacent_move_does_not_damage_or_mark_the_field(self):
        path = [(4, 2), (3, 2), (2, 2), (1, 2), (0, 2)]
        player = make_player(101)
        game = make_game(path, {101: player})
        game["progress"] = 1

        result = maize.apply_move(game, 101, (0, 0))

        self.assertEqual(result["status"], "invalid_move")
        self.assertEqual(player["lives"], maize.START_LIVES)
        self.assertFalse(game["wrong_open"])

    def test_last_alive_player_wins(self):
        path = [(4, 2), (3, 2), (2, 2), (1, 2), (0, 2)]
        players = {101: make_player(101), 202: make_player(202), 303: make_player(303)}
        players[202]["alive"] = False
        players[202]["lives"] = 0
        players[303]["lives"] = 1
        game = make_game(path, players)

        result = maize.apply_move(game, 303, (4, 0))

        self.assertEqual(result["status"], "winner")
        self.assertEqual(result["reason"], "last_alive")
        self.assertEqual(result["winner_id"], 101)
        self.assertEqual(game["winner_id"], 101)


if __name__ == "__main__":
    unittest.main()
