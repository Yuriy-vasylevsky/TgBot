from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
import asyncio
import logging
import random
import time

from handlers.config import ADMIN_ID
from db import add_money_win, add_daily_game_win
from db.wallet import (
    add_to_balance,
    get_daily_net,
    get_yesterday_net,
    get_daily_game_win,
    get_yesterday_game_win,
)

router = Router(name="group_skarb")
router.message.filter(F.chat.type.in_({"group", "supergroup"}))

GRID_SIZE = 7
REQUIRED_PLAYERS = 4
PRIZE_AMOUNT = 50
CLICK_COOLDOWN_SEC = 6        # мінімум між кліками одного гравця
GLOBAL_CLICK_COOLDOWN_SEC = 1 # мінімум між будь-якими кліками (анти-флуд)
WIN_COOLDOWN_HOURS = 0
AUTO_DELETE_AFTER_WIN_SEC = 6000

CLOSED_CELL = "🃏"
WIN_CARD = "A♥️"
BOMB_CELL = "💣"

NUM_ARROWS = 7
NUM_BOMBS = 5

LIFE_EMOJI = "❤️"
INITIAL_LIVES = 1

active_skarb = {}
winners_cooldown = {}

# Глобальний анти-флуд: час останнього кліку по конкретній грі (будь-яким гравцем)
_global_last_click: dict[int, float] = {}


# =====================================
# ДОПОМІЖНІ
# =====================================

def _positive_or_zero(value: int) -> int:
    return value if value > 0 else 0


def is_on_cooldown(user_id: int) -> tuple[bool, int]:
    if user_id in winners_cooldown:
        remaining = winners_cooldown[user_id] - time.time()
        if remaining > 0:
            return True, int(remaining)
        del winners_cooldown[user_id]
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


def get_display_name(user) -> str:
    return f"@{user.username}" if user.username else user.full_name


def get_starters_text(game) -> str:
    lines = ["👥 Учасники:"]
    for uid, data in game["participants"].items():
        name = data["name"]
        lives = data["lives"]
        lives_str = LIFE_EMOJI * lives if lives > 0 else " 💣"
        lines.append(f"• {name}{lives_str}")
    return "\n".join(lines) if game["participants"] else "Поки нікого немає"


def get_arrow(prize_r: int, prize_c: int, click_r: int, click_c: int) -> str:
    dr = prize_r - click_r
    dc = prize_c - click_c

    if dr == 0 and dc == 0:
        return WIN_CARD

    if dc == 0: return "⬇️" if dr > 0 else "⬆️"
    if dr == 0: return "➡️" if dc > 0 else "⬅️"

    ratio = abs(dc) / abs(dr) if dr != 0 else 999

    if ratio > 2.5: return "➡️" if dc > 0 else "⬅️"
    if ratio < 0.4: return "⬇️" if dr > 0 else "⬆️"

    if dc > 0 and dr > 0: return "↘️"
    if dc > 0 and dr < 0: return "↗️"
    if dc < 0 and dr > 0: return "↙️"
    if dc < 0 and dr < 0: return "↖️"

    return "❓"


def is_ace(card: str) -> bool:
    return card.startswith("A")


def generate_deck() -> list[str]:
    suits = ["♠️", "♥️", "♦️", "♣️"]
    ranks = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]
    deck = [rank + suit for suit in suits for rank in ranks]
    random.shuffle(deck)
    return deck


def build_grid_keyboard(game: dict, disabled: bool = False) -> InlineKeyboardMarkup:
    keyboard = []
    for r in range(GRID_SIZE):
        row = []
        for c in range(GRID_SIZE):
            pos = (r, c)
            text = game["opened"].get(pos, CLOSED_CELL)
            if disabled:
                row.append(InlineKeyboardButton(text=text, callback_data="skarb_noop"))
            else:
                row.append(InlineKeyboardButton(text=text, callback_data=f"skarb_{r}_{c}"))
        keyboard.append(row)
    # Кнопка перезапуску для адміна (завжди видима під полем під час гри)
    keyboard.append([
        InlineKeyboardButton(text="🔄 Перезапустити гру (адмін)", callback_data="skarb_reset")
    ])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def build_lobby_keyboard(count: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"🚀 УЧАСТЬ ({count}/{REQUIRED_PLAYERS})",
            callback_data="skarb_join"
        )],
        [InlineKeyboardButton(
            text="🔥 Запустити гру",
            callback_data="skarb_force_start"
        )],
        [InlineKeyboardButton(
            text="🔄 Перезапустити гру (адмін)",
            callback_data="skarb_reset"
        )],
    ])


def build_game_text(game: dict) -> str:
    count = len(game["participants"])
    active_count = count - len(game["eliminated"])
    return (
        f"<b>🃏 ТУЗ ЧІРВА ЗАХОВАНО НА ПОЛІ {GRID_SIZE}×{GRID_SIZE}! 🃏</b>\n\n"
        f"Приз — <b>{PRIZE_AMOUNT} грн</b>\n\n"
        f"{get_starters_text(game)}\n\n"
        f"Гравців в грі: <b>{active_count}</b>\n"
        f"Клікай на {CLOSED_CELL} (кожні {CLICK_COOLDOWN_SEC} сек)\n"
        f"52 карти + {NUM_ARROWS} стрілок + {NUM_BOMBS} бомб 💣\n"
        f"Туз дає +1 життя ❤️\n"
        f"Останній живий — переможець 🏆"
    )


async def cleanup_after_win(chat_id: int):
    if AUTO_DELETE_AFTER_WIN_SEC <= 0:
        return
    await asyncio.sleep(AUTO_DELETE_AFTER_WIN_SEC)
    if chat_id in active_skarb:
        try:
            await active_skarb[chat_id]["message"].delete()
        except:
            pass
        active_skarb.pop(chat_id, None)


# =====================================
# ПЕРЕВІРКА: ЄДИНИЙ ЖИВИЙ ГРАВЕЦЬ
# =====================================

async def check_last_survivor(chat_id: int, bot, game: dict):
    """Якщо залишився 1 живий гравець — він переможець."""
    alive = [uid for uid in game["participants"] if uid not in game["eliminated"]]
    if len(alive) != 1:
        return False

    winner_id = alive[0]
    winner_name = game["participants"][winner_id]["name"]

    game["active"] = False
    game["opened"][game["prize_pos"]] = WIN_CARD  # розкриваємо де був туз

    final_text = (
        f"🏆 <b>ОСТАННІЙ ЖИВИЙ — ПЕРЕМОЖЕЦЬ!</b>\n\n"
        f"<b>{winner_name}</b> вижив і забирає <b>{PRIZE_AMOUNT} грн</b>!\n\n"
        f"Туз чірва був на полі 👆"
    )

    try:
        await game["message"].edit_text(
            text=final_text,
            reply_markup=build_grid_keyboard(game, disabled=True),
            parse_mode="HTML"
        )
    except Exception as e:
        logging.warning(f"last survivor edit error: {e}")

    await _payout_winner(chat_id, bot, winner_id, winner_name, PRIZE_AMOUNT)

    active_skarb.pop(chat_id, None)

    if AUTO_DELETE_AFTER_WIN_SEC > 0:
        asyncio.create_task(cleanup_after_win(chat_id))

    return True


# =====================================
# ВИПЛАТА ПЕРЕМОЖЦЯ
# =====================================

async def _payout_winner(chat_id: int, bot, user_id: int, name: str, taken: int):
    if taken <= 0:
        return

    today_net = await get_daily_net(user_id)
    yesterday_net = await get_yesterday_net(user_id)
    total_net = _positive_or_zero(today_net) + _positive_or_zero(yesterday_net)

    if total_net < 200:
        await bot.send_message(
            chat_id=chat_id,
            text=(
                f"👤 <b>{name}</b> — виграш <b>{taken} грн</b>\n"
                f"❌ Не було депозиту! Виграш не нараховано❗"
            ),
            parse_mode="HTML"
        )
        return

    daily_game_win = await get_daily_game_win(user_id)
    yesterday_game_win = await get_yesterday_game_win(user_id)

    already_won = _positive_or_zero(daily_game_win) + _positive_or_zero(yesterday_game_win)
    max_allowed_win = int(total_net * 80 / 200)
    available_limit = max(max_allowed_win - already_won, 0)

    payout_amount = min(taken, available_limit)

    if payout_amount > 0:
        await add_to_balance(user_id, payout_amount)
        await add_daily_game_win(user_id, payout_amount)

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
        await bot.send_message(
            chat_id=chat_id,
            text=(
                f"👤 <b>{name}</b> — виграш <b>{taken} грн</b>\n"
                f"❌ Ліміт виграшів вичерпано."
            ),
            parse_mode="HTML"
        )


# =====================================
# СТАРТ ГРИ
# =====================================

async def start_skarb_game(chat_id: int, callback: CallbackQuery):
    if chat_id not in active_skarb:
        return

    game = active_skarb[chat_id]

    if game["active"]:
        await callback.answer("Гра вже почалася!", show_alert=True)
        return

    count = len(game["participants"])
    if count == 0:
        await callback.answer("Немає учасників — запуск неможливий", show_alert=True)
        return

    game["active"] = True

    prize_r = random.randint(0, GRID_SIZE - 1)
    prize_c = random.randint(0, GRID_SIZE - 1)
    game["prize_pos"] = (prize_r, prize_c)

    all_pos = [(r, c) for r in range(GRID_SIZE) for c in range(GRID_SIZE)]
    all_pos.remove(game["prize_pos"])
    special_pos = random.sample(all_pos, NUM_ARROWS + NUM_BOMBS)
    game["arrow_positions"] = set(special_pos[:NUM_ARROWS])
    game["bomb_positions"] = set(special_pos[NUM_ARROWS:])

    deck = game["deck"].copy()
    try:
        deck.remove(WIN_CARD)
    except ValueError:
        pass

    card_idx = 0
    for r in range(GRID_SIZE):
        for c in range(GRID_SIZE):
            pos = (r, c)
            if pos == game["prize_pos"]:
                game["card_map"][pos] = WIN_CARD
            elif pos in game["arrow_positions"]:
                game["card_map"][pos] = None
            elif pos in game["bomb_positions"]:
                game["card_map"][pos] = None
            else:
                if card_idx < len(deck):
                    game["card_map"][pos] = deck[card_idx]
                    card_idx += 1
                else:
                    game["card_map"][pos] = "🃏"

    try:
        await game["message"].edit_text(
            text=build_game_text(game),
            reply_markup=build_grid_keyboard(game),
            parse_mode="HTML"
        )
    except Exception as e:
        logging.warning(f"start_skarb_game edit error: {e}")

    await callback.message.answer("Гра почалася! Удачі всім! 🍀")


# =====================================
# КОМАНДА /skarb
# =====================================

@router.message(Command("skarb"))
async def cmd_skarb(message: Message):
    if message.from_user.id != ADMIN_ID:
        try: await message.delete()
        except: pass
        return

    chat_id = message.chat.id
    if chat_id in active_skarb:
        await message.answer("❌ У цьому чаті вже запущена гра «Скарб»!")
        return

    text = (
        "<b>🃏 ПОШУК ТУЗА ЧІРВА 🃏</b>\n\n"
        f"Приз: <b>{PRIZE_AMOUNT} грн</b>\n\n"
        f"Адмін може запустити гру в будь-який момент\n"
        f"Натискай «УЧАСТЬ», щоб приєднатися\n\n"
        f"Учасників: 0"
    )

    msg = await message.answer(
        text,
        reply_markup=build_lobby_keyboard(0),
        parse_mode="HTML"
    )

    active_skarb[chat_id] = {
        "message": msg,
        "participants": {},
        "prize_pos": None,
        "opened": {},
        "last_click": {},
        "eliminated": set(),
        "deck": generate_deck(),
        "card_map": {},
        "arrow_positions": set(),
        "bomb_positions": set(),
        "active": False,
    }


# =====================================
# ПРИЄДНАННЯ
# =====================================

@router.callback_query(F.data == "skarb_join")
async def skarb_join(callback: CallbackQuery):
    chat_id = callback.message.chat.id
    user = callback.from_user
    user_id = user.id

    if chat_id not in active_skarb:
        await callback.answer("Гра не знайдена", show_alert=True)
        return

    game = active_skarb[chat_id]

    if game["active"]:
        await callback.answer("Гра вже почалася!", show_alert=True)
        return

    on_cd, rem = is_on_cooldown(user_id)
    if on_cd:
        await callback.answer(
            f"⏳ Ти вже вигравав!\nНаступна гра через {format_cooldown(rem)}",
            show_alert=True
        )
        return

    if user_id in game["participants"]:
        await callback.answer("Ти вже приєднався!", show_alert=True)
        return

    if len(game["participants"]) >= REQUIRED_PLAYERS:
        await callback.answer(f"Максимум {REQUIRED_PLAYERS} гравців!", show_alert=True)
        return

    game["participants"][user_id] = {
        "name": get_display_name(user),
        "lives": INITIAL_LIVES
    }

    count = len(game["participants"])

    text = (
        f"<b>🃏 ПОШУК ТУЗА ЧІРВА 🃏</b>\n\n"
        f"Приз: <b>{PRIZE_AMOUNT} грн</b>\n\n"
        f"{get_starters_text(game)}\n\n"
        f"Учасників: <b>{count}</b>\n"
        f"Адмін може запустити гру кнопкою нижче"
    )

    try:
        await game["message"].edit_text(
            text=text,
            reply_markup=build_lobby_keyboard(count),
            parse_mode="HTML"
        )
    except Exception as e:
        logging.warning(f"skarb_join edit error: {e}")

    await callback.answer("Ти приєднався!")


# =====================================
# ЗАПУСК АДМІНОМ
# =====================================

@router.callback_query(F.data == "skarb_force_start")
async def skarb_force_start(callback: CallbackQuery):
    chat_id = callback.message.chat.id
    user_id = callback.from_user.id

    if user_id != ADMIN_ID:
        await callback.answer("Ця кнопка тільки для адміністратора", show_alert=True)
        return

    if chat_id not in active_skarb:
        await callback.answer("Гра вже неактивна", show_alert=True)
        return

    game = active_skarb[chat_id]

    if game["active"]:
        await callback.answer("Гра вже почалася", show_alert=True)
        return

    await start_skarb_game(chat_id, callback)
    await callback.answer("Гру запущено!")


# =====================================
# ПЕРЕЗАПУСК (адмін, будь-коли)
# =====================================

@router.callback_query(F.data == "skarb_reset")
async def skarb_reset(callback: CallbackQuery):
    chat_id = callback.message.chat.id
    user_id = callback.from_user.id

    if user_id != ADMIN_ID:
        await callback.answer("Тільки адмін може перезапустити гру", show_alert=True)
        return

    # Видаляємо стару гру якщо є
    old_game = active_skarb.pop(chat_id, None)
    _global_last_click.pop(chat_id, None)

    text = (
        "<b>🃏 ПОШУК ТУЗА ЧІРВА 🃏</b>\n\n"
        f"Приз: <b>{PRIZE_AMOUNT} грн</b>\n\n"
        f"Гру перезапущено адміном 🔄\n"
        f"Натискай «УЧАСТЬ», щоб приєднатися\n\n"
        f"Учасників: 0"
    )

    try:
        msg = await callback.message.answer(
            text,
            reply_markup=build_lobby_keyboard(0),
            parse_mode="HTML"
        )
    except Exception as e:
        logging.warning(f"skarb_reset send error: {e}")
        await callback.answer("Помилка перезапуску", show_alert=True)
        return

    # Намагаємось видалити старе повідомлення
    if old_game:
        try:
            await old_game["message"].delete()
        except:
            pass

    active_skarb[chat_id] = {
        "message": msg,
        "participants": {},
        "prize_pos": None,
        "opened": {},
        "last_click": {},
        "eliminated": set(),
        "deck": generate_deck(),
        "card_map": {},
        "arrow_positions": set(),
        "bomb_positions": set(),
        "active": False,
    }

    await callback.answer("Гру перезапущено! ✅")


# =====================================
# NOOP (кнопки заблокованого поля)
# =====================================

@router.callback_query(F.data == "skarb_noop")
async def skarb_noop(callback: CallbackQuery):
    await callback.answer("Гра завершена")


# =====================================
# КЛІКИ ПО ПОЛЮ
# =====================================

@router.callback_query(F.data.startswith("skarb_"))
async def skarb_click(callback: CallbackQuery):
    # Ігноруємо вже оброблені окремими хендлерами
    if callback.data in ("skarb_join", "skarb_force_start", "skarb_reset", "skarb_noop"):
        return

    chat_id = callback.message.chat.id
    user = callback.from_user
    user_id = user.id
    now = time.time()

    # --- Глобальний анти-флуд по чату ---
    last_global = _global_last_click.get(chat_id, 0)
    if now - last_global < GLOBAL_CLICK_COOLDOWN_SEC:
        await callback.answer("⏳ Зачекай!", show_alert=False)
        return
    _global_last_click[chat_id] = now

    if chat_id not in active_skarb:
        await callback.answer("Гра вже закінчена", show_alert=True)
        return

    game = active_skarb[chat_id]

    if not game.get("active", False):
        await callback.answer("Гра ще не почалася або вже закінчена", show_alert=True)
        return

    if user_id not in game["participants"]:
        await callback.answer("Тільки учасники гри можуть клікати", show_alert=True)
        return

    if user_id in game["eliminated"]:
        await callback.answer("Ти вже вибув (0 життів) 💣", show_alert=True)
        return

    # --- Персональний кулдаун гравця ---
    last_personal = game["last_click"].get(user_id, 0)
    if now - last_personal < CLICK_COOLDOWN_SEC:
        left = CLICK_COOLDOWN_SEC - (now - last_personal)
        await callback.answer(f"⏳ Зачекай ще ~{int(left)+1} сек", show_alert=True)
        return

    game["last_click"][user_id] = now

    try:
        parts = callback.data.split("_")
        r, c = int(parts[1]), int(parts[2])
    except:
        await callback.answer("Помилка", show_alert=True)
        return

    pos = (r, c)

    if pos in game["opened"]:
        await callback.answer("Вже відкрито", show_alert=True)
        return

    pr, pc = game["prize_pos"]

    # ===== ПЕРЕМОГА (знайшов туз) =====
    if r == pr and c == pc:
        game["opened"][pos] = WIN_CARD
        game["active"] = False
        game["winner"] = user_id

        winners_cooldown[user_id] = time.time() + WIN_COOLDOWN_HOURS * 3600

        name = game["participants"][user_id]["name"]

        final_text = (
            f"🎉 <b>ТУЗ ЧІРВА ЗНАЙДЕНО!</b> 🏆\n\n"
            f"{user.mention_html()} знайшов {WIN_CARD} і забирає <b>{PRIZE_AMOUNT} грн</b>!\n\n"
        )

        try:
            await game["message"].edit_text(
                text=final_text,
                reply_markup=build_grid_keyboard(game, disabled=True),
                parse_mode="HTML"
            )
        except Exception as e:
            logging.warning(f"win edit error: {e}")

        await _payout_winner(chat_id, callback.bot, user_id, name, PRIZE_AMOUNT)

        active_skarb.pop(chat_id, None)
        _global_last_click.pop(chat_id, None)

        if AUTO_DELETE_AFTER_WIN_SEC > 0:
            asyncio.create_task(cleanup_after_win(chat_id))

        await callback.answer(f"Вітаю! Ти знайшов {WIN_CARD} 🎉")
        return

    card = game["card_map"].get(pos)

    # ===== БОМБА =====
    if pos in game["bomb_positions"]:
        game["opened"][pos] = BOMB_CELL
        game["participants"][user_id]["lives"] -= 1

        if game["participants"][user_id]["lives"] <= 0:
            game["eliminated"].add(user_id)
            await callback.message.answer(
                f"💥 <b>{user.mention_html()}</b> втратив останнє життя і вибув з гри!",
                parse_mode="HTML"
            )
        else:
            await callback.answer("💥 БОМБА! Втратив життя!", show_alert=True)

        # Перевірка: залишився 1 живий?
        if await check_last_survivor(chat_id, callback.bot, game):
            _global_last_click.pop(chat_id, None)
            return

        # Перевірка: всі вибули?
        if len(game["eliminated"]) == len(game["participants"]):
            try:
                await game["message"].edit_text(
                    f"<b>💥 УСІ УЧАСНИКИ ВИБУХНУЛИ! ГРА ЗАКІНЧЕНА БЕЗ ПЕРЕМОЖЦЯ 😔</b>\n\n"
                    f"Приз {PRIZE_AMOUNT} грн ніхто не забрав.\n"
                    f"Спробуйте ще раз новою грою!",
                    reply_markup=None,
                    parse_mode="HTML"
                )
            except Exception as e:
                logging.warning(f"all eliminated edit error: {e}")
            game["active"] = False
            active_skarb.pop(chat_id, None)
            _global_last_click.pop(chat_id, None)
            return

        try:
            await game["message"].edit_text(
                text=build_game_text(game),
                reply_markup=build_grid_keyboard(game),
                parse_mode="HTML"
            )
        except Exception as e:
            logging.warning(f"bomb edit error: {e}")

        if game["participants"][user_id]["lives"] <= 0:
            pass  # вже відповіли вище через answer()
        else:
            await callback.answer("💥 БОМБА! Втратив життя!", show_alert=True)

    # ===== СТРІЛКА =====
    elif pos in game["arrow_positions"]:
        content = get_arrow(pr, pc, r, c)
        game["opened"][pos] = content

        try:
            await game["message"].edit_reply_markup(
                reply_markup=build_grid_keyboard(game)
            )
        except Exception as e:
            if "message is not modified" not in str(e).lower():
                logging.warning(f"arrow edit error: {e}")

        await callback.answer(content)

    # ===== ЗВИЧАЙНА КАРТА =====
    else:
        game["opened"][pos] = card

        if is_ace(card):
            game["participants"][user_id]["lives"] += 1
            await callback.answer(
                f"+1 життя! Тепер у тебе {game['participants'][user_id]['lives']} ❤️",
                show_alert=True
            )
            try:
                await game["message"].edit_text(
                    text=build_game_text(game),
                    reply_markup=build_grid_keyboard(game),
                    parse_mode="HTML"
                )
            except Exception as e:
                logging.warning(f"ace edit error: {e}")
        else:
            await callback.answer(card)
            try:
                await game["message"].edit_reply_markup(
                    reply_markup=build_grid_keyboard(game)
                )
            except Exception as e:
                if "message is not modified" not in str(e).lower():
                    logging.warning(f"card edit error: {e}")