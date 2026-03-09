from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
import asyncio
import logging
import random
import time
from handlers.config import ADMIN_ID
from aiogram.exceptions import TelegramRetryAfter
from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter
router = Router(name="group_minefield")
router.message.filter(F.chat.type.in_({"group", "supergroup"}))

# ==========================
# НАЛАШТУВАННЯ ГРИ (все редагуй тут)
# ==========================
FIELD_SIZE = 7

MONEY_CELLS_COUNT = 20
MONEY_PER_CELL = 10

HEART_CELLS_COUNT = 4
MINES_COUNT = 10
STEAL_COUNT = 10

START_LIVES = 2
MAX_PLAYERS = 2

COOLDOWN_SECONDS = 4
MESSAGE_DELAY = 0.8
DISPLAY_UPDATE_DELAY = 0.8
# ==========================

# ЕМОДЗІ
EMOJI_MONEY    = "💰"
EMOJI_HEART    = "❤️"
EMOJI_MINE     = "💣"
EMOJI_STEAL    = "🕵️"
EMOJI_DEAD     = "💀"
EMOJI_PLAYERS  = "👥 Учасники:"

active_minefields = {}


def get_display_name(user) -> str:
    return f"@{user.username}" if user.username else user.full_name


def generate_field():
    board = [["EMPTY" for _ in range(FIELD_SIZE)] for _ in range(FIELD_SIZE)]
    positions = [(i, j) for i in range(FIELD_SIZE) for j in range(FIELD_SIZE)]
    random.shuffle(positions)

    for _ in range(MONEY_CELLS_COUNT):
        x, y = positions.pop()
        board[x][y] = "MONEY"
    for _ in range(HEART_CELLS_COUNT):
        x, y = positions.pop()
        board[x][y] = "HEART"
    for _ in range(MINES_COUNT):
        x, y = positions.pop()
        board[x][y] = "MINE"
    for _ in range(STEAL_COUNT):
        x, y = positions.pop()
        board[x][y] = "STEAL"

    return board


def build_field_keyboard(game):
    kb = []
    for i in range(FIELD_SIZE):
        row = []
        for j in range(FIELD_SIZE):
            if game["revealed"][i][j]:
                cell = game["board"][i][j]
                emoji = {
                    "MONEY": EMOJI_MONEY,
                    "HEART": EMOJI_HEART,
                    "STEAL": EMOJI_STEAL,
                    "MINE": EMOJI_MINE,
                }.get(cell, "⬜")
                row.append(InlineKeyboardButton(text=emoji, callback_data=f"field_{i}_{j}"))
            else:
                row.append(InlineKeyboardButton(text="⬛", callback_data=f"field_{i}_{j}"))
        kb.append(row)
    return InlineKeyboardMarkup(inline_keyboard=kb)


def build_players_text(game):
    lines = [EMOJI_PLAYERS]
    for p in game["players"].values():
        status = f"{EMOJI_MONEY}{p['money']}  {EMOJI_HEART}{p['lives']}" if p["alive"] else EMOJI_DEAD
        lines.append(f"• {p['name']} {status}")
    return "\n".join(lines)

async def send_action(chat_id: int, text: str):
    """Публікує дію в чат з автоматичним обробленням flood control"""
    try:
        game = active_minefields.get(chat_id)
        if not game:
            return

        for attempt in range(3):  # максимум 3 спроби
            try:
                await asyncio.sleep(MESSAGE_DELAY)

                # Якщо вже 2+ повідомлення — видаляємо найстаріше
                if len(game.get("action_messages", [])) >= 2:
                    old_msg_id = game["action_messages"].pop(0)
                    try:
                        await game["message"].bot.delete_message(chat_id, old_msg_id)
                    except:
                        pass

                msg = await game["message"].bot.send_message(chat_id, text, parse_mode="HTML")
                game.setdefault("action_messages", []).append(msg.message_id)
                return  # успішно відправлено

            except TelegramRetryAfter as e:
                wait = e.retry_after + 1.0  # +1 сек на безпеку
                logging.warning(f"🚨 Flood control! Чекаємо {wait:.1f} сек перед повтором...")
                await asyncio.sleep(wait)

            except Exception as e:
                logging.error(f"Помилка при надсиланні action: {e}")
                break  # інша помилка — виходимо

    except Exception as e:
        logging.error(f"Критична помилка в send_action: {e}")

async def update_game_display(message, game):
    """Оновлення дисплею з debounce + ігнор "message is not modified" """
    try:
        if game.get("display_update_task") is not None:
            try:
                game["display_update_task"].cancel()
            except:
                pass

        async def delayed_update():
            try:
                await asyncio.sleep(DISPLAY_UPDATE_DELAY)
                async with game["edit_lock"]:
                    await message.edit_text(
                        f"<b>💣 МІННЕ ПОЛЕ 💣</b>\n\n"
                        f"{build_players_text(game)}\n\n"
                        f"Зібрано грошей: <b>{game['collected_money']}/{game['total_money']} грн</b>",
                        reply_markup=build_field_keyboard(game),
                        parse_mode="HTML"
                    )
            except TelegramBadRequest as e:
                # 🔥 САМЕ ЦЕ ПОВІДОМЛЕННЯ — ігноруємо безліччю
                if "message is not modified" in str(e).lower():
                    return  # нормально, нічого не робимо
                logging.warning(f"Помилка при оновленні дисплею: {e}")
            except Exception as e:
                logging.warning(f"Помилка при оновленні дисплею: {e}")

        game["display_update_task"] = asyncio.create_task(delayed_update())

    except Exception as e:
        logging.warning(f"Помилка при плануванні оновлення дисплею: {e}")


async def check_game_end(chat_id: int):
    game = active_minefields.get(chat_id)
    if not game or game["phase"] != "playing":
        return

    alive_players = [p for p in game["players"].values() if p["alive"]]

    if len(alive_players) <= 1 or game["collected_money"] >= game["total_money"]:
        await finish_minefield(chat_id)


# ==========================
# ЗАПУСК ГРИ
# ==========================
@router.message(Command("minefield"))
async def start_minefield(message: Message):
    if message.from_user.id != ADMIN_ID:
        try: await message.delete()
        except: pass
        return

    chat_id = message.chat.id
    if chat_id in active_minefields:
        await message.answer("❌ Гра вже запущена!")
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Прийняти участь", callback_data="join_minefield")],
        [InlineKeyboardButton(text="🚀 СТАРТ (тільки адмін)", callback_data="start_minefield")]
    ])

    msg = await message.answer(
        f"<b>💣 МІННЕ ПОЛЕ 💣</b>\n\n"
        f"💰 Кожна зелена клітинка = <b>{MONEY_PER_CELL} грн</b>\n"
        f"{EMOJI_HEART} Знаходь життя\n"
        f"{EMOJI_STEAL} Кради гроші\n"
        f"{EMOJI_MINE} Міни — вибір кого вибути\n\n"
        f"👥 Максимум <b>{MAX_PLAYERS} гравці</b>\n"
        f"Приєднуйтесь!",
        reply_markup=kb,
        parse_mode="HTML"
    )

    active_minefields[chat_id] = {
        "message": msg,
        "phase": "joining",
        "admin_id": message.from_user.id,
        "players": {},
        "board": None,
        "revealed": None,
        "total_money": MONEY_CELLS_COUNT * MONEY_PER_CELL,
        "collected_money": 0,
        "cooldowns": {},
        "lock": asyncio.Lock(),
        "edit_lock": asyncio.Lock(),
        "action_messages": [],
        "awaiting_choice": {},
        "display_update_task": None,
    }


# ==========================
# ПРИЄДНАННЯ + СТАРТ + КЛІКИ (без змін)
# ==========================
@router.callback_query(F.data == "join_minefield")
async def join_minefield(callback: CallbackQuery):
    chat_id = callback.message.chat.id
    user = callback.from_user
    game = active_minefields.get(chat_id)
    if not game or game["phase"] != "joining":
        return

    if user.id in game["players"]:
        await callback.answer("Ти вже в грі!", show_alert=True)
        return

    if len(game["players"]) >= MAX_PLAYERS:
        await callback.answer(f"❌ Максимум {MAX_PLAYERS} гравці!", show_alert=True)
        return

    game["players"][user.id] = {
        "name": get_display_name(user),
        "money": 0,
        "lives": START_LIVES,
        "alive": True
    }

    await callback.answer("✅ Ти приєднався!")

    places_left = MAX_PLAYERS - len(game["players"])
    places_text = f"Залишилось місць: <b>{places_left}</b>" if places_left > 0 else "🚫 Гра заповнена!"

    await callback.message.edit_text(
        f"<b>💣 МІННЕ ПОЛЕ 💣</b>\n\n"
        f"Гравців: <b>{len(game['players'])}/{MAX_PLAYERS}</b>\n"
        f"{places_text}\n\n"
        f"{build_players_text(game)}\n\n"
        f"Адмін, тисни СТАРТ коли готові!",
        reply_markup=callback.message.reply_markup,
        parse_mode="HTML"
    )


@router.callback_query(F.data == "start_minefield")
async def start_game(callback: CallbackQuery):
    chat_id = callback.message.chat.id
    game = active_minefields.get(chat_id)
    if not game or game["phase"] != "joining" or callback.from_user.id != game["admin_id"]:
        return

    if len(game["players"]) < 2:
        await callback.answer("Мінімум 2 гравці!", show_alert=True)
        return

    game["board"] = generate_field()
    game["revealed"] = [[False] * FIELD_SIZE for _ in range(FIELD_SIZE)]
    game["phase"] = "playing"

    await callback.message.edit_text(
        f"<b>💣 МІННЕ ПОЛЕ ЗАПУЩЕНО! 💣</b>\n\n"
        f"{build_players_text(game)}\n\n"
        f"🔥 Гра триває до останнього гравця або до збору всіх грошей!",
        reply_markup=build_field_keyboard(game),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("field_"))
async def field_click(callback: CallbackQuery):
    chat_id = callback.message.chat.id
    user_id = callback.from_user.id
    game = active_minefields.get(chat_id)
    if not game or game["phase"] != "playing":
        return

    player = game["players"].get(user_id)
    if not player or not player["alive"]:
        return

    now = time.time()
    if user_id in game["cooldowns"] and now - game["cooldowns"].get(user_id, 0) < COOLDOWN_SECONDS:
        await callback.answer(f"⏳ Кулдаун! Чекай {COOLDOWN_SECONDS} сек.", show_alert=True)
        return
    game["cooldowns"][user_id] = now

    async with game["lock"]:
        try:
            _, r, c = callback.data.split("_")
            row, col = int(r), int(c)
        except:
            await callback.answer("Помилка клітинки", show_alert=True)
            return

        if game["awaiting_choice"].get(user_id, False):
            await callback.answer("⛔ Спочатку обери з кнопок!", show_alert=True)
            return

        if game["revealed"][row][col]:
            await callback.answer("Вже відкрито!", show_alert=True)
            return

        game["revealed"][row][col] = True
        cell = game["board"][row][col]

        if cell == "MONEY":
            player["money"] += MONEY_PER_CELL
            game["collected_money"] += MONEY_PER_CELL

        elif cell == "HEART":
            player["lives"] += 1

        elif cell == "STEAL":
            buttons = []
            for uid, p in game["players"].items():
                if p["alive"] and p["money"] > 0 and uid != user_id:
                    buttons.append([InlineKeyboardButton(
                        text=f"{EMOJI_STEAL} Вкрасти у {p['name']}",
                        callback_data=f"steal_{user_id}_{uid}"
                    )])
            if buttons:
                game["awaiting_choice"][user_id] = True
                try:
                    await asyncio.sleep(MESSAGE_DELAY)
                    await callback.message.answer(f"🕵️ <b>{player['name']}</b> активував крадіжку! Вибери у кого вкрасти гроші:",
                                                  reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
                except Exception as e:
                    logging.warning(f"Помилка при надсиланні меню крадіжки: {e}")
            else:
                await send_action(chat_id, f"🕵️ <b>{player['name']}</b> активував крадіжку, але грошей немає!")

        elif cell == "MINE":
            buttons = [[InlineKeyboardButton(text=f"{EMOJI_DEAD} Підірвати себе", callback_data=f"mine_self_{user_id}")]]
            for uid, p in game["players"].items():
                if p["alive"] and uid != user_id:
                    buttons.append([InlineKeyboardButton(
                        text=f"{EMOJI_DEAD} Вибити {p['name']}",
                        callback_data=f"mine_kill_{user_id}_{uid}"
                    )])
            game["awaiting_choice"][user_id] = True
            try:
                await asyncio.sleep(MESSAGE_DELAY)
                await callback.message.answer(f"{EMOJI_MINE} <b>{player['name']}</b> наступив на міну! Обери кого вибити:",
                                              reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
            except Exception as e:
                logging.warning(f"Помилка при надсиланні меню міни: {e}")

        await update_game_display(callback.message, game)
        await check_game_end(chat_id)


# ==========================
# КРАДІЖКА + МІНА + ЗАВЕРШЕННЯ (без змін, тільки finish_minefield оновлено)
# ==========================
@router.callback_query(F.data.startswith("steal_"))
async def steal_money(callback: CallbackQuery):
    chat_id = callback.message.chat.id
    game = active_minefields.get(chat_id)
    if not game or game["phase"] != "playing":
        await callback.answer("❌ Гра закінчилась!", show_alert=True)
        return

    try:
        parts = callback.data.split("_")
        thief_id = int(parts[1])
        victim_id = int(parts[2])
    except:
        await callback.answer("❌ Помилка даних!", show_alert=True)
        return

    if callback.from_user.id != thief_id:
        await callback.answer("❌ Це не твоя кнопка!", show_alert=True)
        return

    async with game["lock"]:
        if thief_id not in game["players"] or victim_id not in game["players"]:
            await callback.answer("❌ Один з гравців уже вибув!", show_alert=True)
            return

        thief = game["players"][thief_id]
        victim = game["players"][victim_id]

        if not thief["alive"] or not victim["alive"]:
            await callback.answer("❌ Гравець вже вибув!", show_alert=True)
            return

        if victim["money"] > 0:
            stolen = victim["money"]
            thief["money"] += stolen
            victim["money"] = 0
            await send_action(chat_id, f"🕵️ <b>{thief['name']}</b> вкрав <b>{stolen} грн</b> у <b>{victim['name']}</b>!")
        else:
            await send_action(chat_id, f"🕵️ <b>{thief['name']}</b> спробував вкрасти, але грошей немає!")

        game["awaiting_choice"].pop(thief_id, None)

    try:
        await asyncio.sleep(MESSAGE_DELAY)
        await callback.message.delete()
    except:
        pass

    await callback.answer("✅", show_alert=False)
    await check_game_end(chat_id)


@router.callback_query(F.data.startswith("mine_"))
async def mine_action(callback: CallbackQuery):
    chat_id = callback.message.chat.id
    game = active_minefields.get(chat_id)
    if not game or game["phase"] != "playing":
        await callback.answer("❌ Гра закінчилась!", show_alert=True)
        return

    try:
        parts = callback.data.split("_")
        if parts[1] == "self":
            actor_id = int(parts[2])
            victim_id = None
        elif parts[1] == "kill":
            actor_id = int(parts[2])
            victim_id = int(parts[3])
        else:
            raise ValueError
    except:
        await callback.answer("❌ Помилка даних!", show_alert=True)
        return

    if callback.from_user.id != actor_id:
        await callback.answer("❌ Це не твоя кнопка!", show_alert=True)
        return

    async with game["lock"]:
        if actor_id not in game["players"]:
            await callback.answer("❌ Актор вже вибув!", show_alert=True)
            return

        actor = game["players"][actor_id]
        if not actor["alive"]:
            await callback.answer("❌ Ти вже вибув!", show_alert=True)
            return

        if victim_id is None:  # Підірвати себе
            actor["lives"] -= 1
            if actor["lives"] <= 0:
                actor["alive"] = False
                msg = f"💀 <b>{actor['name']}</b> вибив себе та вибув з гри!"
            else:
                msg = f"⚡ <b>{actor['name']}</b> вибив себе! Залишилось <b>{actor['lives']}</b> {get_lives_text(actor['lives'])}"
            await send_action(chat_id, msg)

        else:  # Вибити іншого
            if victim_id not in game["players"]:
                await callback.answer("❌ Жертва не знайдена!", show_alert=True)
                return
            victim = game["players"][victim_id]
            if not victim["alive"]:
                await callback.answer("❌ Жертва вже вибула!", show_alert=True)
                return

            victim["lives"] -= 1
            if victim["lives"] <= 0:
                victim["alive"] = False
                stolen = victim["money"]
                actor["money"] += stolen
                victim["money"] = 0
                msg = f"💀 <b>{actor['name']}</b> вибив <b>{victim['name']}</b> і забрав <b>{stolen} грн</b>!"
            else:
                msg = f"⚡ <b>{actor['name']}</b> поранив <b>{victim['name']}</b>! Залишилось <b>{victim['lives']}</b> {get_lives_text(victim['lives'])}"
            await send_action(chat_id, msg)

        game["awaiting_choice"].pop(actor_id, None)

    try:
        await asyncio.sleep(MESSAGE_DELAY)
        await callback.message.delete()
    except:
        pass

    await callback.answer("✅", show_alert=False)
    await check_game_end(chat_id)


def get_lives_text(lives: int) -> str:
    if lives % 10 == 1 and lives % 100 != 11:
        return "життя"
    return "життів"


# ==========================
# ЗАВЕРШЕННЯ ГРИ
# ==========================
async def finish_minefield(chat_id: int):
    game = active_minefields.get(chat_id)
    if not game or game["phase"] == "finished":
        return

    game["phase"] = "finished"

    # ВИПРАВЛЕНО: безпечне скасування задачі
    if game.get("display_update_task") is not None:
        try:
            game["display_update_task"].cancel()
        except:
            pass

    winners = sorted(game["players"].values(), key=lambda p: p["money"], reverse=True)

    text = f"🏆 <b>ГРА ЗАВЕРШЕНА!</b>\n\n<b>РЕЙТИНГ:</b>\n"
    for i, p in enumerate(winners, 1):
        emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "•"
        status = "✅ Живий" if p["alive"] else "💀 Вибув"
        text += f"{emoji} #{i} {p['name']} — {EMOJI_MONEY}<b>{p['money']} грн</b> ({status})\n"

    try:
        await game["message"].edit_text(text, reply_markup=None, parse_mode="HTML")
    except:
        pass

    del active_minefields[chat_id]