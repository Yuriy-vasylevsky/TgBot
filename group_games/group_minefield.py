import logging
import random
import time
import asyncio
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.exceptions import TelegramRetryAfter, TelegramBadRequest, TelegramForbiddenError
from handlers.config import ADMIN_ID

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

WIN_MONEY = 70          # Перший хто набрав — переможець

HEART_CELLS_COUNT = 3
MINES_COUNT = 14
STEAL_COUNT = 9

START_LIVES = 2
MAX_PLAYERS = 3

COOLDOWN_SECONDS = 5
TURN_TIMEOUT = 10        # секунд на хід, потім хід передається далі

# Телеграм дозволяє ~1 edit/сек на одне повідомлення і ~30 msg/сек на чат
API_CALL_INTERVAL = 1.2   # мін. пауза між API-запитами для одного чату
DISPLAY_DEBOUNCE  = 1.5   # debounce для edit основного поля

WINNER_COOLDOWN_HOURS = 12
# ==========================

EMOJI_MONEY   = "💰"
EMOJI_DIAMOND = "💎"
EMOJI_HEART   = "❤️"
EMOJI_MINE    = "💣"
EMOJI_STEAL   = "🕵️"
EMOJI_DEAD    = "💀"
EMOJI_PLAYERS = "👥 Учасники:"

active_minefields: dict = {}
banned_players: dict = {}

# ==========================
# RATE-LIMITER (per chat_id)
# ==========================
_last_api_call: dict[int, float] = {}
_api_locks: dict[int, asyncio.Lock] = {}


def _get_api_lock(chat_id: int) -> asyncio.Lock:
    if chat_id not in _api_locks:
        _api_locks[chat_id] = asyncio.Lock()
    return _api_locks[chat_id]


async def rate_limited_call(chat_id: int, factory):
    """
    Виконує API-запит з паузою API_CALL_INTERVAL між запитами до одного чату.
    factory — callable без аргументів що повертає нову корутину (lambda або functools.partial).
    Це дозволяє безпечно робити retry після TelegramRetryAfter.

    Приклад: rate_limited_call(chat_id, lambda: msg.edit_text("hi"))
    """
    async with _get_api_lock(chat_id):
        since = time.monotonic() - _last_api_call.get(chat_id, 0)
        if since < API_CALL_INTERVAL:
            await asyncio.sleep(API_CALL_INTERVAL - since)

        for attempt in range(2):
            try:
                result = await factory()
                _last_api_call[chat_id] = time.monotonic()
                return result
            except TelegramRetryAfter as e:
                if attempt == 0:
                    wait = e.retry_after + 1.0
                    logging.warning(f"[{chat_id}] Flood control — чекаємо {wait:.1f}с")
                    await asyncio.sleep(wait)
                    _last_api_call[chat_id] = time.monotonic()
                else:
                    logging.error(f"[{chat_id}] Повторний flood — пропускаємо")
                    return
            except TelegramForbiddenError as e:
                logging.error(f"[{chat_id}] Forbidden: {e}")
                active_minefields.pop(chat_id, None)
                return
            except TelegramBadRequest as e:
                if "message is not modified" not in str(e).lower():
                    logging.warning(f"[{chat_id}] BadRequest: {e}")
                return
            except Exception as e:
                logging.error(f"[{chat_id}] rate_limited_call: {e}")
                return


# ==========================
# ДОПОМІЖНІ ФУНКЦІЇ
# ==========================
def get_display_name(user) -> str:
    return f"@{user.username}" if user.username else user.full_name


def generate_field():
    board = [["EMPTY"] * FIELD_SIZE for _ in range(FIELD_SIZE)]
    positions = [(i, j) for i in range(FIELD_SIZE) for j in range(FIELD_SIZE)]
    random.shuffle(positions)
    for kind, count in [("MONEY", MONEY_CELLS_COUNT), ("DIAMOND", DIAMOND_CELLS_COUNT),
                        ("HEART", HEART_CELLS_COUNT),
                        ("MINE", MINES_COUNT), ("STEAL", STEAL_COUNT)]:
        for _ in range(count):
            if not positions:
                logging.warning(f"generate_field: закінчились позиції при розміщенні {kind}")
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
    """Тільки стати гравців. Без стрілки і лічильника — менше зайвих edit."""
    lines = ["<b>💣 МІННЕ ПОЛЕ 💣</b>\n", EMOJI_PLAYERS]
    for p in game["players"].values():
        status = f"{EMOJI_MONEY}{p['money']}/{WIN_MONEY}  {EMOJI_HEART}{p['lives']}" if p["alive"] else EMOJI_DEAD
        lines.append(f"• {p['name']} {status}")
    return "\n".join(lines)


def build_log_text(game) -> str:
    """Лог-повідомлення: остання дія гравця + хто ходить зараз."""
    parts = []
    action = game.get("log_action", "")
    if action:
        parts.append(f"📋 <b>Остання дія:</b>\n{action}")
    cur = game.get("current_player")
    if cur and cur in game["players"]:
        parts.append(f"\n➡️ Зараз ходить: <b>{game['players'][cur]['name']}</b>")
    return "\n".join(parts) or "⏳ Гра починається..."


def get_lives_text(lives: int) -> str:
    return "життя" if lives % 10 == 1 and lives % 100 != 11 else "життів"


# ==========================
# ОНОВЛЕННЯ ДИСПЛЕЮ (debounce) + ЛОГ
# ==========================
async def update_display(chat_id: int):
    """
    Планує редагування основного поля з debounce.
    Дублюючі виклики скасовуються — виконується лише останній.
    """
    game = active_minefields.get(chat_id)
    if not game:
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
            logging.warning(f"update_display task: {e}")

    game["display_task"] = asyncio.create_task(_do())


async def update_log(chat_id: int, action: str):
    """
    Редагує фіксоване лог-повідомлення під полем.
    Ніколи не надсилає нове — тільки edit. Безпечно для rate limits.
    """
    game = active_minefields.get(chat_id)
    if not game or not action:
        return

    log_msg = game.get("log_message")
    if not log_msg:
        return

    game["log_action"] = action
    await rate_limited_call(
        chat_id,
        lambda: log_msg.edit_text(build_log_text(game), parse_mode="HTML")
    )


# ==========================
# ЛОГІКА ХОДІВ
# ==========================
def _cancel_turn_task(game: dict):
    """Скасовує попередній таймер ходу, якщо є."""
    task = game.get("turn_task")
    if task and not task.done():
        task.cancel()
    game["turn_task"] = None


def schedule_turn_timeout(chat_id: int):
    """Запускає таймер: якщо гравець не ходить TURN_TIMEOUT секунд — хід передається."""
    game = active_minefields.get(chat_id)
    if not game:
        return
    _cancel_turn_task(game)

    async def _timeout():
        try:
            await asyncio.sleep(TURN_TIMEOUT)
            g = active_minefields.get(chat_id)
            if not g or g["phase"] != "playing":
                return
            # Якщо гравець очікує вибору (міна/крадіжка) — не пропускаємо
            cur = g.get("current_player")
            if cur and g["awaiting_choice"].get(cur):
                return
            skipped_name = g["players"].get(cur, {}).get("name", "?")
            g["log_action"] = f"⏩ <b>{skipped_name}</b> не встиг — хід пропущено!"
            await next_turn(chat_id)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logging.warning(f"turn_timeout: {e}")

    game["turn_task"] = asyncio.create_task(_timeout())


async def next_turn(chat_id: int):
    game = active_minefields.get(chat_id)
    if not game or game["phase"] != "playing":
        return

    alive = [uid for uid, p in game["players"].items() if p["alive"]]
    if not alive:
        await finish_minefield(chat_id)
        return

    game["queue"] = [uid for uid in game["queue"] if uid in alive]
    if not game["queue"]:
        await finish_minefield(chat_id)
        return

    game["current_turn"] = (game.get("current_turn", 0) + 1) % len(game["queue"])
    game["current_player"] = game["queue"][game["current_turn"]]
    # Редагуємо лише лог (current_player змінився) — поле не чіпаємо
    g = active_minefields.get(chat_id)
    if g and g.get("log_message"):
        await rate_limited_call(
            chat_id,
            lambda: g["log_message"].edit_text(build_log_text(g), parse_mode="HTML")
        )
    schedule_turn_timeout(chat_id)


async def check_and_finish(chat_id: int) -> bool:
    game = active_minefields.get(chat_id)
    if not game or game["phase"] != "playing":
        return True
    alive = [p for p in game["players"].values() if p["alive"]]
    winner_by_money = any(p["money"] >= WIN_MONEY for p in game["players"].values())
    if len(alive) <= 1 or winner_by_money:
        await finish_minefield(chat_id)
        return True
    return False


# ==========================
# СТАРТ ГРИ
# ==========================
@router.message(Command("minefield"))
async def start_minefield(message: Message):
    try:
        if message.from_user.id != ADMIN_ID:
            try:
                await message.delete()
            except Exception:
                pass
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
            f"💰 Клітинка = <b>{MONEY_PER_CELL} грн</b>  💎 Алмаз = <b>{DIAMOND_PER_CELL} грн</b>\n"
            f"🏆 Перший хто набрав <b>{WIN_MONEY} грн</b> — переможець!\n"
            # f"{EMOJI_HEART} Знаходь життя\n"
            # f"{EMOJI_STEAL} Кради гроші\n"
            # f"{EMOJI_MINE} Міни — вибір кого вибути\n\n"
            f"👥 Максимум <b>{MAX_PLAYERS} гравці</b>\nПриєднуйтесь!",
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
            "log_message": None,
            "log_action": "",
            "turn_task": None,
        }
    except Exception as e:
        logging.error(f"start_minefield: {e}")


# ==========================
# ПРИЄДНАННЯ
# ==========================
@router.callback_query(F.data == "join_minefield")
async def join_minefield(callback: CallbackQuery):
    try:
        await callback.answer()
        chat_id = callback.message.chat.id
        user = callback.from_user
        game = active_minefields.get(chat_id)

        if not game or game["phase"] != "joining":
            return
        if user.id in game["players"]:
            await callback.answer("Ти вже в грі!", show_alert=True)
            return

        now = time.time()
        if user.id in banned_players and now < banned_players[user.id]:
            left = int((banned_players[user.id] - now) / 3600) + 1
            await callback.answer(f"❌ Переможець! Зачекай {left} год.", show_alert=True)
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
    except Exception as e:
        logging.error(f"join_minefield: {e}")


# ==========================
# СТАРТ ПАРТІЇ
# ==========================
@router.callback_query(F.data == "start_minefield")
async def start_game(callback: CallbackQuery):
    try:
        await callback.answer()
        chat_id = callback.message.chat.id
        game = active_minefields.get(chat_id)

        if not game or game["phase"] != "joining" or callback.from_user.id != game["admin_id"]:
            return
        member = await callback.message.bot.get_chat_member(chat_id, callback.from_user.id)
        if member.status not in ("administrator", "creator"):
            await callback.answer("Тільки адмін може стартувати!", show_alert=True)
            return
        if len(game["players"]) < 2:
            await callback.answer("Мінімум 2 гравці!", show_alert=True)
            return

        queue = list(game["players"].keys())
        if not queue:
            await callback.answer("❌ Немає гравців!", show_alert=True)
            return
        random.shuffle(queue)
        game["queue"] = queue
        game["current_turn"] = 0
        game["current_player"] = queue[0]
        game["board"] = generate_field()
        game["revealed"] = [[False] * FIELD_SIZE for _ in range(FIELD_SIZE)]
        game["phase"] = "playing"

        first = game["players"][game["current_player"]]["name"]
        await rate_limited_call(chat_id, lambda: callback.message.edit_text(
            build_main_text(game),
            reply_markup=build_field_keyboard(game), parse_mode="HTML"
        ))
        # Надсилаємо лог-повідомлення одразу під полем
        log_msg = await rate_limited_call(chat_id, lambda: callback.message.bot.send_message(
            chat_id,
            f"➡️ Зараз ходить: <b>{first}</b>",
            parse_mode="HTML"
        ))
        game["log_message"] = log_msg
        schedule_turn_timeout(chat_id)
    except Exception as e:
        logging.error(f"start_game: {e}")


# ==========================
# КЛІК ПО ПОЛЮ
# ==========================
@router.callback_query(F.data.startswith("field_"))
async def field_click(callback: CallbackQuery):
    try:
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
        _cancel_turn_task(game)  # гравець ходить — скасовуємо таймер

        # --- тільки зміна стану ---
        async with game["lock"]:
            try:
                _, r, c = callback.data.split("_")
                row, col = int(r), int(c)
            except Exception:
                await callback.answer("Помилка!", show_alert=True)
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
                has_victims = any(
                    p["alive"] and p["money"] > 0 and uid != user_id
                    for uid, p in game["players"].items()
                )
                if has_victims:
                    game["awaiting_choice"][user_id] = True
                else:
                    action = f"🕵️ <b>{player['name']}</b> крадіжка, але красти нічого!"
                    auto_next = True

            elif cell == "MINE":
                alive_others = [uid for uid, p in game["players"].items()
                                if p["alive"] and uid != user_id]
                if random.random() < 0.4:
                    # 40% — вибухає на самому гравці
                    player["lives"] -= 1
                    if player["lives"] <= 0:
                        player["alive"] = False
                        player["money"] = 0   # сам зірвався — гроші згоріли
                        action = f"💥 Міна вибухнула! <b>{player['name']}</b> вибув і втратив всі гроші!"
                    else:
                        action = f"💥 Міна вибухнула на <b>{player['name']}</b>! {player['lives']} {get_lives_text(player['lives'])}"
                    auto_next = True
                elif alive_others:
                    # 60% — кидає міну в іншого, треба вибрати
                    game["awaiting_choice"][user_id] = True
                else:
                    # 60% але немає інших — міна дуда
                    action = f"💨 <b>{player['name']}</b> наступив на міну, але вона не спрацювала!"
                    auto_next = True

        # --- side-effects поза локом ---

        if cell == "STEAL" and game["awaiting_choice"].get(user_id):
            buttons = [[InlineKeyboardButton(text="🚫 Не красти",
                                             callback_data=f"steal_cancel_{user_id}")]]
            for uid, p in game["players"].items():
                if p["alive"] and p["money"] > 0 and uid != user_id:
                    buttons.append([InlineKeyboardButton(
                        text=f"{EMOJI_STEAL} Вкрасти у {p['name']}",
                        callback_data=f"steal_{user_id}_{uid}"
                    )])
            await update_log(chat_id, f"🕵️ <b>{player['name']}</b> активував крадіжку!")
            await rate_limited_call(chat_id, lambda: callback.message.bot.send_message(
                chat_id,
                f"🕵️ <b>{player['name']}</b>, обери у кого вкрасти:",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
                parse_mode="HTML"
            ))
            return

        if cell == "MINE" and game["awaiting_choice"].get(user_id):
            buttons = []
            for uid, p in game["players"].items():
                if p["alive"] and uid != user_id:
                    buttons.append([InlineKeyboardButton(
                        text=f"{EMOJI_DEAD} Кинути міну в {p['name']}",
                        callback_data=f"mine_kill_{user_id}_{uid}"
                    )])
            await update_log(chat_id, f"💣 <b>{player['name']}</b> перекидає міну! Вибирає жертву...")
            await rate_limited_call(chat_id, lambda: callback.message.bot.send_message(
                chat_id,
                f"💣 <b>{player['name']}</b> Обери кому кинути міну:",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
                parse_mode="HTML"
            ))
            return

        finished = await check_and_finish(chat_id)
        if not finished and auto_next:
            # Зберігаємо дію — next_turn покаже її разом з новим поточним гравцем (1 edit)
            if action:
                game["log_action"] = action
            await update_display(chat_id)  # оновлюємо стати (гроші/життя змінились)
            await next_turn(chat_id)       # оновлює лог: стара дія + новий гравець
        elif action:
            await update_log(chat_id, action)
            await update_display(chat_id)

    except Exception as e:
        logging.error(f"field_click: {e}")


# ==========================
# КРАДІЖКА
# ==========================
@router.callback_query(F.data.startswith("steal_"))
async def steal_money(callback: CallbackQuery):
    try:
        await callback.answer()
        chat_id = callback.message.chat.id
        game = active_minefields.get(chat_id)

        if not game or game["phase"] != "playing":
            await callback.answer("❌ Гра закінчилась!", show_alert=True)
            return

        parts = callback.data.split("_")
        if len(parts) != 3:
            return

        if parts[1] == "cancel":
            thief_id = int(parts[2])
            if callback.from_user.id != thief_id:
                await callback.answer("❌ Не твоя кнопка!", show_alert=True)
                return
            game["awaiting_choice"].pop(thief_id, None)
            try:
                await callback.message.delete()
            except Exception:
                pass
            finished = await check_and_finish(chat_id)
            if not finished:
                game["log_action"] = f"🕵️ <b>{game['players'][thief_id]['name']}</b> вирішив не красти"
                await next_turn(chat_id)
            return

        thief_id = int(parts[1])
        victim_id = int(parts[2])

        if callback.from_user.id != thief_id:
            await callback.answer("❌ Не твоя кнопка!", show_alert=True)
            return

        async with game["lock"]:
            if thief_id not in game["players"] or victim_id not in game["players"]:
                await callback.answer("❌ Гравець вже вибув!", show_alert=True)
                return
            thief = game["players"][thief_id]
            victim = game["players"][victim_id]
            if not thief["alive"] or not victim["alive"]:
                await callback.answer("❌ Гравець вже вибув!", show_alert=True)
                return
            if victim["money"] <= 0:
                await callback.answer("❌ У жертви немає грошей!", show_alert=True)
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
        except Exception:
            pass

        finished = await check_and_finish(chat_id)
        if not finished:
            game["log_action"] = action
            await update_display(chat_id)
            await next_turn(chat_id)

    except Exception as e:
        logging.error(f"steal_money: {e}")


# ==========================
# МІНА
# ==========================
@router.callback_query(F.data.startswith("mine_"))
async def mine_action(callback: CallbackQuery):
    try:
        await callback.answer()
        chat_id = callback.message.chat.id
        game = active_minefields.get(chat_id)

        if not game or game["phase"] != "playing":
            await callback.answer("❌ Гра закінчилась!", show_alert=True)
            return

        parts = callback.data.split("_")
        if parts[1] == "kill" and len(parts) == 4:
            actor_id, victim_id = int(parts[2]), int(parts[3])
        else:
            return

        if callback.from_user.id != actor_id:
            await callback.answer("❌ Не твоя кнопка!", show_alert=True)
            return

        async with game["lock"]:
            if actor_id not in game["players"]:
                return
            actor = game["players"][actor_id]
            if not actor["alive"]:
                return

            if victim_id not in game["players"]:
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
                action = f"💀 <b>{actor['name']}</b> кинув міну в <b>{victim['name']}</b> — вибув! +{stolen} грн"
            else:
                action = (f"💣 <b>{actor['name']}</b> кинув міну в <b>{victim['name']}</b>! "
                          f"Залишилось {victim['lives']} {get_lives_text(victim['lives'])}")

            game["awaiting_choice"].pop(actor_id, None)

        try:
            await callback.message.delete()
        except Exception:
            pass

        finished = await check_and_finish(chat_id)
        if not finished:
            game["log_action"] = action
            await update_display(chat_id)
            await next_turn(chat_id)

    except Exception as e:
        logging.error(f"mine_action: {e}")


# ==========================
# ЗАВЕРШЕННЯ ГРИ
# ==========================
async def finish_minefield(chat_id: int):
    try:
        game = active_minefields.get(chat_id)
        if not game or game["phase"] == "finished":
            return

        game["phase"] = "finished"

        task = game.get("display_task")
        if task and not task.done():
            task.cancel()
        _cancel_turn_task(game)

        winners = sorted(game["players"].values(), key=lambda p: (p["alive"], p["money"]), reverse=True)

        # Визначаємо тип перемоги
        money_winner = next((p for p in winners if p["money"] >= WIN_MONEY), None)
        alive_players = [p for p in game["players"].values() if p["alive"]]

        if money_winner:
            win_reason = f"💰 Перший досяг <b>{WIN_MONEY} грн</b>!"
        elif len(alive_players) == 1:
            win_reason = "⚔️ Останній вцілілий!"
        else:
            win_reason = "🏁 Гра завершена"

        # Приз 1-го місця: набрав >= WIN_MONEY → приз WIN_MONEY, інакше → мінімум 50 грн
        first = winners[0] if winners else None
        prize = WIN_MONEY if (first and first["money"] >= WIN_MONEY) else 50

        text = f"🏆 <b>ГРА ЗАВЕРШЕНА!</b>  {win_reason}\n\n<b>РЕЙТИНГ:</b>\n"
        for i, p in enumerate(winners, 1):
            medal = ("🥇", "🥈", "🥉")[i - 1] if i <= 3 else "•"
            status = "✅ Живий" if p["alive"] else "💀 Вибув"
            if i == 1:
                # text += f"{medal} {p['name']} — {EMOJI_MONEY}<b>{p['money']} грн</b> → приз <b>{prize} грн</b> ({status})\n"
                text += f"{medal} {p['name']} — {EMOJI_MONEY} Приз <b>{prize} грн</b> ({status})\n"
            else:
                text += f"{medal} {p['name']} — {EMOJI_MONEY}<b>{p['money']} грн</b> ({status})\n"

        if first and first["money"] > 0:
            banned_players[first["id"]] = time.time() + WINNER_COOLDOWN_HOURS * 3600
            text += f"\n🥇 <b>{first['name']}</b> не може грати {WINNER_COOLDOWN_HOURS} год."

        await rate_limited_call(chat_id, lambda: game["message"].edit_text(
            text, reply_markup=None, parse_mode="HTML"
        ))

        active_minefields.pop(chat_id, None)
        _last_api_call.pop(chat_id, None)
        _api_locks.pop(chat_id, None)

    except Exception as e:
        logging.error(f"finish_minefield: {e}")