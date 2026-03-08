from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
import asyncio
import logging
import random
import time

from handlers.config import ADMIN_ID   # ← зміни шлях, якщо потрібно

router = Router(name="group_skarb")
router.message.filter(F.chat.type.in_({"group", "supergroup"}))

# =====================================
# НАЛАШТУВАННЯ ГРИ «СКАРБ»
# =====================================
GRID_SIZE = 8
REQUIRED_PLAYERS = 5          # це тепер більше орієнтир, а не жорстка вимога
PRIZE_AMOUNT = 50
CLICK_COOLDOWN_SEC = 6
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


# =====================================
# ДОПОМІЖНІ ФУНКЦІЇ
# =====================================
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
                row.append(InlineKeyboardButton(text=text, callback_data="disabled"))
            else:
                row.append(InlineKeyboardButton(text=text, callback_data=f"skarb_{r}_{c}"))
        keyboard.append(row)
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


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
# ЗАПУСК ГРИ (генерація поля)
# =====================================
async def start_skarb_game(chat_id: int, message_or_query, forced: bool = True):
    if chat_id not in active_skarb:
        return

    game = active_skarb[chat_id]

    if game["active"]:
        if hasattr(message_or_query, 'answer'):
            await message_or_query.answer("Гра вже почалася!")
        else:
            await message_or_query.message.answer("Гра вже почалася!")
        return

    count = len(game["participants"])
    if count == 0:
        if hasattr(message_or_query, 'answer'):
            await message_or_query.answer("Немає учасників — запуск неможливий", show_alert=True)
        else:
            await message_or_query.message.answer("Немає учасників — запуск неможливий")
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

    text = (
        f"<b>🃏 ТУЗ ЧІРВА ЗАХОВАНО НА ПОЛІ 8×8! 🃏</b>\n\n"
        f"Приз — <b>{PRIZE_AMOUNT} грн</b>\n\n"
        f"{get_starters_text(game)}\n\n"
        f"Гравців: <b>{count}</b>\n"
        f"Клікай на {CLOSED_CELL} (кожні {CLICK_COOLDOWN_SEC} сек)\n"
        f"Туз дає +1 життя ❤️"
    )

    await message_or_query.message.edit_text(
        text=text,
        reply_markup=build_grid_keyboard(game),
        parse_mode="HTML"
    )

    await message_or_query.message.answer("Гра почалася! Удачі всім! 🍀")


# =====================================
# СТАРТ ГРИ КОМАНДОЮ /skarb
# =====================================
async def create_skarb(message: Message):
    chat_id = message.chat.id
    if chat_id in active_skarb:
        await message.answer("❌ У цьому чаті вже запущена гра «Скарб»!")
        return

    buttons = [
        [InlineKeyboardButton(
            text=f"🚀 УЧАСТЬ (0/{REQUIRED_PLAYERS})",
            callback_data="skarb_join"
        )],
        [InlineKeyboardButton(
            text="🔥 Запустити гру",
            callback_data="skarb_force_start"
        )]
    ]

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    text = (
        "<b>🃏 ПОШУК ТУЗА ЧІРВА 🃏</b>\n\n"
        f"Приз: <b>{PRIZE_AMOUNT} грн</b>\n\n"
        f"Адмін може запустити гру в будь-який момент\n"
        f"Натискай «УЧАСТЬ», щоб приєднатися\n\n"
        f"Учасників: 0"
    )

    msg = await message.answer(text, reply_markup=keyboard, parse_mode="HTML")

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
        "active": False
    }


@router.message(Command("skarb"))
async def cmd_skarb(message: Message):
    if message.from_user.id != ADMIN_ID:
        try: await message.delete()
        except: pass
        return
    await create_skarb(message)


# =====================================
# ПРИЄДНАННЯ ДО ГРИ
# =====================================
@router.callback_query(F.data == "skarb_join")
async def skarb_join(callback: CallbackQuery):
    chat_id = callback.message.chat.id
    user = callback.from_user
    user_id = user.id

    if chat_id not in active_skarb:
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

    game["participants"][user_id] = {
        "name": get_display_name(user),
        "lives": INITIAL_LIVES
    }

    count = len(game["participants"])

    buttons = [
        [InlineKeyboardButton(
            text=f"🚀 УЧАСТЬ ({count}/{REQUIRED_PLAYERS})",
            callback_data="skarb_join"
        )],
        [InlineKeyboardButton(
            text="🔥 Запустити гру",
            callback_data="skarb_force_start"
        )]
    ]

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    text = (
        f"<b>🃏 ПОШУК ТУЗА ЧІРВА 🃏</b>\n\n"
        f"Приз: <b>{PRIZE_AMOUNT} грн</b>\n\n"
        f"{get_starters_text(game)}\n\n"
        f"Учасників: <b>{count}</b>\n"
        f"Адмін може запустити гру кнопкою нижче"
    )

    await callback.message.edit_text(
        text=text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )

    await callback.answer("Ти приєднався!")


# =====================================
# ЗАПУСК ГРИ АДМІНОМ
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
# КЛІК ПО КЛІТИНЦІ
# =====================================
@router.callback_query(F.data.startswith("skarb_"))
async def skarb_click(callback: CallbackQuery):
    chat_id = callback.message.chat.id
    user = callback.from_user
    user_id = user.id

    if chat_id not in active_skarb:
        await callback.answer("Гра вже закінчена", show_alert=True)
        return

    game = active_skarb[chat_id]

    if callback.data == "disabled":
        await callback.answer("Гра завершена", show_alert=True)
        return

    if not game.get("active", False):
        await callback.answer("Гра вже закінчена", show_alert=True)
        return

    if user_id not in game["participants"]:
        await callback.answer("Тільки учасники гри можуть клікати", show_alert=True)
        return

    if user_id in game["eliminated"]:
        await callback.answer("Ти вже вибув (0 життів) 💣", show_alert=True)
        return

    now = time.time()
    if user_id in game["last_click"] and now - game["last_click"][user_id] < CLICK_COOLDOWN_SEC:
        left = CLICK_COOLDOWN_SEC - (now - game["last_click"][user_id])
        await callback.answer(f"⏳ Зачекай ще ~{int(left)+1} сек", show_alert=True)
        return

    game["last_click"][user_id] = now

    try:
        _, r_str, c_str = callback.data.split("_")
        r, c = int(r_str), int(c_str)
    except:
        await callback.answer("Помилка", show_alert=True)
        return

    pos = (r, c)

    if pos in game["opened"]:
        await callback.answer("Вже відкрито", show_alert=True)
        return

    pr, pc = game["prize_pos"]

    if r == pr and c == pc:
        game["opened"][pos] = WIN_CARD
        game["active"] = False
        game["winner"] = user_id

        winners_cooldown[user_id] = time.time() + WIN_COOLDOWN_HOURS * 3600

        final_text = (
            f"🎉 <b>ТУЗ ЧІРВА ЗНАЙДЕНО!</b> 🏆\n\n"
            f"{user.mention_html()} знайшов {WIN_CARD} і забирає <b>{PRIZE_AMOUNT} грн</b>!\n\n"
        )

        await callback.message.edit_text(
            text=final_text,
            reply_markup=build_grid_keyboard(game, disabled=True),
            parse_mode="HTML"
        )

        if AUTO_DELETE_AFTER_WIN_SEC > 0:
            asyncio.create_task(cleanup_after_win(chat_id))

        active_skarb.pop(chat_id, None)

        await callback.answer(f"Вітаю! Ти знайшов {WIN_CARD}")
        return

    card = game["card_map"].get(pos)

    if pos in game["bomb_positions"]:
        game["opened"][pos] = BOMB_CELL
        game["participants"][user_id]["lives"] -= 1

        if game["participants"][user_id]["lives"] <= 0:
            game["eliminated"].add(user_id)
            await callback.message.answer(
                f"💥 <b>{user.mention_html()}</b> втратив останнє життя і вибув з гри!",
                parse_mode="HTML"
            )

        await callback.message.edit_text(
            f"<b>🃏 ТУЗ ЧІРВА ЗАХОВАНО НА ПОЛІ 8×8! 🃏</b>\n\n"
            f"Приз — <b>{PRIZE_AMOUNT} грн</b>\n\n"
            f"{get_starters_text(game)}\n\n"
            f"Клікай на {CLOSED_CELL} (кожні {CLICK_COOLDOWN_SEC} сек)\n"
            f"52 карти + {NUM_ARROWS} стрілок + {NUM_BOMBS} бомб 💣\n"
            f"Туз дає +1 життя ❤️",
            reply_markup=build_grid_keyboard(game),
            parse_mode="HTML"
        )

        await callback.answer("💥 БОМБА! Втратив життя!", show_alert=True)

        if len(game["eliminated"]) == len(game["participants"]):
            await callback.message.edit_text(
                f"<b>💥 УСІ УЧАСНИКИ ВИБУХНУЛИ! ГРА ЗАКІНЧЕНА БЕЗ ПЕРЕМОЖЦЯ 😔</b>\n\n"
                f"Приз {PRIZE_AMOUNT} грн ніхто не забрав.\n"
                f"Спробуйте ще раз новою грою!",
                reply_markup=None,
                parse_mode="HTML"
            )
            game["active"] = False
            active_skarb.pop(chat_id, None)

    elif pos in game["arrow_positions"]:
        content = get_arrow(pr, pc, r, c)
        game["opened"][pos] = content
        await callback.answer(content)
    else:
        content = card
        game["opened"][pos] = content
        await callback.answer(content)

        if is_ace(card):
            game["participants"][user_id]["lives"] += 1
            await callback.answer(f"+1 життя! Тепер у тебе {game['participants'][user_id]['lives']} ❤️", show_alert=True)

            await callback.message.edit_text(
                f"<b>🃏 ТУЗ ЧІРВА ЗАХОВАНО НА ПОЛІ 8×8! 🃏</b>\n\n"
                f"Приз — <b>{PRIZE_AMOUNT} грн</b>\n\n"
                f"{get_starters_text(game)}\n\n"
                f"Клікай на {CLOSED_CELL} (кожні {CLICK_COOLDOWN_SEC} сек)\n"
                f"52 карти + {NUM_ARROWS} стрілок + {NUM_BOMBS} бомб 💣\n"
                f"Туз дає +1 життя ❤️",
                reply_markup=build_grid_keyboard(game),
                parse_mode="HTML"
            )

    try:
        await callback.message.edit_reply_markup(reply_markup=build_grid_keyboard(game))
    except Exception as e:
        if "message is not modified" not in str(e).lower():
            logging.warning(f"skarb edit warning: {e}")