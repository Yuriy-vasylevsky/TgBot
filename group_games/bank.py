from aiogram import Router, F
from aiogram.filters import Command, Filter
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, FSInputFile, InputMediaPhoto
import random
import asyncio

from handlers.config import ADMIN_ID

router = Router(name="group_pograb")
router.message.filter(F.chat.type.in_({"group", "supergroup"}))

# =====================================
# НАЛАШТУВАННЯ
# =====================================
REQUIRED_PLAYERS = 4
MAX_ROUNDS = 4
TOTAL_LOOT = 200
CODE_LENGTH = 2
TURN_TIMEOUT_SECONDS = 40

IMAGE_GUESSING = "bank1.png"
IMAGE_LOOTING  = "bank2.png"
IMAGE_FINAL    = "bank3.png"
IMAGE_CAUGHT   = "caught.png"
IMAGE_ESCAPED  = "escaped.png"

# Шанс спіймання у % для суми; 0 = безпечно
RISK_CHANCES = {100: 50, 150: 60, 200: 70}

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


def build_loot_keyboard(remaining: int) -> InlineKeyboardMarkup:
    amounts = [a for a in [25, 50, 100, 150] if a < remaining]
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
            "🔹 Кнопки 100, 150, 200 грн — ризиковані (шанс спіймання 50–70%)\n"
            "🔹 25 та 50 грн — безпечні\n"
            "🔹 Останній гравець забирає залишок без ризику\n"
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


async def finish_game(chat_id: int, bot, game: dict):
    """Видаляє статус і надсилає фінальне фото."""
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
    active_pograb.pop(chat_id, None)


async def advance_turn(chat_id: int, bot, game: dict):
    """Оновлює статус-повідомлення або завершує гру."""
    is_finished = game["remaining_loot"] <= 0 or game["current_turn"] >= len(game["ranking"])
    if is_finished:
        await finish_game(chat_id, bot, game)
        return

    new_status = await bot.send_message(
        chat_id=chat_id,
        text=status_text(game),
        reply_markup=build_loot_keyboard(game["remaining_loot"]),
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

        # Захист від race condition — якщо одночасно два гравці вгадали
        if user_id in game["ranking"]:
            return

        # Правильна відповідь
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

        # Видаляємо старе статус-повідомлення і надсилаємо нове з фото bank2
        try:
            await message.bot.delete_message(chat_id, game["status_msg_id"])
        except:
            pass

        new_status = await message.answer_photo(
            photo=FSInputFile(IMAGE_LOOTING),
            caption=status_text(game),
            reply_markup=build_loot_keyboard(game["remaining_loot"]),
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

    try:
        amount = int(callback.data.split("_take_")[1])
    except:
        return await callback.answer("Помилка", show_alert=True)

    if amount < 1 or amount > game["remaining_loot"]:
        return await callback.answer("Невірна сума!", show_alert=True)

    await callback.answer("Обробляємо...")

    name = game["participants"][user_id]["name"]
    is_last = game["current_turn"] == len(game["ranking"]) - 1
    risk = RISK_CHANCES.get(amount, 0)

    if is_last:
        # Останній гравець — без ризику, забирає залишок
        final_amount = game["remaining_loot"]
        await callback.message.answer(
            f"💰 <b>{name}</b> спокійно забирає залишок — <b>{final_amount} грн</b>",
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