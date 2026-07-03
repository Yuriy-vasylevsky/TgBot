
# import logging
# import random
# import time
# import asyncio
# from aiogram import Router, F
# from aiogram.filters import Command
# from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
# from aiogram.exceptions import TelegramRetryAfter, TelegramBadRequest, TelegramForbiddenError
# from handlers.config import ADMIN_ID

# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
# router = Router(name="group_minefield")
# router.message.filter(F.chat.type.in_({"group", "supergroup"}))

# # ==========================
# # НАЛАШТУВАННЯ ГРИ
# # ==========================
# FIELD_SIZE = 7
# MONEY_CELLS_COUNT = 18
# MONEY_PER_CELL = 15
# DIAMOND_CELLS_COUNT = 5
# DIAMOND_PER_CELL = 25
# WIN_MONEY = 70
# HEART_CELLS_COUNT = 3
# MINES_COUNT = 14
# STEAL_COUNT = 9
# START_LIVES = 2
# MAX_PLAYERS = 3
# COOLDOWN_SECONDS = 5
# TURN_TIMEOUT = 10

# # === АНТИ-ФЛУД (збільшено спеціально для TG) ===
# API_CALL_INTERVAL = 1.8
# DISPLAY_DEBOUNCE = 2.0
# WINNER_COOLDOWN_HOURS = 12

# # ==========================
# EMOJI_MONEY = "💰"
# EMOJI_DIAMOND = "💎"
# EMOJI_HEART = "❤️"
# EMOJI_MINE = "💣"
# EMOJI_STEAL = "🕵️"
# EMOJI_DEAD = "💀"
# EMOJI_PLAYERS = "👥 Учасники:"

# active_minefields: dict = {}
# banned_players: dict = {}

# # ==========================
# # RATE-LIMITER
# # ==========================
# _last_api_call: dict[int, float] = {}
# _api_locks: dict[int, asyncio.Lock] = {}

# def _get_api_lock(chat_id: int) -> asyncio.Lock:
#     if chat_id not in _api_locks:
#         _api_locks[chat_id] = asyncio.Lock()
#     return _api_locks[chat_id]

# async def rate_limited_call(chat_id: int, factory):
#     async with _get_api_lock(chat_id):
#         since = time.monotonic() - _last_api_call.get(chat_id, 0)
#         if since < API_CALL_INTERVAL:
#             await asyncio.sleep(API_CALL_INTERVAL - since)

#         for attempt in range(3):
#             try:
#                 result = await factory()
#                 _last_api_call[chat_id] = time.monotonic()
#                 return result
#             except TelegramRetryAfter as e:
#                 wait = e.retry_after + 1.5
#                 logging.warning(f"[{chat_id}] Flood — чекаємо {wait:.1f}с")
#                 await asyncio.sleep(wait)
#             except (TelegramBadRequest, TelegramForbiddenError) as e:
#                 if "message is not modified" not in str(e).lower():
#                     logging.warning(f"[{chat_id}] {type(e).__name__}: {e}")
#                 return
#             except Exception as e:
#                 logging.error(f"[{chat_id}] rate_limited_call: {e}")
#                 return

# # ==========================
# # ДОПОМІЖНІ ФУНКЦІЇ
# # ==========================
# def get_display_name(user) -> str:
#     return f"@{user.username}" if user.username else user.full_name

# def generate_field():
#     board = [["EMPTY"] * FIELD_SIZE for _ in range(FIELD_SIZE)]
#     positions = [(i, j) for i in range(FIELD_SIZE) for j in range(FIELD_SIZE)]
#     random.shuffle(positions)
#     for kind, count in [("MONEY", MONEY_CELLS_COUNT), ("DIAMOND", DIAMOND_CELLS_COUNT),
#                         ("HEART", HEART_CELLS_COUNT), ("MINE", MINES_COUNT), ("STEAL", STEAL_COUNT)]:
#         for _ in range(count):
#             if not positions:
#                 break
#             x, y = positions.pop()
#             board[x][y] = kind
#     return board

# def build_field_keyboard(game) -> InlineKeyboardMarkup:
#     cell_emoji = {"MONEY": EMOJI_MONEY, "DIAMOND": EMOJI_DIAMOND,
#                   "HEART": EMOJI_HEART, "STEAL": EMOJI_STEAL, "MINE": EMOJI_MINE}
#     kb = []
#     for i in range(FIELD_SIZE):
#         row = []
#         for j in range(FIELD_SIZE):
#             emoji = cell_emoji.get(game["board"][i][j], "⬜") if game["revealed"][i][j] else "⬛"
#             row.append(InlineKeyboardButton(text=emoji, callback_data=f"field_{i}_{j}"))
#         kb.append(row)
#     return InlineKeyboardMarkup(inline_keyboard=kb)

# def build_main_text(game) -> str:
#     lines = ["<b>💣 МІННЕ ПОЛЕ 💣</b>\n", EMOJI_PLAYERS]
#     for p in game["players"].values():
#         status = f"{EMOJI_MONEY}{p['money']}/{WIN_MONEY} {EMOJI_HEART}{p['lives']}" if p["alive"] else EMOJI_DEAD
#         lines.append(f"• {p['name']} {status}")

#     action = game.get("log_action", "")
#     if action:
#         lines.append(f"\n📋 <b>Остання дія:</b>\n{action}")

#     cur = game.get("current_player")
#     if cur and cur in game["players"]:
#         lines.append(f"\n➡️ Зараз ходить: <b>{game['players'][cur]['name']}</b>")

#     return "\n".join(lines)

# # ==========================
# # ОНОВЛЕННЯ (одне повідомлення = менше спаму)
# # ==========================
# async def update_game_message(chat_id: int):
#     game = active_minefields.get(chat_id)
#     if not game or game["phase"] == "finished":
#         return

#     task: asyncio.Task = game.get("display_task")
#     if task and not task.done():
#         task.cancel()

#     async def _do():
#         try:
#             await asyncio.sleep(DISPLAY_DEBOUNCE)
#             g = active_minefields.get(chat_id)
#             if not g or g["phase"] == "finished":
#                 return
#             await rate_limited_call(
#                 chat_id,
#                 lambda: g["message"].edit_text(
#                     build_main_text(g),
#                     reply_markup=build_field_keyboard(g),
#                     parse_mode="HTML"
#                 )
#             )
#         except asyncio.CancelledError:
#             pass
#         except Exception as e:
#             logging.warning(f"update_game_message: {e}")

#     game["display_task"] = asyncio.create_task(_do())

# # ==========================
# # ЛОГІКА ХОДІВ
# # ==========================
# def _cancel_turn_task(game):
#     task = game.get("turn_task")
#     if task and not task.done():
#         task.cancel()
#     game["turn_task"] = None

# def schedule_turn_timeout(chat_id: int):
#     game = active_minefields.get(chat_id)
#     if not game:
#         return
#     _cancel_turn_task(game)

#     async def _timeout():
#         await asyncio.sleep(TURN_TIMEOUT)
#         g = active_minefields.get(chat_id)
#         if not g or g["phase"] != "playing":
#             return
#         if g["awaiting_choice"].get(g.get("current_player")):
#             return
#         skipped = g["players"].get(g["current_player"], {}).get("name", "?")
#         g["log_action"] = f"⏩ <b>{skipped}</b> не встиг — хід пропущено!"
#         await next_turn(chat_id)

#     game["turn_task"] = asyncio.create_task(_timeout())

# async def next_turn(chat_id: int):
#     game = active_minefields.get(chat_id)
#     if not game or game["phase"] != "playing":
#         return

#     alive = [uid for uid, p in game["players"].items() if p["alive"]]
#     if len(alive) <= 1:
#         await finish_minefield(chat_id)
#         return

#     game["queue"] = [uid for uid in game["queue"] if uid in alive]
#     if not game["queue"]:
#         await finish_minefield(chat_id)
#         return

#     game["current_turn"] = (game.get("current_turn", 0) + 1) % len(game["queue"])
#     game["current_player"] = game["queue"][game["current_turn"]]

#     await update_game_message(chat_id)
#     schedule_turn_timeout(chat_id)

# async def check_and_finish(chat_id: int) -> bool:
#     game = active_minefields.get(chat_id)
#     if not game or game["phase"] != "playing":
#         return True
#     if any(p["money"] >= WIN_MONEY for p in game["players"].values()) or \
#        len([p for p in game["players"].values() if p["alive"]]) <= 1:
#         await finish_minefield(chat_id)
#         return True
#     return False

# # ==========================
# # СТАРТ ГРИ
# # ==========================
# @router.message(Command("minefield"))
# async def start_minefield(message: Message):
#     if message.from_user.id != ADMIN_ID:
#         await message.delete()
#         return

#     chat_id = message.chat.id
#     if chat_id in active_minefields:
#         await message.answer("❌ Гра вже запущена!")
#         return

#     kb = InlineKeyboardMarkup(inline_keyboard=[
#         [InlineKeyboardButton(text="✅ Прийняти участь", callback_data="join_minefield")],
#         [InlineKeyboardButton(text="🚀 СТАРТ (тільки адмін)", callback_data="start_minefield")]
#     ])

#     msg = await message.answer(
#         f"<b>💣 МІННЕ ПОЛЕ 💣</b>\n\n"
#         f"💰 Клітинка = <b>{MONEY_PER_CELL} грн</b> | 💎 Алмаз = <b>{DIAMOND_PER_CELL} грн</b>\n"
#         f"🏆 Перший до <b>{WIN_MONEY} грн</b> — переможець!\n"
#         f"👥 Макс. <b>{MAX_PLAYERS} гравців</b>\nПриєднуйтесь!",
#         reply_markup=kb, parse_mode="HTML"
#     )

#     active_minefields[chat_id] = {
#         "message": msg,
#         "phase": "joining",
#         "admin_id": message.from_user.id,
#         "players": {},
#         "board": None,
#         "revealed": None,
#         "cooldowns": {},
#         "queue": [],
#         "current_turn": 0,
#         "current_player": None,
#         "lock": asyncio.Lock(),
#         "awaiting_choice": {},
#         "display_task": None,
#         "log_action": "",
#         "turn_task": None,
#     }

# # ==========================
# # ПРИЄДНАННЯ
# # ==========================
# @router.callback_query(F.data == "join_minefield")
# async def join_minefield(callback: CallbackQuery):
#     await callback.answer()
#     chat_id = callback.message.chat.id
#     user = callback.from_user
#     game = active_minefields.get(chat_id)
#     if not game or game["phase"] != "joining":
#         return
#     if user.id in game["players"]:
#         await callback.answer("Ти вже в грі!", show_alert=True)
#         return
#     if user.id in banned_players and time.time() < banned_players[user.id]:
#         left = int((banned_players[user.id] - time.time()) / 3600) + 1
#         await callback.answer(f"❌ Переможець! Зачекай {left} год.", show_alert=True)
#         return
#     if len(game["players"]) >= MAX_PLAYERS:
#         await callback.answer(f"❌ Максимум {MAX_PLAYERS} гравці!", show_alert=True)
#         return

#     game["players"][user.id] = {
#         "id": user.id, "name": get_display_name(user),
#         "money": 0, "lives": START_LIVES, "alive": True,
#     }

#     await callback.answer("✅ Ти приєднався!")
#     places_left = MAX_PLAYERS - len(game["players"])
#     places_text = f"Залишилось місць: <b>{places_left}</b>" if places_left > 0 else "🚫 Гра заповнена!"
#     player_list = "\n".join(f"• {p['name']}" for p in game["players"].values())

#     await rate_limited_call(chat_id, lambda: callback.message.edit_text(
#         f"<b>💣 МІННЕ ПОЛЕ 💣</b>\n\nГравців: <b>{len(game['players'])}/{MAX_PLAYERS}</b>\n"
#         f"{places_text}\n\n{EMOJI_PLAYERS}\n{player_list}\n\nАдмін, тисни СТАРТ!",
#         reply_markup=callback.message.reply_markup, parse_mode="HTML"
#     ))

# # ==========================
# # СТАРТ ПАРТІЇ
# # ==========================
# @router.callback_query(F.data == "start_minefield")
# async def start_game(callback: CallbackQuery):
#     await callback.answer()
#     chat_id = callback.message.chat.id
#     game = active_minefields.get(chat_id)
#     if not game or game["phase"] != "joining" or callback.from_user.id != game["admin_id"]:
#         return
#     if len(game["players"]) < 2:
#         await callback.answer("Мінімум 2 гравці!", show_alert=True)
#         return

#     queue = list(game["players"].keys())
#     random.shuffle(queue)
#     game["queue"] = queue
#     game["current_turn"] = 0
#     game["current_player"] = queue[0]
#     game["board"] = generate_field()
#     game["revealed"] = [[False] * FIELD_SIZE for _ in range(FIELD_SIZE)]
#     game["phase"] = "playing"

#     await rate_limited_call(chat_id, lambda: callback.message.edit_text(
#         build_main_text(game),
#         reply_markup=build_field_keyboard(game), parse_mode="HTML"
#     ))

#     schedule_turn_timeout(chat_id)

# # ==========================
# # КЛІК ПО ПОЛЮ
# # ==========================
# @router.callback_query(F.data.startswith("field_"))
# async def field_click(callback: CallbackQuery):
#     await callback.answer()
#     chat_id = callback.message.chat.id
#     user_id = callback.from_user.id
#     game = active_minefields.get(chat_id)
#     if not game or game["phase"] != "playing":
#         return
#     if user_id != game["current_player"]:
#         await callback.answer("❌ Не твій хід!", show_alert=True)
#         return

#     player = game["players"].get(user_id)
#     if not player or not player["alive"]:
#         return

#     now = time.time()
#     if now - game["cooldowns"].get(user_id, 0) < COOLDOWN_SECONDS:
#         await callback.answer(f"⏳ Зачекай {COOLDOWN_SECONDS}с", show_alert=True)
#         return
#     game["cooldowns"][user_id] = now
#     _cancel_turn_task(game)

#     async with game["lock"]:
#         try:
#             _, r, c = callback.data.split("_")
#             row, col = int(r), int(c)
#         except Exception:
#             return

#         if game["awaiting_choice"].get(user_id):
#             await callback.answer("⛔ Спочатку обери з кнопок!", show_alert=True)
#             return
#         if game["revealed"][row][col]:
#             await callback.answer("Вже відкрито!", show_alert=True)
#             return

#         game["revealed"][row][col] = True
#         cell = game["board"][row][col]
#         action = ""
#         auto_next = False

#         if cell == "MONEY":
#             player["money"] += MONEY_PER_CELL
#             action = f"💰 <b>{player['name']}</b> знайшов {MONEY_PER_CELL} грн!"
#             auto_next = True
#         elif cell == "HEART":
#             player["lives"] += 1
#             action = f"❤️ <b>{player['name']}</b> знайшов життя!"
#             auto_next = True
#         elif cell == "DIAMOND":
#             player["money"] += DIAMOND_PER_CELL
#             action = f"💎 <b>{player['name']}</b> знайшов алмаз! +{DIAMOND_PER_CELL} грн!"
#             auto_next = True
#         elif cell == "STEAL":
#             has_victims = any(p["alive"] and p["money"] > 0 and uid != user_id for uid, p in game["players"].items())
#             if has_victims:
#                 game["awaiting_choice"][user_id] = True
#             else:
#                 action = f"🕵️ <b>{player['name']}</b> крадіжка, але красти нічого!"
#                 auto_next = True
#         elif cell == "MINE":
#             alive_others = [uid for uid, p in game["players"].items() if p["alive"] and uid != user_id]
#             if random.random() < 0.4:
#                 player["lives"] -= 1
#                 if player["lives"] <= 0:
#                     player["alive"] = False
#                     player["money"] = 0
#                     action = f"💥 Міна вибухнула! <b>{player['name']}</b> вибув і втратив всі гроші!"
#                 else:
#                     action = f"💥 Міна вибухнула на <b>{player['name']}</b>! {player['lives']} життів"
#                 auto_next = True
#             elif alive_others:
#                 game["awaiting_choice"][user_id] = True
#             else:
#                 action = f"💨 <b>{player['name']}</b> наступив на міну, але вона не спрацювала!"
#                 auto_next = True

#     # === обробка вибору ===
#     if cell == "STEAL" and game["awaiting_choice"].get(user_id):
#         buttons = [[InlineKeyboardButton(text="🚫 Не красти", callback_data=f"steal_cancel_{user_id}")]]
#         for uid, p in game["players"].items():
#             if p["alive"] and p["money"] > 0 and uid != user_id:
#                 buttons.append([InlineKeyboardButton(text=f"{EMOJI_STEAL} Вкрасти у {p['name']}", callback_data=f"steal_{user_id}_{uid}")])
#         await rate_limited_call(chat_id, lambda: callback.message.bot.send_message(
#             chat_id, f"🕵️ <b>{player['name']}</b>, обери у кого вкрасти:", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML"
#         ))
#         return

#     if cell == "MINE" and game["awaiting_choice"].get(user_id):
#         buttons = []
#         for uid, p in game["players"].items():
#             if p["alive"] and uid != user_id:
#                 buttons.append([InlineKeyboardButton(text=f"{EMOJI_DEAD} Кинути міну в {p['name']}", callback_data=f"mine_kill_{user_id}_{uid}")])
#         await rate_limited_call(chat_id, lambda: callback.message.bot.send_message(
#             chat_id, f"💣 <b>{player['name']}</b> Обери кому кинути міну:", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML"
#         ))
#         return

#     if action:
#         game["log_action"] = action

#     finished = await check_and_finish(chat_id)
#     if not finished:
#         if auto_next:
#             await update_game_message(chat_id)
#             await next_turn(chat_id)
#         else:
#             await update_game_message(chat_id)

# # ==========================
# # КРАДІЖКА
# # ==========================
# @router.callback_query(F.data.startswith("steal_"))
# async def steal_money(callback: CallbackQuery):
#     await callback.answer()
#     chat_id = callback.message.chat.id
#     game = active_minefields.get(chat_id)
#     if not game or game["phase"] != "playing":
#         return

#     parts = callback.data.split("_")
#     if parts[1] == "cancel":
#         thief_id = int(parts[2])
#         if callback.from_user.id != thief_id:
#             return
#         game["awaiting_choice"].pop(thief_id, None)
#         try:
#             await callback.message.delete()
#         except:
#             pass
#         if not await check_and_finish(chat_id):
#             game["log_action"] = f"🕵️ <b>{game['players'][thief_id]['name']}</b> вирішив не красти"
#             await next_turn(chat_id)
#         return

#     thief_id = int(parts[1])
#     victim_id = int(parts[2])
#     if callback.from_user.id != thief_id:
#         return

#     async with game["lock"]:
#         thief = game["players"].get(thief_id)
#         victim = game["players"].get(victim_id)
#         if not thief or not victim or not thief["alive"] or not victim["alive"]:
#             return
#         if victim["money"] <= 0:
#             return

#         if random.random() < 0.5:
#             stolen = victim["money"]
#             thief["money"] += stolen
#             victim["money"] = 0
#             action = f"🕵️ <b>{thief['name']}</b> вкрав ВСІ <b>{stolen} грн</b> у <b>{victim['name']}</b>!"
#         else:
#             given = thief["money"]
#             victim["money"] += given
#             thief["money"] = 0
#             action = f"😇 Совість! <b>{thief['name']}</b> віддав ВСІ свої <b>{given} грн</b> гравцю <b>{victim['name']}</b>!"

#         game["awaiting_choice"].pop(thief_id, None)

#     try:
#         await callback.message.delete()
#     except:
#         pass

#     if not await check_and_finish(chat_id):
#         game["log_action"] = action
#         await update_game_message(chat_id)
#         await next_turn(chat_id)

# # ==========================
# # МІНА
# # ==========================
# @router.callback_query(F.data.startswith("mine_kill_"))
# async def mine_action(callback: CallbackQuery):
#     await callback.answer()
#     chat_id = callback.message.chat.id
#     game = active_minefields.get(chat_id)
#     if not game or game["phase"] != "playing":
#         return

#     parts = callback.data.split("_")
#     actor_id = int(parts[2])
#     victim_id = int(parts[3])
#     if callback.from_user.id != actor_id:
#         return

#     async with game["lock"]:
#         actor = game["players"].get(actor_id)
#         victim = game["players"].get(victim_id)
#         if not actor or not victim or not victim["alive"]:
#             return

#         victim["lives"] -= 1
#         if victim["lives"] <= 0:
#             victim["alive"] = False
#             stolen = victim["money"]
#             actor["money"] += stolen
#             victim["money"] = 0
#             action = f"💀 <b>{actor['name']}</b> кинув міну в <b>{victim['name']}</b> — вибув! +{stolen} грн"
#         else:
#             action = f"💣 <b>{actor['name']}</b> кинув міну в <b>{victim['name']}</b>! Залишилось {victim['lives']} життів"

#         game["awaiting_choice"].pop(actor_id, None)

#     try:
#         await callback.message.delete()
#     except:
#         pass

#     if not await check_and_finish(chat_id):
#         game["log_action"] = action
#         await update_game_message(chat_id)
#         await next_turn(chat_id)

# # ==========================
# # СТОП ГРИ
# # ==========================
# @router.message(Command("stopmine"))
# async def stop_minefield(message: Message):
#     if message.from_user.id != ADMIN_ID:
#         return
#     chat_id = message.chat.id
#     if chat_id in active_minefields:
#         await finish_minefield(chat_id)
#         await message.answer("🛑 Гра примусово зупинена")
#     else:
#         await message.answer("❌ Активної гри немає")

# # ==========================
# # ЗАВЕРШЕННЯ ГРИ
# # ==========================
# async def finish_minefield(chat_id: int):
#     game = active_minefields.get(chat_id)
#     if not game or game["phase"] == "finished":
#         return
#     game["phase"] = "finished"

#     if game.get("display_task"):
#         game["display_task"].cancel()
#     _cancel_turn_task(game)

#     winners = sorted(game["players"].values(), key=lambda p: (p["alive"], p["money"]), reverse=True)
#     win_reason = "💰 Перший досяг 70 грн!" if any(p["money"] >= WIN_MONEY for p in winners) else "⚔️ Останній вцілілий!"
#     prize = WIN_MONEY if winners and winners[0]["money"] >= WIN_MONEY else 50

#     text = f"🏆 <b>ГРА ЗАВЕРШЕНА!</b> {win_reason}\n\n<b>РЕЙТИНГ:</b>\n"
#     for i, p in enumerate(winners, 1):
#         medal = ("🥇", "🥈", "🥉")[i-1] if i <= 3 else "•"
#         status = "✅ Живий" if p["alive"] else "💀 Вибув"
#         if i == 1:
#             text += f"{medal} 🏆 <b>{p['name']}</b> — ПРИЗ <b>{prize} грн</b> ({status})\n"
#         else:
#             text += f"{medal} {p['name']} — {EMOJI_MONEY}<b>{p['money']} грн</b> ({status})\n"

#     if winners and winners[0]["money"] > 0:
#         banned_players[winners[0]["id"]] = time.time() + WINNER_COOLDOWN_HOURS * 3600
#         text += f"\n🥇 {winners[0]['name']} забанений на {WINNER_COOLDOWN_HOURS} годин."

#     await rate_limited_call(
#         chat_id,
#         lambda: game["message"].edit_text(text, reply_markup=None, parse_mode="HTML")
#     )

#     active_minefields.pop(chat_id, None)
#     _last_api_call.pop(chat_id, None)
#     _api_locks.pop(chat_id, None)


import logging
import random
import time
import asyncio
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.exceptions import TelegramRetryAfter, TelegramBadRequest, TelegramForbiddenError
from handlers.config import ADMIN_ID

from db import add_money_win, add_daily_game_win
from db.game_cooldown import (
    is_game_on_cooldown,
    get_game_cooldown_remaining,
    set_game_cooldown,
    format_cooldown as format_game_cooldown,
)
from db.wallet import (
    add_to_balance,
    get_daily_net,
    get_yesterday_net,
    get_daily_game_win,
    get_yesterday_game_win,
)
from db.winlog import log_win

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
router = Router(name="group_minefield")
router.message.filter(F.chat.type.in_({"group", "supergroup"}))

# ==========================
# НАЛАШТУВАННЯ ГРИ
# ==========================
FIELD_SIZE = 7
MONEY_CELLS_COUNT = 18
MONEY_PER_CELL = 15
DIAMOND_CELLS_COUNT = 5
DIAMOND_PER_CELL = 25
WIN_MONEY = 70
HEART_CELLS_COUNT = 3
MINES_COUNT = 14
STEAL_COUNT = 9
START_LIVES = 2
MAX_PLAYERS = 3
COOLDOWN_SECONDS = 5
TURN_TIMEOUT = 10

# === АНТИ-ФЛУД (збільшено спеціально для TG) ===
API_CALL_INTERVAL = 1.8
DISPLAY_DEBOUNCE = 2.0
WINNER_COOLDOWN_HOURS = 12

# ==========================
EMOJI_MONEY = "💰"
EMOJI_DIAMOND = "💎"
EMOJI_HEART = "❤️"
EMOJI_MINE = "💣"
EMOJI_STEAL = "🕵️"
EMOJI_DEAD = "💀"
EMOJI_PLAYERS = "👥 Учасники:"

active_minefields: dict = {}
banned_players: dict = {}

# ==========================
# RATE-LIMITER
# ==========================
_last_api_call: dict[int, float] = {}
_api_locks: dict[int, asyncio.Lock] = {}

def _get_api_lock(chat_id: int) -> asyncio.Lock:
    if chat_id not in _api_locks:
        _api_locks[chat_id] = asyncio.Lock()
    return _api_locks[chat_id]

async def rate_limited_call(chat_id: int, factory):
    async with _get_api_lock(chat_id):
        since = time.monotonic() - _last_api_call.get(chat_id, 0)
        if since < API_CALL_INTERVAL:
            await asyncio.sleep(API_CALL_INTERVAL - since)

        for attempt in range(3):
            try:
                result = await factory()
                _last_api_call[chat_id] = time.monotonic()
                return result
            except TelegramRetryAfter as e:
                wait = e.retry_after + 1.5
                logging.warning(f"[{chat_id}] Flood — чекаємо {wait:.1f}с")
                await asyncio.sleep(wait)
            except (TelegramBadRequest, TelegramForbiddenError) as e:
                if "message is not modified" not in str(e).lower():
                    logging.warning(f"[{chat_id}] {type(e).__name__}: {e}")
                return
            except Exception as e:
                logging.error(f"[{chat_id}] rate_limited_call: {e}")
                return

# ==========================
# ДОПОМІЖНІ ФУНКЦІЇ (виплата — як у wordle)
# ==========================
def _positive_or_zero(value: int) -> int:
    return value if value > 0 else 0


def is_on_cooldown(user_id: int) -> tuple[bool, int]:
    if user_id in banned_players:
        remaining = banned_players[user_id] - time.time()
        if remaining > 0:
            return True, int(remaining)
        del banned_players[user_id]
    return False, 0


def format_cooldown(remaining_seconds: int) -> str:
    hours = remaining_seconds // 3600
    minutes = (remaining_seconds % 3600) // 60
    seconds = remaining_seconds % 60
    parts = []
    if hours: parts.append(f"{hours}г")
    if minutes: parts.append(f"{minutes}хв")
    if seconds and not hours and not minutes: parts.append(f"{seconds}с")
    return " ".join(parts) or "менше хвилини"


async def _payout_winner(chat_id: int, bot, user_id: int, name: str, taken: int) -> int:
    """Повертає суму, яку реально нараховано на баланс (0, якщо нічого не нараховано)."""
    if taken <= 0:
        return 0

    today_net = await get_daily_net(user_id)
    yesterday_net = await get_yesterday_net(user_id)
    total_net = _positive_or_zero(today_net) + _positive_or_zero(yesterday_net)

    if total_net <= 0:
        # Немає депозиту — гроші не нараховуємо, кулдаун гри НЕ ставимо
        await bot.send_message(
            chat_id=chat_id,
            text=(
                f"👤 <b>{name}</b> — виграш <b>{taken} грн</b>\n"
                f"❌ Не було депозиту! Виграш не нараховано❗"
            ),
            parse_mode="HTML"
        )
        return 0

    daily_game_win = await get_daily_game_win(user_id)
    yesterday_game_win = await get_yesterday_game_win(user_id)

    already_won = _positive_or_zero(daily_game_win) + _positive_or_zero(yesterday_game_win)
    # Ліміт пропорційний депозиту: 80 грн на кожні 200 грн депу
    max_allowed_win = int(total_net * 80 / 200)
    available_limit = max(max_allowed_win - already_won, 0)

    payout_amount = min(taken, available_limit)

    if payout_amount > 0:
        await add_to_balance(user_id, payout_amount)
        await add_daily_game_win(user_id, payout_amount)
        # Кулдаун гри ставимо ТІЛЬКИ якщо гроші реально нараховано на баланс
        await set_game_cooldown(user_id)

        await log_win(user_id, None, name, "group", "Minefield", payout_amount)

    await add_money_win(user_id, taken)

    if payout_amount >= taken:
        await bot.send_message(
            chat_id=chat_id,
            text=(
                f"👤 <b>{name}</b> — виграш <b>{taken} грн</b>\n"
                f"✅ Нараховано на баланс 💸"
            ),
            parse_mode="HTML"
        )
    elif payout_amount > 0:
        await bot.send_message(
            chat_id=chat_id,
            text=(
                f"👤 <b>{name}</b> — виграш <b>{taken} грн</b>\n"
                f"⚠️ Ліміт виграшів вичерпано.\n"
                f"Вам зараховано <b>{payout_amount} грн</b> на баланс."
            ),
            parse_mode="HTML"
        )
    else:
        # Ліміт вичерпано повністю — нічого не нараховано, кулдаун гри НЕ ставимо
        await bot.send_message(
            chat_id=chat_id,
            text=(
                f"👤 <b>{name}</b> — виграш <b>{taken} грн</b>\n"
                f"❌ Ліміт виграшів вичерпано."
            ),
            parse_mode="HTML"
        )

    return payout_amount


def get_display_name(user) -> str:
    return f"@{user.username}" if user.username else user.full_name

def generate_field():
    board = [["EMPTY"] * FIELD_SIZE for _ in range(FIELD_SIZE)]
    positions = [(i, j) for i in range(FIELD_SIZE) for j in range(FIELD_SIZE)]
    random.shuffle(positions)
    for kind, count in [("MONEY", MONEY_CELLS_COUNT), ("DIAMOND", DIAMOND_CELLS_COUNT),
                        ("HEART", HEART_CELLS_COUNT), ("MINE", MINES_COUNT), ("STEAL", STEAL_COUNT)]:
        for _ in range(count):
            if not positions:
                break
            x, y = positions.pop()
            board[x][y] = kind
    return board

def build_field_keyboard(game) -> InlineKeyboardMarkup:
    cell_emoji = {"MONEY": EMOJI_MONEY, "DIAMOND": EMOJI_DIAMOND,
                  "HEART": EMOJI_HEART, "STEAL": EMOJI_STEAL, "MINE": EMOJI_MINE}
    kb = []
    for i in range(FIELD_SIZE):
        row = []
        for j in range(FIELD_SIZE):
            emoji = cell_emoji.get(game["board"][i][j], "⬜") if game["revealed"][i][j] else "⬛"
            row.append(InlineKeyboardButton(text=emoji, callback_data=f"field_{i}_{j}"))
        kb.append(row)
    return InlineKeyboardMarkup(inline_keyboard=kb)

def build_main_text(game) -> str:
    lines = ["<b>💣 МІННЕ ПОЛЕ 💣</b>\n", EMOJI_PLAYERS]
    for p in game["players"].values():
        status = f"{EMOJI_MONEY}{p['money']}/{WIN_MONEY} {EMOJI_HEART}{p['lives']}" if p["alive"] else EMOJI_DEAD
        lines.append(f"• {p['name']} {status}")

    action = game.get("log_action", "")
    if action:
        lines.append(f"\n📋 <b>Остання дія:</b>\n{action}")

    cur = game.get("current_player")
    if cur and cur in game["players"]:
        lines.append(f"\n➡️ Зараз ходить: <b>{game['players'][cur]['name']}</b>")

    return "\n".join(lines)

# ==========================
# ОНОВЛЕННЯ (одне повідомлення = менше спаму)
# ==========================
async def update_game_message(chat_id: int):
    game = active_minefields.get(chat_id)
    if not game or game["phase"] == "finished":
        return

    task: asyncio.Task = game.get("display_task")
    if task and not task.done():
        task.cancel()

    async def _do():
        try:
            await asyncio.sleep(DISPLAY_DEBOUNCE)
            g = active_minefields.get(chat_id)
            if not g or g["phase"] == "finished":
                return
            await rate_limited_call(
                chat_id,
                lambda: g["message"].edit_text(
                    build_main_text(g),
                    reply_markup=build_field_keyboard(g),
                    parse_mode="HTML"
                )
            )
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logging.warning(f"update_game_message: {e}")

    game["display_task"] = asyncio.create_task(_do())

# ==========================
# ЛОГІКА ХОДІВ
# ==========================
def _cancel_turn_task(game):
    task = game.get("turn_task")
    if task and not task.done():
        task.cancel()
    game["turn_task"] = None

def schedule_turn_timeout(chat_id: int):
    game = active_minefields.get(chat_id)
    if not game:
        return
    _cancel_turn_task(game)

    async def _timeout():
        await asyncio.sleep(TURN_TIMEOUT)
        g = active_minefields.get(chat_id)
        if not g or g["phase"] != "playing":
            return
        if g["awaiting_choice"].get(g.get("current_player")):
            return
        skipped = g["players"].get(g["current_player"], {}).get("name", "?")
        g["log_action"] = f"⏩ <b>{skipped}</b> не встиг — хід пропущено!"
        await next_turn(chat_id)

    game["turn_task"] = asyncio.create_task(_timeout())

async def next_turn(chat_id: int):
    game = active_minefields.get(chat_id)
    if not game or game["phase"] != "playing":
        return

    alive = [uid for uid, p in game["players"].items() if p["alive"]]
    if len(alive) <= 1:
        await finish_minefield(chat_id)
        return

    game["queue"] = [uid for uid in game["queue"] if uid in alive]
    if not game["queue"]:
        await finish_minefield(chat_id)
        return

    game["current_turn"] = (game.get("current_turn", 0) + 1) % len(game["queue"])
    game["current_player"] = game["queue"][game["current_turn"]]

    await update_game_message(chat_id)
    schedule_turn_timeout(chat_id)

async def check_and_finish(chat_id: int) -> bool:
    game = active_minefields.get(chat_id)
    if not game or game["phase"] != "playing":
        return True
    if any(p["money"] >= WIN_MONEY for p in game["players"].values()) or \
       len([p for p in game["players"].values() if p["alive"]]) <= 1:
        await finish_minefield(chat_id)
        return True
    return False

# ==========================
# СТАРТ ГРИ
# ==========================
@router.message(Command("minefield"))
async def start_minefield(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.delete()
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
        f"💰 Клітинка = <b>{MONEY_PER_CELL} грн</b> | 💎 Алмаз = <b>{DIAMOND_PER_CELL} грн</b>\n"
        f"🏆 Перший до <b>{WIN_MONEY} грн</b> — переможець!\n"
        f"👥 Макс. <b>{MAX_PLAYERS} гравців</b>\nПриєднуйтесь!",
        reply_markup=kb, parse_mode="HTML"
    )

    active_minefields[chat_id] = {
        "message": msg,
        "phase": "joining",
        "admin_id": message.from_user.id,
        "players": {},
        "board": None,
        "revealed": None,
        "cooldowns": {},
        "queue": [],
        "current_turn": 0,
        "current_player": None,
        "lock": asyncio.Lock(),
        "awaiting_choice": {},
        "display_task": None,
        "log_action": "",
        "turn_task": None,
    }

# ==========================
# ПРИЄДНАННЯ
# ==========================
@router.callback_query(F.data == "join_minefield")
async def join_minefield(callback: CallbackQuery):
    await callback.answer()
    chat_id = callback.message.chat.id
    user = callback.from_user
    game = active_minefields.get(chat_id)
    if not game or game["phase"] != "joining":
        return
    if user.id in game["players"]:
        await callback.answer("Ти вже в грі!", show_alert=True)
        return

    on_cd, remaining = is_on_cooldown(user.id)
    if on_cd:
        await callback.answer(f"❌ Переможець! Зачекай {format_cooldown(remaining)}.", show_alert=True)
        return

    if await is_game_on_cooldown(user.id):
        rem = await get_game_cooldown_remaining(user.id)
        cd_text = format_game_cooldown(*rem) if rem else "невідомо"
        await callback.answer(f"⏳ Не так швидко! Зачекай ще {cd_text}", show_alert=True)
        return

    if len(game["players"]) >= MAX_PLAYERS:
        await callback.answer(f"❌ Максимум {MAX_PLAYERS} гравці!", show_alert=True)
        return

    game["players"][user.id] = {
        "id": user.id, "name": get_display_name(user),
        "money": 0, "lives": START_LIVES, "alive": True,
    }

    await callback.answer("✅ Ти приєднався!")
    places_left = MAX_PLAYERS - len(game["players"])
    places_text = f"Залишилось місць: <b>{places_left}</b>" if places_left > 0 else "🚫 Гра заповнена!"
    player_list = "\n".join(f"• {p['name']}" for p in game["players"].values())

    await rate_limited_call(chat_id, lambda: callback.message.edit_text(
        f"<b>💣 МІННЕ ПОЛЕ 💣</b>\n\nГравців: <b>{len(game['players'])}/{MAX_PLAYERS}</b>\n"
        f"{places_text}\n\n{EMOJI_PLAYERS}\n{player_list}\n\nАдмін, тисни СТАРТ!",
        reply_markup=callback.message.reply_markup, parse_mode="HTML"
    ))

# ==========================
# СТАРТ ПАРТІЇ
# ==========================
@router.callback_query(F.data == "start_minefield")
async def start_game(callback: CallbackQuery):
    await callback.answer()
    chat_id = callback.message.chat.id
    game = active_minefields.get(chat_id)
    if not game or game["phase"] != "joining" or callback.from_user.id != game["admin_id"]:
        return
    if len(game["players"]) < 2:
        await callback.answer("Мінімум 2 гравці!", show_alert=True)
        return

    queue = list(game["players"].keys())
    random.shuffle(queue)
    game["queue"] = queue
    game["current_turn"] = 0
    game["current_player"] = queue[0]
    game["board"] = generate_field()
    game["revealed"] = [[False] * FIELD_SIZE for _ in range(FIELD_SIZE)]
    game["phase"] = "playing"

    await rate_limited_call(chat_id, lambda: callback.message.edit_text(
        build_main_text(game),
        reply_markup=build_field_keyboard(game), parse_mode="HTML"
    ))

    schedule_turn_timeout(chat_id)

# ==========================
# КЛІК ПО ПОЛЮ
# ==========================
@router.callback_query(F.data.startswith("field_"))
async def field_click(callback: CallbackQuery):
    await callback.answer()
    chat_id = callback.message.chat.id
    user_id = callback.from_user.id
    game = active_minefields.get(chat_id)
    if not game or game["phase"] != "playing":
        return
    if user_id != game["current_player"]:
        await callback.answer("❌ Не твій хід!", show_alert=True)
        return

    player = game["players"].get(user_id)
    if not player or not player["alive"]:
        return

    now = time.time()
    if now - game["cooldowns"].get(user_id, 0) < COOLDOWN_SECONDS:
        await callback.answer(f"⏳ Зачекай {COOLDOWN_SECONDS}с", show_alert=True)
        return
    game["cooldowns"][user_id] = now
    _cancel_turn_task(game)

    async with game["lock"]:
        try:
            _, r, c = callback.data.split("_")
            row, col = int(r), int(c)
        except Exception:
            return

        if game["awaiting_choice"].get(user_id):
            await callback.answer("⛔ Спочатку обери з кнопок!", show_alert=True)
            return
        if game["revealed"][row][col]:
            await callback.answer("Вже відкрито!", show_alert=True)
            return

        game["revealed"][row][col] = True
        cell = game["board"][row][col]
        action = ""
        auto_next = False

        if cell == "MONEY":
            player["money"] += MONEY_PER_CELL
            action = f"💰 <b>{player['name']}</b> знайшов {MONEY_PER_CELL} грн!"
            auto_next = True
        elif cell == "HEART":
            player["lives"] += 1
            action = f"❤️ <b>{player['name']}</b> знайшов життя!"
            auto_next = True
        elif cell == "DIAMOND":
            player["money"] += DIAMOND_PER_CELL
            action = f"💎 <b>{player['name']}</b> знайшов алмаз! +{DIAMOND_PER_CELL} грн!"
            auto_next = True
        elif cell == "STEAL":
            has_victims = any(p["alive"] and p["money"] > 0 and uid != user_id for uid, p in game["players"].items())
            if has_victims:
                game["awaiting_choice"][user_id] = True
            else:
                action = f"🕵️ <b>{player['name']}</b> крадіжка, але красти нічого!"
                auto_next = True
        elif cell == "MINE":
            alive_others = [uid for uid, p in game["players"].items() if p["alive"] and uid != user_id]
            if random.random() < 0.4:
                player["lives"] -= 1
                if player["lives"] <= 0:
                    player["alive"] = False
                    player["money"] = 0
                    action = f"💥 Міна вибухнула! <b>{player['name']}</b> вибув і втратив всі гроші!"
                else:
                    action = f"💥 Міна вибухнула на <b>{player['name']}</b>! {player['lives']} життів"
                auto_next = True
            elif alive_others:
                game["awaiting_choice"][user_id] = True
            else:
                action = f"💨 <b>{player['name']}</b> наступив на міну, але вона не спрацювала!"
                auto_next = True

    # === обробка вибору ===
    if cell == "STEAL" and game["awaiting_choice"].get(user_id):
        buttons = [[InlineKeyboardButton(text="🚫 Не красти", callback_data=f"steal_cancel_{user_id}")]]
        for uid, p in game["players"].items():
            if p["alive"] and p["money"] > 0 and uid != user_id:
                buttons.append([InlineKeyboardButton(text=f"{EMOJI_STEAL} Вкрасти у {p['name']}", callback_data=f"steal_{user_id}_{uid}")])
        await rate_limited_call(chat_id, lambda: callback.message.bot.send_message(
            chat_id, f"🕵️ <b>{player['name']}</b>, обери у кого вкрасти:", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML"
        ))
        return

    if cell == "MINE" and game["awaiting_choice"].get(user_id):
        buttons = []
        for uid, p in game["players"].items():
            if p["alive"] and uid != user_id:
                buttons.append([InlineKeyboardButton(text=f"{EMOJI_DEAD} Кинути міну в {p['name']}", callback_data=f"mine_kill_{user_id}_{uid}")])
        await rate_limited_call(chat_id, lambda: callback.message.bot.send_message(
            chat_id, f"💣 <b>{player['name']}</b> Обери кому кинути міну:", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML"
        ))
        return

    if action:
        game["log_action"] = action

    finished = await check_and_finish(chat_id)
    if not finished:
        if auto_next:
            await update_game_message(chat_id)
            await next_turn(chat_id)
        else:
            await update_game_message(chat_id)

# ==========================
# КРАДІЖКА
# ==========================
@router.callback_query(F.data.startswith("steal_"))
async def steal_money(callback: CallbackQuery):
    await callback.answer()
    chat_id = callback.message.chat.id
    game = active_minefields.get(chat_id)
    if not game or game["phase"] != "playing":
        return

    parts = callback.data.split("_")
    if parts[1] == "cancel":
        thief_id = int(parts[2])
        if callback.from_user.id != thief_id:
            return
        game["awaiting_choice"].pop(thief_id, None)
        try:
            await callback.message.delete()
        except:
            pass
        if not await check_and_finish(chat_id):
            game["log_action"] = f"🕵️ <b>{game['players'][thief_id]['name']}</b> вирішив не красти"
            await next_turn(chat_id)
        return

    thief_id = int(parts[1])
    victim_id = int(parts[2])
    if callback.from_user.id != thief_id:
        return

    async with game["lock"]:
        thief = game["players"].get(thief_id)
        victim = game["players"].get(victim_id)
        if not thief or not victim or not thief["alive"] or not victim["alive"]:
            return
        if victim["money"] <= 0:
            return

        if random.random() < 0.5:
            stolen = victim["money"]
            thief["money"] += stolen
            victim["money"] = 0
            action = f"🕵️ <b>{thief['name']}</b> вкрав ВСІ <b>{stolen} грн</b> у <b>{victim['name']}</b>!"
        else:
            given = thief["money"]
            victim["money"] += given
            thief["money"] = 0
            action = f"😇 Совість! <b>{thief['name']}</b> віддав ВСІ свої <b>{given} грн</b> гравцю <b>{victim['name']}</b>!"

        game["awaiting_choice"].pop(thief_id, None)

    try:
        await callback.message.delete()
    except:
        pass

    if not await check_and_finish(chat_id):
        game["log_action"] = action
        await update_game_message(chat_id)
        await next_turn(chat_id)

# ==========================
# МІНА
# ==========================
@router.callback_query(F.data.startswith("mine_kill_"))
async def mine_action(callback: CallbackQuery):
    await callback.answer()
    chat_id = callback.message.chat.id
    game = active_minefields.get(chat_id)
    if not game or game["phase"] != "playing":
        return

    parts = callback.data.split("_")
    actor_id = int(parts[2])
    victim_id = int(parts[3])
    if callback.from_user.id != actor_id:
        return

    async with game["lock"]:
        actor = game["players"].get(actor_id)
        victim = game["players"].get(victim_id)
        if not actor or not victim or not victim["alive"]:
            return

        victim["lives"] -= 1
        if victim["lives"] <= 0:
            victim["alive"] = False
            stolen = victim["money"]
            actor["money"] += stolen
            victim["money"] = 0
            action = f"💀 <b>{actor['name']}</b> кинув міну в <b>{victim['name']}</b> — вибув! +{stolen} грн"
        else:
            action = f"💣 <b>{actor['name']}</b> кинув міну в <b>{victim['name']}</b>! Залишилось {victim['lives']} життів"

        game["awaiting_choice"].pop(actor_id, None)

    try:
        await callback.message.delete()
    except:
        pass

    if not await check_and_finish(chat_id):
        game["log_action"] = action
        await update_game_message(chat_id)
        await next_turn(chat_id)

# ==========================
# СТОП ГРИ
# ==========================
@router.message(Command("stopmine"))
async def stop_minefield(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    chat_id = message.chat.id
    if chat_id in active_minefields:
        await finish_minefield(chat_id)
        await message.answer("🛑 Гра примусово зупинена")
    else:
        await message.answer("❌ Активної гри немає")

# ==========================
# ЗАВЕРШЕННЯ ГРИ (виплата — як у wordle)
# ==========================
async def finish_minefield(chat_id: int):
    game = active_minefields.get(chat_id)
    if not game or game["phase"] == "finished":
        return
    game["phase"] = "finished"

    if game.get("display_task"):
        game["display_task"].cancel()
    _cancel_turn_task(game)

    bot = game["message"].bot

    winners = sorted(game["players"].values(), key=lambda p: (p["alive"], p["money"]), reverse=True)
    win_reason = "💰 Перший досяг 70 грн!" if any(p["money"] >= WIN_MONEY for p in winners) else "⚔️ Останній вцілілий!"
    prize = WIN_MONEY if winners and winners[0]["money"] >= WIN_MONEY else 50

    text = f"🏆 <b>ГРА ЗАВЕРШЕНА!</b> {win_reason}\n\n<b>РЕЙТИНГ:</b>\n"
    for i, p in enumerate(winners, 1):
        medal = ("🥇", "🥈", "🥉")[i-1] if i <= 3 else "•"
        status = "✅ Живий" if p["alive"] else "💀 Вибув"
        if i == 1:
            text += f"{medal} 🏆 <b>{p['name']}</b> — ПРИЗ <b>{prize} грн</b> ({status})\n"
        else:
            text += f"{medal} {p['name']} — {EMOJI_MONEY}<b>{p['money']} грн</b> ({status})\n"

    await rate_limited_call(
        chat_id,
        lambda: game["message"].edit_text(text, reply_markup=None, parse_mode="HTML")
    )

    # === Виплата переможцю: перевірка депозиту та ліміту виграшів, як у wordle ===
    if winners and winners[0]["money"] > 0:
        winner = winners[0]
        payout_amount = await _payout_winner(chat_id, bot, winner["id"], winner["name"], prize)

        # Бан на участь у наступній грі ставимо ТІЛЬКИ якщо гроші реально нарахувались
        if payout_amount > 0:
            banned_players[winner["id"]] = time.time() + WINNER_COOLDOWN_HOURS * 3600
            await bot.send_message(
                chat_id=chat_id,
                text=f"🥇 {winner['name']} забанений на {WINNER_COOLDOWN_HOURS} годин.",
                parse_mode="HTML"
            )

    active_minefields.pop(chat_id, None)
    _last_api_call.pop(chat_id, None)
    _api_locks.pop(chat_id, None)