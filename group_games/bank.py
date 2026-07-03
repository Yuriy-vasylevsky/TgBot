from aiogram import Router, F
from aiogram.filters import Command, Filter
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, FSInputFile, InputMediaPhoto
import random
import asyncio

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

router = Router(name="group_pograb")
router.message.filter(F.chat.type.in_({"group", "supergroup"}))

# =====================================
# НАЛАШТУВАННЯ
# =====================================
REQUIRED_PLAYERS = 3
MAX_ROUNDS = 3
TOTAL_LOOT = 150
CODE_LENGTH = 2
TURN_TIMEOUT_SECONDS = 45

# Максимальна сума, яку може забрати останній гравець (без ризику)
LAST_PLAYER_MAX = 80

IMAGE_GUESSING = "images/bank1.png"
IMAGE_LOOTING  = "images/bank2.png"
IMAGE_FINAL    = "images/bank3.png"
IMAGE_CAUGHT   = "images/caught.png"
IMAGE_ESCAPED  = "images/escaped.png"

# Доступні суми для забору (в порядку зростання)
LOOT_AMOUNTS = [30, 50, 80, 120, 150]

# Шанс спіймання у % для суми; 0 = безпечно
RISK_CHANCES = {80: 50, 120: 65, 150: 75}


def _positive_or_zero(value: int) -> int:
    return value if value > 0 else 0


active_pograb = {}


# =====================================
# ФІЛЬТР
# =====================================
class PograbActiveFilter(Filter):
    async def __call__(self, message: Message) -> bool:
        return message.chat.id in active_pograb


# =====================================
# ДОПОМІЖНІ ФУНКЦІЇ
# =====================================
def get_display_name(user) -> str:
    return f"@{user.username}" if user.username else user.full_name


def get_feedback(guess: str, secret: str) -> str:
    result = ['⬛'] * CODE_LENGTH
    secret_list = list(secret)
    for i in range(CODE_LENGTH):
        if guess[i] == secret_list[i]:
            result[i] = '🟩'
            secret_list[i] = None
    for i in range(CODE_LENGTH):
        if result[i] == '⬛' and guess[i] in secret_list:
            result[i] = '🟨'
            secret_list[secret_list.index(guess[i])] = None
    return ''.join(result)


def build_recruit_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔥 ЗАПУСТИТИ ГРУ", callback_data="pograb_force_start")],
        [InlineKeyboardButton(text="❌ Скасувати гру",  callback_data="pograb_cancel")],
    ])


def build_cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Скасувати гру", callback_data="pograb_cancel")],
    ])


def build_loot_keyboard(remaining: int, is_last: bool) -> InlineKeyboardMarkup:
    if is_last:
        capped = min(remaining, LAST_PLAYER_MAX)
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text=f"💰 ЗАБРАТИ {capped} грн",
                callback_data=f"pograb_take_{capped}"
            )],
        ])

    amounts = [a for a in LOOT_AMOUNTS if a < remaining]
    rows, row = [], []
    for a in amounts:
        row.append(InlineKeyboardButton(text=f"{a} грн", callback_data=f"pograb_take_{a}"))
        if len(row) == 3:
            rows.append(row); row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(
        text=f"💰 ЗАБРАТИ ВСЕ ({remaining} грн)",
        callback_data=f"pograb_take_{remaining}"
    )])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def status_text(game: dict) -> str:
    phase = game["phase"]

    if phase == "recruiting":
        return (
            "<b>🏦 ПОГРАБУВАННЯ БАНКУ</b>\n\n"
            "<b>ПРАВИЛА ГРИ:</b>\n"
            "🔹 Гравці на швидкість вгадують 2-значний код сейфа\n"
            "🔹 Хто вгадав — потрапляє в чергу на пограбування\n"
            f"🔹 У сейфі {TOTAL_LOOT} грн, кожен бере скільки хоче по черзі\n"
            "🔹 Кнопки 80, 120, 150 грн — ризиковані (шанс спіймання 50–80%)\n"
            "🔹 30 та 50 грн — безпечні\n"
            f"🔹 Останній гравець забирає залишок без ризику (максимум {LAST_PLAYER_MAX} грн)\n"
            f"🔹 Таймер на хід: {TURN_TIMEOUT_SECONDS} сек"
        )

    if phase == "guessing":
        ranking = "\n".join(
            f"{i+1}. {game['participants'][uid]['name']}" for i, uid in enumerate(game["ranking"])
        ) or "Очікуємо першого вгадування..."
        return (
            f"<b>🛡️ РАУНД {game['current_round']}/{MAX_ROUNDS}</b>\n"
            f"Взлом 2-значного коду\n\n"
            f"🟩 правильно  🟨 є, але не там  ⬛ немає\n\n"
            f"<b>Черга:</b>\n{ranking}\n\n"
            f"Пишіть двозначний код в чат"
        )

    if phase == "looting":
        ranking = "\n".join(
            f"{i+1}. {game['participants'][uid]['name']} — <b>{game['participants'][uid].get('taken', 0)} грн</b>"
            for i, uid in enumerate(game["ranking"])
        )
        current = ""
        if game["current_turn"] < len(game["ranking"]):
            uid = game["ranking"][game["current_turn"]]
            current = f"\n\n🔥 <b>Зараз ходить:</b> {game['participants'][uid]['name']}"
        return (
            f"<b>💰 ПОГРАБУВАННЯ СЕЙФУ</b>\n\n"
            f"Залишок у сейфі: <b>{game['remaining_loot']} грн</b>\n\n"
            f"<b>Черга:</b>\n{ranking}{current}"
        )


def final_text(game: dict) -> str:
    lines = "\n".join(
        f"{i+1}. {game['participants'][uid]['name']} — {game['participants'][uid].get('taken', 0)} грн"
        for i, uid in enumerate(game["ranking"])
    )
    return (
        f"<b>🏁 ПОГРАБУВАННЯ ЗАВЕРШЕНО!</b>\n\n"
        f"Залишок у сейфі: <b>{game['remaining_loot']} грн</b>\n\n"
        f"<b>Результати:</b>\n{lines}"
    )


def new_game_state(msg_id: int) -> dict:
    return {
        "phase": "recruiting",
        "participants": {},
        "ranking": [],
        "current_round": 1,
        "secret": None,
        "status_msg_id": msg_id,
        "round_messages": [],
        "remaining_loot": TOTAL_LOOT,
        "current_turn": 0,
        "turn_task": None,
    }


# =====================================
# ВИДАЧА ВИГРАШІВ ПІД ЧАС ФІНАЛІЗАЦІЇ
# =====================================
async def _payout_player(chat_id: int, bot, user_id: int, name: str, taken: int):
    """Перевіряє ліміти і нараховує виграш пропорційно депозиту."""
    if taken <= 0:
        return

    today_net = await get_daily_net(user_id)
    yesterday_net = await get_yesterday_net(user_id)
    total_net = _positive_or_zero(today_net) + _positive_or_zero(yesterday_net)

    # Немає депозиту взагалі — нічого не нараховуємо, кулдаун НЕ ставимо
    if total_net <= 0:
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
    # Ліміт пропорційний депозиту: 80 грн на кожні 200 грн депу
    # Приклад: деп 100 грн → ліміт 40 грн; деп 300 грн → ліміт 120 грн
    max_allowed_win = int(total_net * 80 / 200)
    available_limit = max(max_allowed_win - already_won, 0)

    payout_amount = min(taken, available_limit)

    if payout_amount > 0:
        await add_to_balance(user_id, payout_amount)
        await add_daily_game_win(user_id, payout_amount)
        # Кулдаун ставимо ТІЛЬКИ якщо гроші реально нараховано на баланс
        await set_game_cooldown(user_id)

        from db.winlog import log_win
        await log_win(user_id, None, name, "group", "💰 Банк", payout_amount)

    # Облік повного виграшу в іграх
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
        # Ліміт вичерпано повністю — нічого не нараховано, кулдаун НЕ ставимо
        await bot.send_message(
            chat_id=chat_id,
            text=(
                f"👤 <b>{name}</b> — виграш <b>{taken} грн</b>\n"
                f"❌ Ліміт виграшів вичерпано."
            ),
            parse_mode="HTML"
        )


async def finish_game(chat_id: int, bot, game: dict):
    """Видаляє статус, надсилає фінальне фото і окремо розраховує виграш кожного гравця."""
    try:
        await bot.delete_message(chat_id, game["status_msg_id"])
    except:
        pass
    await bot.send_photo(
        chat_id=chat_id,
        photo=FSInputFile(IMAGE_FINAL),
        caption=final_text(game),
        parse_mode="HTML"
    )

    for uid in game["ranking"]:
        info = game["participants"][uid]
        await _payout_player(chat_id, bot, uid, info["name"], info.get("taken", 0))

    active_pograb.pop(chat_id, None)


async def advance_turn(chat_id: int, bot, game: dict):
    """Оновлює статус-повідомлення або завершує гру."""
    is_finished = game["remaining_loot"] <= 0 or game["current_turn"] >= len(game["ranking"])
    if is_finished:
        await finish_game(chat_id, bot, game)
        return

    is_last_turn = game["current_turn"] == len(game["ranking"]) - 1
    new_status = await bot.send_message(
        chat_id=chat_id,
        text=status_text(game),
        reply_markup=build_loot_keyboard(game["remaining_loot"], is_last_turn),
        parse_mode="HTML"
    )
    try:
        await bot.delete_message(chat_id, game["status_msg_id"])
    except:
        pass
    game["status_msg_id"] = new_status.message_id

    if game.get("turn_task"):
        game["turn_task"].cancel()
    game["turn_task"] = asyncio.create_task(turn_timeout_task(chat_id, bot))


# =====================================
# ТАЙМАУТ ХОДУ
# =====================================
async def turn_timeout_task(chat_id: int, bot):
    await asyncio.sleep(TURN_TIMEOUT_SECONDS)
    game = active_pograb.get(chat_id)
    if not game or game["phase"] != "looting":
        return
    if game["current_turn"] >= len(game["ranking"]):
        return

    uid = game["ranking"][game["current_turn"]]
    name = game["participants"][uid]["name"]
    await bot.send_message(
        chat_id=chat_id,
        text=f"⏰ <b>{name}</b> не встиг зробити хід — копи зловили! Хід переходить далі.",
        parse_mode="HTML"
    )
    game["current_turn"] += 1
    await advance_turn(chat_id, bot, game)


# =====================================
# КОМАНДА /bank
# =====================================
@router.message(Command("bank"))
async def cmd_bank(message: Message):
    if message.from_user.id != ADMIN_ID:
        try:
            await message.delete()
        except:
            pass
        return

    chat_id = message.chat.id
    if chat_id in active_pograb:
        await message.answer("❌ У цьому чаті вже запущена гра!")
        return

    try:
        await message.delete()
    except:
        pass

    msg = await message.answer_photo(
        photo=FSInputFile(IMAGE_GUESSING),
        caption=status_text({"phase": "recruiting", "participants": {}}),
        reply_markup=build_recruit_keyboard(),
        parse_mode="HTML"
    )
    active_pograb[chat_id] = new_game_state(msg.message_id)


# =====================================
# ЗАПУСК ГРИ
# =====================================
@router.callback_query(F.data == "pograb_force_start")
async def pograb_force_start(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return await callback.answer("Тільки адмін може запустити гру", show_alert=True)

    chat_id = callback.message.chat.id
    game = active_pograb.get(chat_id)
    if not game:
        return await callback.answer("Гра вже неактивна", show_alert=True)

    game.update(phase="guessing", secret=f"{random.randint(0, 99):02d}", round_messages=[])

    try:
        await callback.bot.edit_message_caption(
            chat_id=chat_id, message_id=game["status_msg_id"],
            caption=status_text(game), reply_markup=build_cancel_keyboard(), parse_mode="HTML"
        )
    except Exception:
        pass

    await callback.answer("Гру запущено! 🔥")


# =====================================
# СКАСУВАННЯ
# =====================================
@router.callback_query(F.data == "pograb_cancel")
async def pograb_cancel(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return await callback.answer("Тільки адмін може скасувати гру", show_alert=True)

    chat_id = callback.message.chat.id
    game = active_pograb.pop(chat_id, None)
    if not game:
        return

    if game.get("turn_task"):
        game["turn_task"].cancel()
    try:
        await callback.bot.delete_message(chat_id, game["status_msg_id"])
    except:
        pass

    await callback.answer("Гра скасована")
    await callback.message.answer("❌ Пограбування банку скасовано")


# =====================================
# ВГАДУВАННЯ КОДУ
# =====================================
@router.message(F.text, PograbActiveFilter())
async def handle_pograb_message(message: Message):
    chat_id = message.chat.id
    user, user_id = message.from_user, message.from_user.id
    text = message.text.strip()
    game = active_pograb[chat_id]

    if game["phase"] == "guessing":
        is_admin = user_id == ADMIN_ID

        if user_id in game["ranking"]:
            if not is_admin:
                await message.delete()
            return

        if len(text) != CODE_LENGTH or not text.isdigit():
            if not is_admin:
                await message.delete()
            return

        game["round_messages"].append(message.message_id)
        resp = await message.answer(
            f"{user.mention_html()} → <b>{text}</b>  {get_feedback(text, game['secret'])}",
            parse_mode="HTML"
        )
        game["round_messages"].append(resp.message_id)

        if text != game["secret"]:
            return

        # Захист від race condition
        if user_id in game["ranking"]:
            return

        # Перевірка глобального кулдауну участі в іграх
        if await is_game_on_cooldown(user_id):
            remaining = await get_game_cooldown_remaining(user_id)
            cd_text = format_game_cooldown(*remaining) if remaining else "невідомо"
            cd_msg = await message.answer(
                f"{user.mention_html()}, ти нещодавно вже вигравав у грі!\n"
                f"⏳ Зачекай ще <b>{cd_text}</b>",
                parse_mode="HTML"
            )
            game["round_messages"].append(cd_msg.message_id)
            return

        if user_id not in game["participants"]:
            game["participants"][user_id] = {"name": get_display_name(user), "taken": 0}
        game["ranking"].append(user_id)

        win = await message.answer(
            f"🎉 <b>РАУНД {game['current_round']} ЗАВЕРШЕНО!</b>\n"
            f"{user.mention_html()} вгадав код <b>{game['secret']}</b>!",
            parse_mode="HTML"
        )
        game["round_messages"].append(win.message_id)

        for mid in game["round_messages"]:
            try:
                await message.bot.delete_message(chat_id, mid)
            except:
                pass
        game["round_messages"] = []

        if len(game["ranking"]) < MAX_ROUNDS:
            game["current_round"] += 1
            game["secret"] = f"{random.randint(0, 99):02d}"
            try:
                await message.bot.edit_message_caption(
                    chat_id=chat_id, message_id=game["status_msg_id"],
                    caption=status_text(game), reply_markup=build_cancel_keyboard(), parse_mode="HTML"
                )
            except Exception:
                pass
            return

        # Всі раунди зіграно — переходимо до пограбування
        ranked_set = set(game["ranking"])
        last_uid = next((uid for uid in game["participants"] if uid not in ranked_set), None)
        if last_uid:
            game["ranking"].append(last_uid)

        game.update(phase="looting", current_turn=0)

        try:
            await message.bot.delete_message(chat_id, game["status_msg_id"])
        except:
            pass

        is_last_turn = game["current_turn"] == len(game["ranking"]) - 1
        new_status = await message.answer_photo(
            photo=FSInputFile(IMAGE_LOOTING),
            caption=status_text(game),
            reply_markup=build_loot_keyboard(game["remaining_loot"], is_last_turn),
            parse_mode="HTML"
        )
        game["status_msg_id"] = new_status.message_id
        game["turn_task"] = asyncio.create_task(turn_timeout_task(chat_id, message.bot))

    elif game["phase"] == "looting":
        if user_id not in game["participants"] or game["current_turn"] >= len(game["ranking"]):
            await message.delete()
            return
        if user_id != game["ranking"][game["current_turn"]]:
            return
        await message.delete()


# =====================================
# ЗАБИРАННЯ ГРОШЕЙ
# =====================================
@router.callback_query(F.data.startswith("pograb_take_"))
async def pograb_take_money(callback: CallbackQuery):
    chat_id = callback.message.chat.id
    user_id = callback.from_user.id
    game = active_pograb.get(chat_id)

    if not game or game["phase"] != "looting" or game["current_turn"] >= len(game["ranking"]):
        return await callback.answer("Гра вже завершена", show_alert=True)
    if user_id != game["ranking"][game["current_turn"]]:
        return await callback.answer("Не твоя черга!", show_alert=True)

    is_last = game["current_turn"] == len(game["ranking"]) - 1

    try:
        amount = int(callback.data.split("_take_")[1])
    except:
        return await callback.answer("Помилка", show_alert=True)

    max_allowed = min(game["remaining_loot"], LAST_PLAYER_MAX) if is_last else game["remaining_loot"]
    if amount < 1 or amount > max_allowed:
        return await callback.answer("Невірна сума!", show_alert=True)

    await callback.answer("Обробляємо...")

    name = game["participants"][user_id]["name"]
    risk = RISK_CHANCES.get(amount, 0)

    if is_last:
        final_amount = amount
        await callback.message.answer(
            f"💰 <b>{name}</b> спокійно забирає <b>{final_amount} грн</b>",
            parse_mode="HTML"
        )
    elif risk > 0:
        caught = random.random() < (risk / 100)
        if caught:
            await callback.message.answer_photo(
                photo=FSInputFile(IMAGE_CAUGHT),
                caption=f"💰 <b>{name}</b> намагався забрати <b>{amount} грн</b>\n😭 <b>ВАС СПІЙМАЛИ КОПИ!</b>",
                parse_mode="HTML"
            )
            final_amount = 0
        else:
            await callback.message.answer_photo(
                photo=FSInputFile(IMAGE_ESCAPED),
                caption=f"💰 <b>{name}</b> намагався забрати <b>{amount} грн</b>\n🏃‍♂️ <b>ВИ ЗМОГЛИ ВТЕКТИ!</b>",
                parse_mode="HTML"
            )
            final_amount = amount
    else:
        final_amount = amount
        await callback.message.answer(
            f"💰 <b>{name}</b> забрав <b>{final_amount} грн</b>\n"
            f"Залишок: <b>{game['remaining_loot'] - final_amount} грн</b>",
            parse_mode="HTML"
        )

    if final_amount > 0:
        game["remaining_loot"] -= final_amount
        game["participants"][user_id]["taken"] += final_amount

    game["current_turn"] += 1

    if game.get("turn_task"):
        game["turn_task"].cancel()
    await advance_turn(chat_id, callback.bot, game)