from aiogram import Router, F
from aiogram.filters import Command, Filter
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, FSInputFile, InputMediaPhoto
import random
import asyncio

from handlers.config import ADMIN_ID

router = Router(name="group_pograb")
router.message.filter(F.chat.type.in_({"group", "supergroup"}))

REQUIRED_PLAYERS = 2
MAX_ROUNDS = 2
TOTAL_LOOT = 200
CODE_LENGTH = 2

IMAGE_GUESSING = "bank1.png"
IMAGE_LOOTING = "bank2.png"
IMAGE_3 = "bank3.png"
IMAGE_POLICE = "police.png"          # ← картинка поліції (залишена)

# === НАЛАШТУВАННЯ ===
RISK_CHANCES = {200: 70, 150: 60, 100: 50}

POLICE_HEADING = "🚨 ЗА ВАМИ ВИЇХАЛА ПОЛІЦІЯ 🚨"
CAUGHT_TEXT = "😭 <b>ВАС СПІЙМАЛИ КОПИ!</b>\nВи надто довго збирали гроші."
ESCAPED_TEXT = "🏃‍♂️ <b>ВИ ЗМОГЛИ ВТЕКТИ!</b>\nГроші ваші!"

LAST_PLAYER_TEXT = "🎟️ <b>Копам на вас всеодно бо ви поганий взломщик сейфів, спокійно забираєте все що залишилось</b>"

TURN_TIMEOUT_SECONDS = 40
TIMEOUT_CAUGHT_TEXT = "⏰ <b>ВИ ЗАНАДТО ДОВГО ГРАБУВАЛИ!</b>\nКопи вас зловили. Хід переходить далі."


active_pograb = {}


class PograbActiveFilter(Filter):
    async def __call__(self, message: Message) -> bool:
        return message.chat.id in active_pograb


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
        [InlineKeyboardButton(text="❌ Скасувати гру", callback_data="pograb_cancel")]
    ])


def build_cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Скасувати гру", callback_data="pograb_cancel")]
    ])


def build_loot_keyboard(remaining: int) -> InlineKeyboardMarkup:
    if remaining <= 0:
        return InlineKeyboardMarkup(inline_keyboard=[])

    amounts = [amt for amt in [25, 50, 100, 150] if amt < remaining]
    keyboard = []
    row = []
    for amt in amounts:
        row.append(InlineKeyboardButton(text=f"{amt} грн", callback_data=f"pograb_take_{amt}"))
        if len(row) == 3:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    keyboard.append([InlineKeyboardButton(
        text=f"💰 ЗАБРАТИ ВСЕ ({remaining} грн)",
        callback_data=f"pograb_take_{remaining}"
    )])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_status_text(game: dict) -> str:
    phase = game["phase"]

    if phase == "recruiting":
        participants = "\n".join(f"• {data['name']}" for data in game["participants"].values()) or "Поки нікого..."
        return f"<b>🏦 ПОГРАБУВАННЯ БАНКУ</b>\n\n👥 Учасники:\n{participants}\n\n<b>{len(game['participants'])}/{REQUIRED_PLAYERS}</b> гравців"

    elif phase == "guessing":
        round_num = game["current_round"]
        ranking = "\n".join(f"{i+1}. {game['participants'][uid]['name']}" for i, uid in enumerate(game["ranking"])) or "Очікуємо першого вгадування..."
        return f"<b>🛡️ РАУНД {round_num}/{MAX_ROUNDS}</b>\nВзлом 2-значного коду\n\n🟩 правильно 🟨 є, але не там ⬛ немає\n\n<b>Черга:</b>\n{ranking}\n\nПишіть двозначний код в чат"

    elif phase == "looting":
        remaining = game["remaining_loot"]
        ranking = "\n".join(f"{i+1}. {game['participants'][uid]['name']} — <b>{game['participants'][uid].get('taken', 0)} грн</b>" for i, uid in enumerate(game["ranking"]))
        current = f"\n\n🔥 <b>Зараз ходить:</b> {game['participants'][game['ranking'][game['current_turn']]]['name']}" if game["current_turn"] < len(game["ranking"]) else ""
        return f"<b>💰 ПОГРАБУВАННЯ СЕЙФУ</b>\n\nЗалишок у сейфі: <b>{remaining} грн</b>\n\n<b>Черга:</b>\n{ranking}{current}"


def get_final_text(game: dict) -> str:
    ranking_lines = "\n".join(f"{i+1}. {game['participants'][uid]['name']} — {game['participants'][uid].get('taken', 0)} грн" for i, uid in enumerate(game["ranking"]))
    return f"<b>🏁 ПОГРАБУВАННЯ ЗАВЕРШЕНО!</b>\n\nЗалишок у сейфі: <b>{game['remaining_loot']} грн</b>\n\n<b>Переможці:</b>\n{ranking_lines}"


async def create_pograb(message: Message):
    chat_id = message.chat.id
    if chat_id in active_pograb:
        await message.answer("❌ У цьому чаті вже запущена гра!")
        return

    try: await message.delete()
    except: pass

    msg = await message.answer_photo(
        photo=FSInputFile(IMAGE_GUESSING),
        caption=get_status_text({"phase": "recruiting", "participants": {}}),
        reply_markup=build_recruit_keyboard(),
        parse_mode="HTML"
    )

    active_pograb[chat_id] = {
        "phase": "recruiting",
        "participants": {},
        "ranking": [],
        "current_round": 1,
        "secret": None,
        "status_msg_id": msg.message_id,
        "round_messages": [],
        "remaining_loot": TOTAL_LOOT,
        "current_turn": 0,
        "turn_task": None,
    }


@router.message(Command("bank"))
async def cmd_bank(message: Message):
    if message.from_user.id != ADMIN_ID:
        try: await message.delete()
        except: pass
        return
    await create_pograb(message)


@router.callback_query(F.data == "pograb_force_start")
async def pograb_force_start(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return await callback.answer("Тільки адмін може запустити гру", show_alert=True)

    chat_id = callback.message.chat.id
    if chat_id not in active_pograb:
        return await callback.answer("Гра вже неактивна", show_alert=True)

    game = active_pograb[chat_id]
    game["phase"] = "guessing"
    game["secret"] = f"{random.randint(0, 99):02d}"
    game["round_messages"] = []

    await callback.bot.edit_message_caption(
        chat_id=chat_id,
        message_id=game["status_msg_id"],
        caption=get_status_text(game),
        reply_markup=build_cancel_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer("Гру запущено! 🔥")


@router.callback_query(F.data == "pograb_cancel")
async def pograb_cancel(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return await callback.answer("Тільки адмін може скасувати гру", show_alert=True)

    chat_id = callback.message.chat.id
    if chat_id not in active_pograb:
        return

    game = active_pograb[chat_id]
    if game.get("turn_task"):
        game["turn_task"].cancel()

    try: await callback.bot.delete_message(chat_id, game["status_msg_id"])
    except: pass

    active_pograb.pop(chat_id, None)
    await callback.answer("Гра скасована")
    await callback.message.answer("❌ Пограбування банку скасовано")


@router.message(F.text, PograbActiveFilter())
async def handle_pograb_message(message: Message):
    chat_id = message.chat.id
    user = message.from_user
    user_id = user.id
    text = message.text.strip()
    game = active_pograb[chat_id]

    if game["phase"] == "guessing":
        is_admin = (user_id == ADMIN_ID)

        if user_id in game["ranking"]:
            if not is_admin: await message.delete()
            return

        if len(text) != CODE_LENGTH or not text.isdigit():
            if not is_admin: await message.delete()
            return

        game["round_messages"].append(message.message_id)
        feedback = get_feedback(text, game["secret"])

        resp = await message.answer(f"{user.mention_html()} → <b>{text}</b>  {feedback}", parse_mode="HTML")
        game["round_messages"].append(resp.message_id)

        if text == game["secret"]:
            if user_id not in game["participants"]:
                game["participants"][user_id] = {"name": get_display_name(user), "taken": 0}
            game["ranking"].append(user_id)

            win_msg = await message.answer(
                f"🎉 <b>РАУНД {game['current_round']} ЗАВЕРШЕНО!</b>\n{user.mention_html()} вгадав код <b>{game['secret']}</b>!",
                parse_mode="HTML"
            )
            game["round_messages"].append(win_msg.message_id)

            for mid in game["round_messages"]:
                try: await message.bot.delete_message(chat_id, mid)
                except: pass
            game["round_messages"] = []

            if len(game["ranking"]) == MAX_ROUNDS:
                ranked_set = set(game["ranking"])
                last_uid = next((uid for uid in game["participants"] if uid not in ranked_set), None)
                if last_uid:
                    game["ranking"].append(last_uid)

                game["phase"] = "looting"
                game["current_turn"] = 0

                await message.bot.edit_message_media(
                    chat_id=chat_id,
                    message_id=game["status_msg_id"],
                    media=InputMediaPhoto(media=FSInputFile(IMAGE_LOOTING), caption=get_status_text(game), parse_mode="HTML")
                )

                new_status = await message.answer(
                    text=get_status_text(game),
                    reply_markup=build_loot_keyboard(game["remaining_loot"]),
                    parse_mode="HTML"
                )
                game["status_msg_id"] = new_status.message_id

                if game.get("turn_task"): game["turn_task"].cancel()
                game["turn_task"] = asyncio.create_task(turn_timeout_task(chat_id, message.bot))

            else:
                game["current_round"] += 1
                game["secret"] = f"{random.randint(0, 99):02d}"
                await message.bot.edit_message_caption(
                    chat_id=chat_id,
                    message_id=game["status_msg_id"],
                    caption=get_status_text(game),
                    reply_markup=build_cancel_keyboard(),
                    parse_mode="HTML"
                )

    elif game["phase"] == "looting":
        if user_id not in game["participants"] or game["current_turn"] >= len(game["ranking"]):
            await message.delete()
            return
        if user_id != game["ranking"][game["current_turn"]]:
            return
        await message.delete()


@router.callback_query(F.data.startswith("pograb_take_"))
async def pograb_take_money(callback: CallbackQuery):
    chat_id = callback.message.chat.id
    user_id = callback.from_user.id

    if chat_id not in active_pograb: return
    game = active_pograb[chat_id]

    if game["phase"] != "looting" or game["current_turn"] >= len(game["ranking"]):
        return await callback.answer("Гра вже завершена", show_alert=True)

    if user_id != game["ranking"][game["current_turn"]]:
        return await callback.answer("Не твоя черга!", show_alert=True)

    try:
        amount = int(callback.data.split("_take_")[1])
    except:
        return await callback.answer("Помилка", show_alert=True)

    if amount < 1 or amount > game["remaining_loot"]:
        return await callback.answer("Невірна сума!", show_alert=True)

    await callback.answer("Обробляємо запит...")

    name = game["participants"][user_id]["name"]
    is_last_player = (game["current_turn"] == len(game["ranking"]) - 1)

    if is_last_player:
        final_amount = game["remaining_loot"]
        await callback.message.answer(
            f"💰 <b>{name}</b> {LAST_PLAYER_TEXT}\nВи отримали <b>{final_amount} грн</b>",
            parse_mode="HTML"
        )
    else:
        risk_chance = RISK_CHANCES.get(amount, 0)

        if risk_chance > 0:
            # Залишаємо картинку + напис (без анімації)
            police_photo = FSInputFile(IMAGE_POLICE)
            await callback.message.answer_photo(
                photo=police_photo,
                caption=POLICE_HEADING
            )

            caught = random.random() < (risk_chance / 100.0)
            result_text = CAUGHT_TEXT if caught else ESCAPED_TEXT
            final_amount = 0 if caught else amount

            await callback.message.answer(
                f"💰 <b>{name}</b> намагався забрати <b>{amount} грн</b>\n{result_text}",
                parse_mode="HTML"
            )
        else:
            final_amount = amount

    if final_amount > 0:
        game["remaining_loot"] -= final_amount
        game["participants"][user_id]["taken"] += final_amount

        if not is_last_player and RISK_CHANCES.get(amount, 0) == 0:
            await callback.message.answer(
                f"💰 <b>{name}</b> забрав <b>{final_amount} грн</b>\nЗалишок: <b>{game['remaining_loot']} грн</b>",
                parse_mode="HTML"
            )

    game["current_turn"] += 1

    is_finished = game["remaining_loot"] <= 0 or game["current_turn"] >= len(game["ranking"])

    if game.get("turn_task"):
        game["turn_task"].cancel()

    if not is_finished:
        new_status = await callback.message.answer(
            text=get_status_text(game),
            reply_markup=build_loot_keyboard(game["remaining_loot"]),
            parse_mode="HTML"
        )
        try: await callback.bot.delete_message(chat_id, game["status_msg_id"])
        except: pass
        game["status_msg_id"] = new_status.message_id

        game["turn_task"] = asyncio.create_task(turn_timeout_task(chat_id, callback.bot))
    else:
        try: await callback.bot.delete_message(chat_id, game["status_msg_id"])
        except: pass
        await callback.message.answer_photo(
            photo=FSInputFile(IMAGE_3),
            caption=get_final_text(game),
            parse_mode="HTML"
        )
        active_pograb.pop(chat_id, None)


async def turn_timeout_task(chat_id: int, bot):
    await asyncio.sleep(TURN_TIMEOUT_SECONDS)
    game = active_pograb.get(chat_id)
    if not game or game["phase"] != "looting":
        return

    current_turn = game.get("current_turn", 0)
    if current_turn >= len(game["ranking"]):
        return

    user_id = game["ranking"][current_turn]
    name = game["participants"][user_id]["name"]

    await bot.send_message(chat_id=chat_id, text=f"💰 <b>{name}</b> {TIMEOUT_CAUGHT_TEXT}", parse_mode="HTML")

    game["current_turn"] += 1
    is_finished = game["remaining_loot"] <= 0 or game["current_turn"] >= len(game["ranking"])

    if not is_finished:
        new_status = await bot.send_message(
            chat_id=chat_id,
            text=get_status_text(game),
            reply_markup=build_loot_keyboard(game["remaining_loot"]),
            parse_mode="HTML"
        )
        try: await bot.delete_message(chat_id, game["status_msg_id"])
        except: pass
        game["status_msg_id"] = new_status.message_id
    else:
        try: await bot.delete_message(chat_id, game["status_msg_id"])
        except: pass
        await bot.send_photo(chat_id=chat_id, photo=FSInputFile(IMAGE_3), caption=get_final_text(game), parse_mode="HTML")
        active_pograb.pop(chat_id, None)