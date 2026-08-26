import asyncio
import html
import logging
import math
import random
import time

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from db import add_daily_game_win, add_money_win
from db.game_cooldown import (
    GAME_COOLDOWN_HOURS,
    GAME_COOLDOWN_MIN_WIN,
    format_cooldown as format_game_cooldown,
    get_game_cooldown_remaining,
    is_game_on_cooldown,
    set_game_cooldown_for_win,
)
from db.wallet import (
    add_to_balance,
    get_daily_game_win,
    get_daily_net,
    get_yesterday_game_win,
    get_yesterday_net,
)
from db.winlog import log_win
from handlers.config import ADMIN_ID


router = Router(name="group_maize")
router.message.filter(F.chat.type.in_({"group", "supergroup"}))

FIELD_SIZE = 5
MIN_PATH_LENGTH = 10
MAX_PATH_LENGTH = 16
MIN_PLAYERS = 2
MAX_PLAYERS = 5
START_LIVES = 2
PRIZE_AMOUNT = 50
CLICK_COOLDOWN_SECONDS = 4
WINNER_COOLDOWN_HOURS = GAME_COOLDOWN_HOURS

UNKNOWN_CELL = "⬜"
CORRECT_CELL = "🟩"
WRONG_CELL = "🟥"
WIN_CELL = "🏆"
DIRECTION_CELL = "⬆️"

UPDATE_DEBOUNCE_SECONDS = 0.15
API_CALL_INTERVAL_SECONDS = 0.8

active_maize_games: dict[int, dict] = {}
winners_cooldown: dict[int, float] = {}

_last_api_call: dict[int, float] = {}
_api_locks: dict[int, asyncio.Lock] = {}


def _positive_or_zero(value: int) -> int:
    return value if value > 0 else 0


def get_display_name(user) -> str:
    return f"@{user.username}" if user.username else user.full_name


def _safe_name(name: str) -> str:
    return html.escape(name)


def _format_local_cooldown(remaining_seconds: int) -> str:
    hours = remaining_seconds // 3600
    minutes = (remaining_seconds % 3600) // 60
    seconds = remaining_seconds % 60
    parts = []
    if hours:
        parts.append(f"{hours}г")
    if minutes:
        parts.append(f"{minutes}хв")
    if seconds and not hours and not minutes:
        parts.append(f"{seconds}с")
    return " ".join(parts) or "менше хвилини"


def _winner_cooldown_remaining(user_id: int) -> int:
    cooldown_until = winners_cooldown.get(user_id, 0)
    remaining = cooldown_until - time.time()
    if remaining > 0:
        return math.ceil(remaining)
    winners_cooldown.pop(user_id, None)
    return 0


def generate_path(rng=None) -> list[tuple[int, int]]:
    """Build a continuous bottom-to-top route within configured length limits."""
    rng = rng or random

    def search(
        path: list[tuple[int, int]],
        visited: set[tuple[int, int]],
        target_length: int,
    ) -> list[tuple[int, int]] | None:
        row, col = path[-1]
        if len(path) == target_length:
            return path if row == 0 else None

        remaining_steps = target_length - len(path)
        if row > remaining_steps:
            return None

        candidates = []
        if row > 0:
            candidates.append((row - 1, col))
        # The bottom row must contain only one possible starting route cell.
        if row < FIELD_SIZE - 1:
            candidates.extend(((row, col - 1), (row, col + 1)))
        rng.shuffle(candidates)

        for next_row, next_col in candidates:
            next_cell = (next_row, next_col)
            if not 0 <= next_row < FIELD_SIZE or not 0 <= next_col < FIELD_SIZE:
                continue
            if next_cell in visited:
                continue

            remaining_after_move = target_length - len(path) - 1
            if next_row > remaining_after_move:
                continue

            # The route may touch only its immediately preceding cell. This
            # keeps every red choice outside the hidden route.
            neighbours = {
                (next_row - 1, next_col),
                (next_row + 1, next_col),
                (next_row, next_col - 1),
                (next_row, next_col + 1),
            }
            if neighbours.intersection(visited) != {path[-1]}:
                continue

            result = search(
                path + [next_cell],
                visited | {next_cell},
                target_length,
            )
            if result is not None:
                return result
        return None

    target_lengths = list(range(MIN_PATH_LENGTH, MAX_PATH_LENGTH + 1))
    rng.shuffle(target_lengths)
    for target_length in target_lengths:
        start_columns = list(range(FIELD_SIZE))
        rng.shuffle(start_columns)
        for start_col in start_columns:
            start = (FIELD_SIZE - 1, start_col)
            result = search([start], {start}, target_length)
            if result is not None:
                return result

    raise RuntimeError(
        f"Unable to generate a Maize route of at least {MIN_PATH_LENGTH} cells"
    )


def get_allowed_moves(game: dict) -> set[tuple[int, int]]:
    """Return cells that may continue the shared route."""
    progress = game["progress"]
    if progress == 0:
        return {(FIELD_SIZE - 1, col) for col in range(FIELD_SIZE)}

    row, col = game["path"][progress - 1]
    traversed = set(game["path"][:progress])
    candidates = {
        (row - 1, col),
        (row, col - 1),
        (row, col + 1),
    }
    return {
        cell
        for cell in candidates
        if 0 <= cell[0] < FIELD_SIZE
        and 0 <= cell[1] < FIELD_SIZE
        and cell not in traversed
    }


def build_field_keyboard(game: dict) -> InlineKeyboardMarkup:
    winner_cell = None
    winner_id = game.get("winner_id")
    if winner_id is not None:
        if game.get("progress", 0) >= len(game.get("path") or []):
            winner_cell = game["path"][-1]

    rows = []
    for row in range(FIELD_SIZE):
        buttons = []
        for col in range(FIELD_SIZE):
            cell = (row, col)
            if cell == winner_cell:
                symbol = WIN_CELL
            elif cell in game.get("correct_open", set()):
                symbol = CORRECT_CELL
            elif cell in game.get("wrong_open", set()):
                symbol = WRONG_CELL
            else:
                symbol = UNKNOWN_CELL
            buttons.append(
                InlineKeyboardButton(
                    text=symbol,
                    callback_data=(
                        f"maize_cell_{game.get('progress', 0)}_{row}_{col}"
                    ),
                )
            )
        rows.append(buttons)

    # This sixth row is a visual direction hint, not an entrance to the field.
    rows.append(
        [
            InlineKeyboardButton(
                text=DIRECTION_CELL,
                callback_data=f"maize_direction_{col}",
            )
            for col in range(FIELD_SIZE)
        ]
    )
    if game.get("phase") == "playing":
        rows.append(
            [
                InlineKeyboardButton(
                    text="❌ Скасувати гру",
                    callback_data="maize_cancel",
                )
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_join_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Приєднатися", callback_data="maize_join")],
            [
                InlineKeyboardButton(
                    text="🚀 СТАРТ (тільки адмін)",
                    callback_data="maize_start",
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Скасувати гру",
                    callback_data="maize_cancel",
                )
            ],
        ]
    )


def build_join_text(game: dict) -> str:
    players = list(game["players"].values())
    player_lines = "\n".join(
        f"• {_safe_name(player['name'])}" for player in players
    ) or "• Поки немає учасників"
    return (
        "<b>🌽 MAIZE</b>\n\n"
        "Знайдіть приховану доріжку крізь поле 5×5.\n"
        f"🌽 У доріжці щонайменше {MIN_PATH_LENGTH} клітинок\n"
        "⬆️ Рух дозволено вперед або вбік\n"
        f"❤️ У кожного гравця {START_LIVES} життів\n"
        f"⏱ Між натисканнями одного гравця — {CLICK_COOLDOWN_SECONDS} секунд\n"
        f"🏆 Приз — <b>{PRIZE_AMOUNT} грн</b>\n\n"
        f"👥 Гравців: <b>{len(players)}/{MAX_PLAYERS}</b> "
        f"(мінімум {MIN_PLAYERS})\n{player_lines}\n\n"
        "Адмін запускає гру кнопкою нижче."
    )


def build_game_text(game: dict) -> str:
    lines = ["<b>🌽 MAIZE</b>", "", "<b>👥 Гравці:</b>"]
    path_length = len(game["path"])
    for player in game["players"].values():
        if player["alive"]:
            hearts = "❤️" * player["lives"]
            status = hearts
        else:
            status = "💀 вибув"
        lines.append(f"• {_safe_name(player['name'])} — {status}")

    lines.extend(
        [
            "",
            f"🌽 Доріжка: <b>{game['progress']}/{path_length}</b>",
            "⬆️ Починайте з нижнього активного рядка.",
            "🟩 правильна клітинка  🟥 неправильна клітинка",
        ]
    )
    if game.get("last_action"):
        lines.extend(["", f"📍 {game['last_action']}"])
    return "\n".join(lines)


def build_final_text(game: dict, winner_id: int, reason: str) -> str:
    winner = game["players"][winner_id]
    reason_text = (
        "дійшов до виграшної клітинки"
        if reason == "finish"
        else "залишився останнім у грі"
    )
    lines = [
        "<b>🏁 MAIZE ЗАВЕРШЕНО!</b>",
        "",
        f"🏆 <b>{_safe_name(winner['name'])}</b> {reason_text}!",
        f"💰 Приз: <b>{PRIZE_AMOUNT} грн</b>",
        "",
        "<b>Результати:</b>",
    ]
    ranking = sorted(
        game["players"].values(),
        key=lambda player: (
            player["id"] == winner_id,
            player["alive"],
            player["correct_steps"],
            player["lives"],
        ),
        reverse=True,
    )
    for index, player in enumerate(ranking, 1):
        marker = "🥇" if player["id"] == winner_id else f"{index}."
        lives = f"❤️×{player['lives']}" if player["alive"] else "💀"
        lines.append(
            f"{marker} {_safe_name(player['name'])} — "
            f"правильних кроків: {player['correct_steps']}, {lives}"
        )
    return "\n".join(lines)


def apply_move(game: dict, user_id: int, cell: tuple[int, int]) -> dict:
    """Apply one move. The caller must hold the game's lock."""
    if game.get("phase") != "playing" or game.get("winner_id") is not None:
        return {"status": "finished"}

    player = game["players"].get(user_id)
    if not player:
        return {"status": "not_player"}
    if not player["alive"]:
        return {"status": "dead"}

    if cell not in get_allowed_moves(game):
        return {"status": "invalid_move"}

    expected = game["path"][game["progress"]]
    if cell == expected:
        game["progress"] += 1
        player["correct_steps"] += 1
        game["wrong_open"].discard(cell)
        game["correct_open"].add(cell)
        game["last_action"] = (
            f"🟩 <b>{_safe_name(player['name'])}</b> зробив правильний крок."
        )
        if game["progress"] == len(game["path"]):
            game["winner_id"] = user_id
            game["finish_reason"] = "finish"
            game["phase"] = "finishing"
            return {"status": "winner", "reason": "finish", "winner_id": user_id}
        return {"status": "correct", "progress": game["progress"]}

    player["lives"] -= 1
    if cell not in game["correct_open"]:
        game["wrong_open"].add(cell)

    if player["lives"] <= 0:
        player["lives"] = 0
        player["alive"] = False
        game["last_action"] = (
            f"💀 <b>{_safe_name(player['name'])}</b> помилився та вибув."
        )
    else:
        game["last_action"] = (
            f"🟥 <b>{_safe_name(player['name'])}</b> помилився. "
            f"Залишилось життів: {player['lives']}."
        )

    alive_ids = [
        player_id
        for player_id, candidate in game["players"].items()
        if candidate["alive"]
    ]
    if len(alive_ids) == 1:
        winner_id = alive_ids[0]
        game["winner_id"] = winner_id
        game["finish_reason"] = "last_alive"
        game["phase"] = "finishing"
        return {
            "status": "winner",
            "reason": "last_alive",
            "winner_id": winner_id,
        }

    return {
        "status": "wrong",
        "lives": player["lives"],
        "eliminated": not player["alive"],
    }


def _get_api_lock(chat_id: int) -> asyncio.Lock:
    return _api_locks.setdefault(chat_id, asyncio.Lock())


async def _rate_limited_edit(chat_id: int, factory):
    async with _get_api_lock(chat_id):
        elapsed = time.monotonic() - _last_api_call.get(chat_id, 0)
        if elapsed < API_CALL_INTERVAL_SECONDS:
            await asyncio.sleep(API_CALL_INTERVAL_SECONDS - elapsed)

        for _ in range(3):
            try:
                result = await factory()
                _last_api_call[chat_id] = time.monotonic()
                return result
            except TelegramRetryAfter as error:
                await asyncio.sleep(error.retry_after + 0.5)
            except TelegramBadRequest as error:
                if "message is not modified" not in str(error).lower():
                    logging.warning("Maize message edit failed in %s: %s", chat_id, error)
                return None
            except TelegramForbiddenError as error:
                logging.warning("Maize message unavailable in %s: %s", chat_id, error)
                return None
            except Exception:
                logging.exception("Unexpected Maize edit failure in chat %s", chat_id)
                return None
    return None


def _cancel_update(game: dict) -> None:
    task = game.get("update_task")
    if task and not task.done():
        task.cancel()
    game["update_task"] = None


def schedule_game_update(chat_id: int) -> None:
    game = active_maize_games.get(chat_id)
    if not game or game["phase"] != "playing":
        return
    _cancel_update(game)

    async def update_after_debounce():
        try:
            await asyncio.sleep(UPDATE_DEBOUNCE_SECONDS)
            current = active_maize_games.get(chat_id)
            if not current or current["phase"] != "playing":
                return
            await _rate_limited_edit(
                chat_id,
                lambda: current["message"].edit_text(
                    build_game_text(current),
                    reply_markup=build_field_keyboard(current),
                    parse_mode="HTML",
                ),
            )
        except asyncio.CancelledError:
            return

    game["update_task"] = asyncio.create_task(update_after_debounce())


async def _payout_winner(
    chat_id: int,
    bot,
    user_id: int,
    name: str,
    prize: int,
) -> int:
    today_net = await get_daily_net(user_id)
    yesterday_net = await get_yesterday_net(user_id)
    total_net = _positive_or_zero(today_net) + _positive_or_zero(yesterday_net)
    safe_name = _safe_name(name)

    if total_net <= 0:
        await bot.send_message(
            chat_id,
            f"👤 <b>{safe_name}</b> — виграш <b>{prize} грн</b>\n"
            "❌ Не було депозиту! Виграш не нараховано❗",
            parse_mode="HTML",
        )
        return 0

    daily_game_win = await get_daily_game_win(user_id)
    yesterday_game_win = await get_yesterday_game_win(user_id)
    already_won = _positive_or_zero(daily_game_win) + _positive_or_zero(
        yesterday_game_win
    )
    max_allowed_win = int(total_net * 80 / 200)
    available_limit = max(max_allowed_win - already_won, 0)
    payout_amount = min(prize, available_limit)

    if payout_amount > 0:
        await add_to_balance(user_id, payout_amount)
        await add_daily_game_win(user_id, payout_amount)
        await set_game_cooldown_for_win(user_id, payout_amount)
        await log_win(user_id, None, name, "group", "Maize", payout_amount)

    await add_money_win(user_id, prize)

    if payout_amount >= prize:
        text = (
            f"👤 <b>{safe_name}</b> — виграш <b>{prize} грн</b>\n"
            "✅ Нараховано на баланс 💸"
        )
    elif payout_amount > 0:
        text = (
            f"👤 <b>{safe_name}</b> — виграш <b>{prize} грн</b>\n"
            "⚠️ Спрацював ліміт виграшів.\n"
            f"На баланс зараховано <b>{payout_amount} грн</b>."
        )
    else:
        text = (
            f"👤 <b>{safe_name}</b> — виграш <b>{prize} грн</b>\n"
            "❌ Ліміт виграшів вичерпано."
        )
    await bot.send_message(chat_id, text, parse_mode="HTML")
    return payout_amount


async def finish_maize(chat_id: int, winner_id: int, reason: str) -> None:
    game = active_maize_games.get(chat_id)
    if not game or game.get("winner_id") != winner_id:
        return

    game["phase"] = "finished"
    _cancel_update(game)
    winner = game["players"][winner_id]
    bot = game["message"].bot

    try:
        await _rate_limited_edit(
            chat_id,
            lambda: game["message"].edit_text(
                build_final_text(game, winner_id, reason),
                reply_markup=build_field_keyboard(game),
                parse_mode="HTML",
            ),
        )
        payout_amount = await _payout_winner(
            chat_id,
            bot,
            winner_id,
            winner["name"],
            PRIZE_AMOUNT,
        )
        if payout_amount >= GAME_COOLDOWN_MIN_WIN:
            winners_cooldown[winner_id] = (
                time.time() + WINNER_COOLDOWN_HOURS * 3600
            )
    except Exception:
        logging.exception("Failed to finish Maize in chat %s", chat_id)
    finally:
        active_maize_games.pop(chat_id, None)
        _last_api_call.pop(chat_id, None)
        _api_locks.pop(chat_id, None)


@router.message(Command("maize"))
async def start_maize(message: Message) -> None:
    if message.from_user.id != ADMIN_ID:
        try:
            await message.delete()
        except Exception:
            pass
        return

    chat_id = message.chat.id
    if chat_id in active_maize_games:
        await message.answer("❌ Гра Maize вже запущена!")
        return

    game = {
        "phase": "joining",
        "admin_id": message.from_user.id,
        "players": {},
        "path": None,
        "progress": 0,
        "correct_open": set(),
        "wrong_open": set(),
        "winner_id": None,
        "finish_reason": None,
        "last_action": "",
        "last_clicks": {},
        "lock": asyncio.Lock(),
        "update_task": None,
        "message": None,
    }
    status_message = await message.answer(
        build_join_text(game),
        reply_markup=build_join_keyboard(),
        parse_mode="HTML",
    )
    game["message"] = status_message
    active_maize_games[chat_id] = game


@router.callback_query(F.data == "maize_join")
async def join_maize(callback: CallbackQuery) -> None:
    chat_id = callback.message.chat.id
    game = active_maize_games.get(chat_id)
    if not game or game["phase"] != "joining":
        await callback.answer("Гра вже недоступна.", show_alert=True)
        return

    user = callback.from_user
    local_remaining = _winner_cooldown_remaining(user.id)
    if local_remaining:
        await callback.answer(
            f"⏳ Після виграшу зачекай {_format_local_cooldown(local_remaining)}.",
            show_alert=True,
        )
        return
    if await is_game_on_cooldown(user.id):
        remaining = await get_game_cooldown_remaining(user.id)
        cooldown_text = (
            format_game_cooldown(*remaining) if remaining else "невідомо"
        )
        await callback.answer(
            f"⏳ Після виграшу зачекай ще {cooldown_text}.",
            show_alert=True,
        )
        return

    joined = False
    async with game["lock"]:
        if game["phase"] != "joining":
            answer = "Гра вже почалася."
        elif user.id in game["players"]:
            answer = "Ти вже в грі!"
        elif len(game["players"]) >= MAX_PLAYERS:
            answer = f"У грі вже максимум {MAX_PLAYERS} учасників."
        else:
            game["players"][user.id] = {
                "id": user.id,
                "name": get_display_name(user),
                "lives": START_LIVES,
                "alive": True,
                "correct_steps": 0,
            }
            answer = "✅ Ти приєднався!"
            joined = True

    await callback.answer(answer, show_alert=not answer.startswith("✅"))
    if joined:
        await _rate_limited_edit(
            chat_id,
            lambda: game["message"].edit_text(
                build_join_text(game),
                reply_markup=build_join_keyboard(),
                parse_mode="HTML",
            ),
        )


@router.callback_query(F.data == "maize_start")
async def begin_maize(callback: CallbackQuery) -> None:
    chat_id = callback.message.chat.id
    game = active_maize_games.get(chat_id)
    if not game or game["phase"] != "joining":
        await callback.answer("Гра вже недоступна.", show_alert=True)
        return
    if callback.from_user.id != game["admin_id"]:
        await callback.answer("Запустити гру може лише адмін.", show_alert=True)
        return

    async with game["lock"]:
        if len(game["players"]) < MIN_PLAYERS:
            await callback.answer(
                f"Потрібно щонайменше {MIN_PLAYERS} гравці.",
                show_alert=True,
            )
            return
        game["path"] = generate_path()
        game["phase"] = "playing"

    await callback.answer("🌽 Гра почалася!")
    await _rate_limited_edit(
        chat_id,
        lambda: game["message"].edit_text(
            build_game_text(game),
            reply_markup=build_field_keyboard(game),
            parse_mode="HTML",
        ),
    )


@router.callback_query(F.data.startswith("maize_cell_"))
async def maize_cell_click(callback: CallbackQuery) -> None:
    chat_id = callback.message.chat.id
    game = active_maize_games.get(chat_id)
    if not game or game["phase"] not in {"playing", "finishing"}:
        await callback.answer("Гра вже завершена.", show_alert=True)
        return

    try:
        parts = callback.data.split("_")
        if len(parts) == 5:
            _, _, raw_progress, raw_row, raw_col = parts
            button_progress = int(raw_progress)
        elif len(parts) == 4:
            # Compatibility with a keyboard created just before this update.
            _, _, raw_row, raw_col = parts
            button_progress = game["progress"]
        else:
            raise ValueError
        cell = (int(raw_row), int(raw_col))
    except (TypeError, ValueError):
        await callback.answer("Некоректна клітинка.", show_alert=True)
        return
    if not all(0 <= coordinate < FIELD_SIZE for coordinate in cell):
        await callback.answer("Некоректна клітинка.", show_alert=True)
        return

    user_id = callback.from_user.id
    winner_data = None
    async with game["lock"]:
        if game["phase"] != "playing":
            result = {"status": "finished"}
        elif user_id not in game["players"]:
            result = {"status": "not_player"}
        elif not game["players"][user_id]["alive"]:
            result = {"status": "dead"}
        elif button_progress != game["progress"]:
            result = {"status": "stale"}
        elif cell in game["correct_open"]:
            result = {"status": "already_correct"}
        elif cell in game["wrong_open"]:
            result = {"status": "already_wrong"}
        else:
            now = time.monotonic()
            elapsed = now - game["last_clicks"].get(user_id, 0)
            if elapsed < CLICK_COOLDOWN_SECONDS:
                result = {
                    "status": "cooldown",
                    "remaining": math.ceil(CLICK_COOLDOWN_SECONDS - elapsed),
                }
            else:
                game["last_clicks"][user_id] = now
                result = apply_move(game, user_id, cell)
                if result["status"] == "winner":
                    winner_data = (
                        result["winner_id"],
                        result["reason"],
                    )

    status = result["status"]
    if status in {"correct", "wrong"}:
        schedule_game_update(chat_id)
    elif status == "stale":
        update_task = game.get("update_task")
        if not update_task or update_task.done():
            schedule_game_update(chat_id)

    if status == "correct":
        await callback.answer("🟩 Правильний крок!")
    elif status == "wrong":
        suffix = " Ти вибув." if result["eliminated"] else ""
        await callback.answer(
            f"🟥 Неправильно. Життів: {result['lives']}.{suffix}",
            show_alert=True,
        )
    elif status == "winner":
        if result["winner_id"] == user_id and result["reason"] == "finish":
            await callback.answer("🏆 Ти дістався фінішу!", show_alert=True)
        else:
            await callback.answer("🏁 Гру завершено!")
    elif status == "cooldown":
        await callback.answer(
            f"⏳ Наступне натискання через {result['remaining']} с.",
            show_alert=True,
        )
    elif status == "invalid_move":
        await callback.answer(
            "↔️ Обери сусідню клітинку попереду або збоку.",
            show_alert=True,
        )
    elif status == "stale":
        await callback.answer(
            "🔄 Інший гравець уже зробив цей крок. Поле оновлюється.",
            show_alert=True,
        )
    elif status == "already_correct":
        await callback.answer(
            "🟩 Цю клітинку вже пройдено. Обери наступну біля останньої зеленої.",
            show_alert=True,
        )
    elif status == "already_wrong":
        await callback.answer("🟥 Ця клітинка вже перевірена.", show_alert=True)
    elif status == "not_player":
        await callback.answer("Ти не береш участі в цій грі.", show_alert=True)
    elif status == "dead":
        await callback.answer("Ти вже вибув із гри.", show_alert=True)
    else:
        await callback.answer("Гра вже завершена.", show_alert=True)

    if winner_data:
        await finish_maize(chat_id, winner_data[0], winner_data[1])


@router.callback_query(F.data.startswith("maize_direction_"))
async def maize_direction_hint(callback: CallbackQuery) -> None:
    await callback.answer("⬆️ Рухайтеся знизу догори.")


async def cancel_maize_game(chat_id: int, game: dict) -> bool:
    """Cancel a lobby or active game without selecting or paying a winner."""
    async with game["lock"]:
        if game["phase"] in {"finishing", "finished"}:
            return False
        game["phase"] = "finished"
        _cancel_update(game)

    await _rate_limited_edit(
        chat_id,
        lambda: game["message"].edit_text(
            "❌ <b>Гру Maize скасовано адміністратором.</b>",
            reply_markup=None,
            parse_mode="HTML",
        ),
    )
    active_maize_games.pop(chat_id, None)
    _last_api_call.pop(chat_id, None)
    _api_locks.pop(chat_id, None)
    return True


@router.callback_query(F.data == "maize_cancel")
async def cancel_maize_callback(callback: CallbackQuery) -> None:
    chat_id = callback.message.chat.id
    game = active_maize_games.get(chat_id)
    if not game:
        await callback.answer("Гра вже завершена.", show_alert=True)
        return
    if callback.from_user.id != game["admin_id"]:
        await callback.answer(
            "Скасувати гру може лише адмін, який її запустив.",
            show_alert=True,
        )
        return

    cancelled = await cancel_maize_game(chat_id, game)
    if cancelled:
        await callback.answer("Гру скасовано.")
    else:
        await callback.answer("Гра вже завершується.", show_alert=True)


@router.message(Command("stopmaize"))
async def stop_maize(message: Message) -> None:
    if message.from_user.id != ADMIN_ID:
        return
    chat_id = message.chat.id
    game = active_maize_games.get(chat_id)
    if not game:
        await message.answer("❌ Активної гри Maize немає.")
        return

    cancelled = await cancel_maize_game(chat_id, game)
    if not cancelled:
        await message.answer("⏳ Гра вже завершується.")
