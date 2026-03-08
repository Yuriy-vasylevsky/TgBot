from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
import asyncio
import logging
import random
import time

from handlers.config import ADMIN_ID

router = Router(name="group_vote_prize")
router.message.filter(F.chat.type.in_({"group", "supergroup"}))

# =====================================
# НАЛАШТУВАННЯ ГРИ
# =====================================
MIN_PLAYERS = 2
MAX_PLAYERS = 10
PRIZE_AMOUNT = 100
VOTE_COOLDOWN_HOURS = 0
DISCUSSION_TIMER_SEC = 60
VOTE_TIMER_SEC = 60
MIN_VOTES_TO_WIN = 2

active_vote_games = {}
winners_cooldown = {}

PLAYER_EMOJIS = ["🐼", "🦊", "🐨", "🦄", "🐸", "🦉", "🐶", "🐱", "🐯", "🐙", "🦋", "🐬", "👻", "🤖", "🧸", "🦝"]


def assign_emoji(used: set = None) -> str:
    if used is None:
        used = set()
    available = [e for e in PLAYER_EMOJIS if e not in used] or PLAYER_EMOJIS
    emoji = random.choice(available)
    used.add(emoji)
    return emoji


def get_display_name(user) -> str:
    return f"@{user.username}" if user.username else user.full_name


def get_starters_text(game: dict, show_voted_emoji: bool = False) -> str:
    lines = []
    for data in game["participants"].values():
        emoji = data["emoji"]
        name = data["name"]
        voted_by = " " + " ".join(data.get("voted_by_emojis", [])) if show_voted_emoji and data.get("voted_by_emojis") else ""
        lines.append(f"{emoji} {name}{voted_by}")
    return "\n".join(lines) if lines else "Поки нікого немає"


def build_vote_keyboard(game: dict) -> InlineKeyboardMarkup:
    keyboard = []
    row = []
    for pid, data in game["participants"].items():
        row.append(InlineKeyboardButton(
            text=f"{data['emoji']} {data['name']}"[:28],
            callback_data=f"vote_{pid}"
        ))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


async def update_message(msg, text: str, reply_markup=None):
    """Безпечно оновлює повідомлення з обробкою помилок"""
    if msg is None:
        return False
    try:
        await msg.edit_text(text, reply_markup=reply_markup, parse_mode="HTML")
        return True
    except Exception as e:
        logging.error(f"Помилка оновлення повідомлення: {e}")
        return False


# =====================================
# ЗАПУСК ГРИ
# =====================================
async def create_vote_game(message: Message):
    chat_id = message.chat.id
    
    # Очищаємо закінчені гри
    if chat_id in active_vote_games and not active_vote_games[chat_id]["active"]:
        del active_vote_games[chat_id]
    
    if chat_id in active_vote_games:
        await message.answer("❌ У цьому чаті вже запущена гра!")
        return

    buttons = [
        [InlineKeyboardButton(text=f"🚀 Беру участь (0/{MIN_PLAYERS})", callback_data="vote_join")],
        [InlineKeyboardButton(text="🔥 Запустити гру", callback_data="vote_start_force")]
    ]

    kb = InlineKeyboardMarkup(inline_keyboard=buttons)

    text = (
        f"<b>🎁 Голосування за приз 🎁</b>\n\n"
        f"Приз: <b>{PRIZE_AMOUNT} грн</b>\n\n"
        f"Рекомендується мінімум {MIN_PLAYERS} гравців\n\n"
        f"Учасників: 0"
    )

    msg = await message.answer(text, reply_markup=kb, parse_mode="HTML")

    active_vote_games[chat_id] = {
        "main_message": msg,
        "voting_message": None,
        "participants": {},
        "votes": {},
        "active": False,
        "round": 1,
        "finalizing": False,
        "voting_task": None
    }


@router.message(Command("vote_prize"))
async def cmd_vote_prize(message: Message):
    if message.from_user.id != ADMIN_ID:
        try:
            await message.delete()
        except:
            pass
        return
    await create_vote_game(message)


# =====================================
# ПРИЄДНАННЯ
# =====================================
@router.callback_query(F.data == "vote_join")
async def vote_join(callback: CallbackQuery):
    chat_id = callback.message.chat.id
    user_id = callback.from_user.id

    if chat_id not in active_vote_games:
        await callback.answer("Гра вже неактивна", show_alert=True)
        return

    game = active_vote_games[chat_id]

    if game["active"]:
        await callback.answer("Гра вже почалася!", show_alert=True)
        return

    if user_id in winners_cooldown:
        rem = winners_cooldown[user_id] - time.time()
        if rem > 0:
            await callback.answer(f"⏳ Наступна гра через {int(rem//3600) + 1} годин", show_alert=True)
            return
        else:
            del winners_cooldown[user_id]

    if user_id in game["participants"]:
        await callback.answer("Ти вже приєднався!", show_alert=True)
        return

    # Ліміт гравців
    if len(game["participants"]) >= MAX_PLAYERS:
        await callback.answer(f"❌ Максимум {MAX_PLAYERS} гравців!", show_alert=True)
        return

    used = {p["emoji"] for p in game["participants"].values()}
    emoji = assign_emoji(used)

    game["participants"][user_id] = {
        "name": get_display_name(callback.from_user),
        "emoji": emoji,
        "voted_by_emojis": []
    }

    count = len(game["participants"])

    buttons = [
        [InlineKeyboardButton(text=f"🚀 Беру участь ({count}/{MIN_PLAYERS})", callback_data="vote_join")],
        [InlineKeyboardButton(text="🔥 Запустити гру", callback_data="vote_start_force")]
    ]

    kb = InlineKeyboardMarkup(inline_keyboard=buttons)

    text = (
        f"<b>🎁 Голосування за приз 🎁</b>\n\n"
        f"Приз: <b>{PRIZE_AMOUNT} грн</b>\n\n"
        f"Гравці:\n{get_starters_text(game)}\n\n"
        f"Учасників: <b>{count}</b>\n"
    )

    updated = await update_message(callback.message, text, kb)
    if updated:
        await callback.answer(f"Твій смайлик — {emoji}")
    else:
        await callback.answer("Помилка оновлення повідомлення", show_alert=True)


# =====================================
# ПРИМУСОВИЙ СТАРТ АДМІНОМ
# =====================================
@router.callback_query(F.data == "vote_start_force")
async def vote_start_force(callback: CallbackQuery):
    chat_id = callback.message.chat.id
    user_id = callback.from_user.id

    if user_id != ADMIN_ID:
        await callback.answer("Тільки адмін може запустити гру", show_alert=True)
        return

    if chat_id not in active_vote_games:
        await callback.answer("Гра вже неактивна", show_alert=True)
        return

    game = active_vote_games[chat_id]

    if game["active"]:
        await callback.answer("Гра вже запущена", show_alert=True)
        return

    if len(game["participants"]) < MIN_PLAYERS:
        await callback.answer(f"❌ Потрібно мінімум {MIN_PLAYERS} гравців!", show_alert=True)
        return

    await callback.answer("✅ Гра запущена!")
    game["active"] = True
    game["round"] = 1
    asyncio.create_task(run_game_loop(chat_id))


async def run_game_loop(chat_id: int):
    """Основний цикл гри"""
    if chat_id not in active_vote_games:
        return
    
    game = active_vote_games[chat_id]
    
    # Раунд 1
    logging.info(f"Раунд 1 розпочато для чату {chat_id}")
    await run_round(chat_id, 1)
    
    # Перевіряємо чи гра ще активна (переможець у раунді 1)
    if chat_id not in active_vote_games or not active_vote_games[chat_id]["active"]:
        logging.info(f"Гра {chat_id} закінчена після раунду 1")
        return
    
    # Раунд 2
    logging.info(f"Раунд 2 розпочато для чату {chat_id}")
    await run_round(chat_id, 2)
    
    # Після раунду 2 гра завершується
    if chat_id in active_vote_games:
        game = active_vote_games[chat_id]
        game["active"] = False
        logging.info(f"Гра {chat_id} закінчена")


async def run_round(chat_id: int, round_num: int):
    """Один раунд: обговорення -> голосування -> результати"""
    if chat_id not in active_vote_games:
        return
    
    game = active_vote_games[chat_id]
    game["round"] = round_num
    game["votes"] = {}
    game["finalizing"] = False
    
    # Очищаємо старі голоси
    for p in game["participants"].values():
        p["voted_by_emojis"] = []
    
    # === ОБГОВОРЕННЯ ===
    logging.info(f"Обговорення раунду {round_num} для чату {chat_id}")
    text = (f"<b>🎁 Обговорення! Раунд {round_num} 🎁</b>\n\n"
            f"Приз: <b>{PRIZE_AMOUNT} грн</b>\n\n"
            f"Час на обговорення: ~{DISCUSSION_TIMER_SEC} сек")
    
    await update_message(game["main_message"], text)
    await asyncio.sleep(DISCUSSION_TIMER_SEC)
    
    if chat_id not in active_vote_games or not game["active"]:
        return
    
    # === ГОЛОСУВАННЯ ===
    logging.info(f"Голосування раунду {round_num} для чату {chat_id}")
    
    # Видаляємо старе повідомлення голосування
    if game.get("voting_message"):
        try:
            await game["voting_message"].delete()
        except:
            pass
    
    vote_kb = build_vote_keyboard(game)
    
    try:
        voting_msg = await game["main_message"].answer(
            f"<b>🎁 ЧАС ГОЛОСУВАТИ! Раунд {round_num} 🎁</b>\n\n"
            f"Приз: <b>{PRIZE_AMOUNT} грн</b>\n\n"
            f"{get_starters_text(game)}\n\n"
            f"Голосуйте (до {VOTE_TIMER_SEC} сек або поки всі не проголосують)",
            reply_markup=vote_kb,
            parse_mode="HTML"
        )
        game["voting_message"] = voting_msg
    except Exception as e:
        logging.error(f"Помилка створення повідомлення голосування: {e}")
        return
    
    game["vote_end_time"] = time.time() + VOTE_TIMER_SEC
    
    # Запускаємо таймер голосування
    if game.get("voting_task"):
        game["voting_task"].cancel()
    game["voting_task"] = asyncio.create_task(voting_timer(chat_id, round_num))
    
    # Чекаємо завершення голосування
    while chat_id in active_vote_games:
        if game.get("finalizing") or time.time() > game.get("vote_end_time", 0):
            break
        await asyncio.sleep(0.5)
    
    # === РЕЗУЛЬТАТИ ===
    logging.info(f"Підрахунок голосів для раунду {round_num}, чат {chat_id}")
    
    if chat_id not in active_vote_games:
        return
    
    votes_count = {}
    for v in game["votes"].values():
        if v is not None:
            votes_count[v] = votes_count.get(v, 0) + 1
    
    max_votes = max(votes_count.values()) if votes_count else 0
    winners = [uid for uid, cnt in votes_count.items() if cnt == max_votes] if votes_count else []
    
    results_text = f"<b>🎁 РЕЗУЛЬТАТИ РАУНДУ {round_num} 🎁</b>\n\n"
    results_text += f"{get_starters_text(game, show_voted_emoji=True)}\n\n"
    
    # Перемога
    if max_votes >= MIN_VOTES_TO_WIN and len(winners) == 1:
        winner_id = winners[0]
        winner = game["participants"][winner_id]
        
        results_text += f"🎉 <b>ПЕРЕМОЖЕЦЬ!</b>\n"
        results_text += f"{winner['emoji']} {winner['name']} — {max_votes} голосів!\n\n"
        results_text += f"Вітаємо! Приз твій! 🏆"
        
        logging.info(f"Переможець раунду {round_num}: {winner['name']}")
        
        await update_message(game["voting_message"], results_text)
        
        if VOTE_COOLDOWN_HOURS > 0:
            winners_cooldown[winner_id] = time.time() + VOTE_COOLDOWN_HOURS * 3600
        
        game["active"] = False
        return
    
    # Нічия
    results_text += f"🤝 <b>НІЧИЯ!</b>\n\n"
    
    if round_num >= 2:
        # Закінчення гри після нічиї в раунді 2
        results_text += f"😔 <b>НАЖАЛЬ ВИ НЕ ДОМОВИЛИСЬ!</b>\n\n"
        results_text += f"Гра закінчена. Переможця не визначено."
        logging.info(f"Гра закінчена - друга нічия в чаті {chat_id}")
    else:
        # Перехід на раунд 2
        results_text += f"Розпочинаємо Раунд 2...\n\n"
        logging.info(f"Нічия в раунді 1, переходимо на раунд 2 для чату {chat_id}")
    
    await update_message(game["voting_message"], results_text)


async def voting_timer(chat_id: int, round_num: int):
    """Таймер голосування"""
    try:
        await asyncio.sleep(VOTE_TIMER_SEC)
        
        if chat_id in active_vote_games:
            game = active_vote_games[chat_id]
            if not game.get("finalizing") and game.get("round") == round_num:
                game["finalizing"] = True
                logging.info(f"Таймер голосування закінчився для раунду {round_num}")
    except asyncio.CancelledError:
        pass


# =====================================
# ОБРОБКА ГОЛОСУ
# =====================================
@router.callback_query(F.data.startswith("vote_"))
async def process_vote(callback: CallbackQuery):
    chat_id = callback.message.chat.id
    user_id = callback.from_user.id
    
    if chat_id not in active_vote_games:
        await callback.answer("Гра вже неактивна", show_alert=True)
        return

    game = active_vote_games[chat_id]

    if not game.get("voting_message") or game.get("finalizing"):
        await callback.answer("Голосування неактивне", show_alert=True)
        return

    if time.time() > game.get("vote_end_time", 0):
        await callback.answer("Час голосування закінчився!", show_alert=True)
        return

    if user_id not in game["participants"]:
        await callback.answer("Ти не в грі!", show_alert=True)
        return

    if user_id in game["votes"]:
        await callback.answer("Ти вже проголосував!", show_alert=True)
        return

    try:
        voted_id = int(callback.data.split("_")[1])
    except (ValueError, IndexError):
        await callback.answer("Помилка голосування", show_alert=True)
        return

    if voted_id not in game["participants"]:
        await callback.answer("Цей гравець більше не в грі", show_alert=True)
        return

    if voted_id == user_id:
        await callback.answer("❌ Не можна голосувати за себе!", show_alert=True)
        return

    game["votes"][user_id] = voted_id
    voter_emoji = game["participants"][user_id]["emoji"]
    game["participants"][voted_id]["voted_by_emojis"].append(voter_emoji)
    await callback.answer("✅ Голос зараховано!")

    # Оновлюємо повідомлення з голосами
    game["vote_kb"] = build_vote_keyboard(game)
    await update_message(
        game["voting_message"],
        f"<b>🎁 ЧАС ГОЛОСУВАТИ! 🎁\n"
        f"<b>Раунд {game['round']} </b>\n\n"
        f"Приз: <b>{PRIZE_AMOUNT} грн</b>\n\n"
        f"{get_starters_text(game, show_voted_emoji=True)}\n\n"
        f"Голосуйте (до {VOTE_TIMER_SEC} сек або поки всі не проголосують)",
        game["vote_kb"]
    )

    # Якщо всі проголосували — відразу фіналізуємо
    if len(game["votes"]) == len(game["participants"]):
        game["finalizing"] = True
        logging.info(f"Всі проголосували на раунді {game['round']}, фіналізуємо")


# =====================================
# КІНЕЦЬ ФАЙЛУ
# =====================================