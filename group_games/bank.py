from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, FSInputFile
import logging
import random

from handlers.config import ADMIN_ID

router = Router(name="group_pograb")
router.message.filter(F.chat.type.in_({"group", "supergroup"}))

# =====================================
# НАЛАШТУВАННЯ ГРИ
# =====================================
REQUIRED_PLAYERS = 4
MAX_ROUNDS = 4

TOTAL_LOOT = 200
CODE_LENGTH = 2

IMAGE_GUESSING = "bank1.png"
IMAGE_LOOTING = "bank2.png"

active_pograb = {}


# =====================================
# ДОПОМІЖНІ ФУНКЦІЇ
# =====================================
def get_display_name(user) -> str:
    return f"@{user.username}" if user.username else user.full_name


def build_recruit_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton(text="🔥 Запустити гру", callback_data="pograb_force_start")],
        [InlineKeyboardButton(text="❌ Скасувати гру", callback_data="pograb_cancel")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


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


def build_loot_keyboard(remaining: int) -> InlineKeyboardMarkup:
    if remaining <= 0:
        return InlineKeyboardMarkup(inline_keyboard=[])

    fixed = [25, 50, 100, 150, 200]
    amounts = [amt for amt in fixed if amt < remaining]

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
        text=f"💰 Забрати все ({remaining} грн)",
        callback_data=f"pograb_take_{remaining}"
    )])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_status_text(game: dict) -> str:
    phase = game["phase"]
    text = "<b>🏦 ПОГРАБУВАННЯ БАНКУ 🏦</b>\n\n"

    if phase in ("recruiting", "guessing"):
        text += f"Загальний скарб: <b>{TOTAL_LOOT} грн</b>\n\n"

    if phase == "recruiting":
        text += "👥 Учасники:\n"
        for data in game["participants"].values():
            text += f"• {data['name']}\n"
        text += f"\nУчасників: <b>{len(game['participants'])}</b>/{REQUIRED_PLAYERS}\n"
        text += f"Максимум {REQUIRED_PLAYERS} учасників"

    elif phase == "guessing":
        round_num = game["current_round"]
        ranked_lines = [f"{i}. {game['participants'][uid]['name']}" for i, uid in enumerate(game["ranking"], 1)]

        text += f"Раунд {round_num}/{MAX_ROUNDS} — взлом {CODE_LENGTH}-значного коду!\n\n"
        text += "🟩 — цифра на правильному місці\n"
        text += "🟨 — цифра є, але не там\n"
        text += "⬛ — такої цифри немає\n\n"
        text += "Перший хто вгадає — отримує наступне місце в черзі\n\n"

        if ranked_lines:
            text += "<b>Поточний порядок:</b>\n" + "\n".join(ranked_lines) + "\n\n"

    elif phase == "looting":
        remaining = game["remaining_loot"]
        text += f"Загальний скарб: <b>{TOTAL_LOOT} грн</b>\n"
        text += f"Залишок у сейфі: <b>{remaining} грн</b>\n\n"
        text += "<b>Черга (за результатами взлому):</b>\n"
        for i, uid in enumerate(game["ranking"], 1):
            name = game["participants"][uid]["name"]
            taken = game["participants"][uid].get("taken", 0)
            text += f"{i}. {name} — {taken} грн\n"

        if game["current_turn"] < len(game["ranking"]):
            current_uid = game["ranking"][game["current_turn"]]
            current_name = game["participants"][current_uid]["name"]
            text += f"\n<b>🔥 Зараз черга:</b> {current_name} (місце {game['current_turn'] + 1})\n"
            text += "Обери скільки грошей забрати ⬇️"
        else:
            text += "\n\nГра завершена — всі гроші розібрано!"

    return text


# =====================================
# СТВОРЕННЯ ГРИ
# =====================================
async def create_pograb(message: Message):
    chat_id = message.chat.id
    if chat_id in active_pograb:
        await message.answer("❌ У цьому чаті вже запущена гра «Пограбування банку»!")
        return

    keyboard = build_recruit_keyboard()
    text = get_status_text({"phase": "recruiting", "participants": {}})

    msg = await message.answer(text=text, reply_markup=keyboard, parse_mode="HTML")

    active_pograb[chat_id] = {
        "phase": "recruiting",
        "participants": {},
        "ranking": [],
        "current_round": 1,
        "secret": None,
        "status_msg_id": msg.message_id,
        "round_messages": [],
        "total_loot": TOTAL_LOOT,
        "remaining_loot": TOTAL_LOOT,
        "current_turn": 0,
    }


@router.message(Command("bank"))
async def cmd_bank(message: Message):
    if message.from_user.id != ADMIN_ID:
        try: await message.delete()
        except: pass
        return
    await create_pograb(message)


# =====================================
# СКАСУВАННЯ ГРИ
# =====================================
@router.callback_query(F.data == "pograb_cancel")
async def pograb_cancel(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Тільки адміністратор може скасувати гру!", show_alert=True)
        return

    chat_id = callback.message.chat.id
    if chat_id not in active_pograb:
        return

    game = active_pograb[chat_id]
    try:
        await callback.bot.delete_message(chat_id=chat_id, message_id=game["status_msg_id"])
    except:
        pass
    active_pograb.pop(chat_id, None)
    await callback.answer("Гра скасована!")
    await callback.message.answer("❌ Гра «Пограбування банку» скасована адміном.")


# =====================================
# ЗАПУСК ГРИ
# =====================================
@router.callback_query(F.data == "pograb_force_start")
async def pograb_force_start(callback: CallbackQuery):
    chat_id = callback.message.chat.id
    user_id = callback.from_user.id

    if user_id != ADMIN_ID:
        await callback.answer("Ця кнопка тільки для адміністратора", show_alert=True)
        return

    if chat_id not in active_pograb:
        await callback.answer("Гра вже неактивна", show_alert=True)
        return

    game = active_pograb[chat_id]

    game["phase"] = "guessing"
    game["current_round"] = 1
    game["ranking"] = []
    game["secret"] = f"{random.randint(0, 99):02d}"
    game["round_messages"] = []

    text = get_status_text(game)
    await callback.bot.edit_message_text(
        chat_id=chat_id, message_id=game["status_msg_id"],
        text=text, reply_markup=None, parse_mode="HTML"
    )

    await callback.message.answer_photo(
        photo=FSInputFile(IMAGE_GUESSING),
        caption=f"🛡️ <b>Раунд 1</b>\n"
                "Пишіть рівно 2 цифри в чат.\n",
        parse_mode="HTML"
    )

    await callback.answer("Гру запущено! Раунд 1 почався 🔥")


# =====================================
# ОБРОБКА ПОВІДОМЛЕНЬ
# =====================================
@router.message(F.text)
async def handle_pograb_message(message: Message):
    chat_id = message.chat.id
    user = message.from_user
    user_id = user.id
    text = message.text.strip()

    if chat_id not in active_pograb:
        return

    game = active_pograb[chat_id]
    phase = game["phase"]

    # --- ФАЗА ВГАДУВАННЯ ---
    if phase == "guessing":
        # Хто вже зайняв місце — мовчки видаляємо їх повідомлення
        if user_id in game["ranking"]:
            try: await message.delete()
            except: pass
            return

        # Не 2 цифри — мовчки видаляємо, не реагуємо
        if len(text) != CODE_LENGTH or not text.isdigit():
            try: await message.delete()
            except: pass
            return

        secret = game["secret"]
        game["round_messages"].append(message.message_id)

        feedback = get_feedback(text, secret)
        resp = await message.answer(
            f"{user.mention_html()} → <b>{text}</b>\n{feedback}",
            parse_mode="HTML"
        )
        game["round_messages"].append(resp.message_id)

        if text == secret:
            # Гравець стає учасником ТІЛЬКИ якщо вгадав код
            if user_id not in game["participants"]:
                game["participants"][user_id] = {"name": get_display_name(user), "taken": 0}
            game["ranking"].append(user_id)

            win_text = (
                f"🎉 <b>РАУНД {game['current_round']} ЗАВЕРШЕНО!</b>\n\n"
                f"{user.mention_html()} вгадав код <b>{secret}</b>!\n"
                f"Отримує місце №{len(game['ranking'])} в черзі!"
            )
            await message.answer(win_text, parse_mode="HTML")

            for msg_id in game["round_messages"]:
                try: await message.bot.delete_message(chat_id=chat_id, message_id=msg_id)
                except: pass
            game["round_messages"] = []

            if len(game["ranking"]) == MAX_ROUNDS:
                # Якщо є другий учасник — додаємо його автоматично останнім
                ranked_set = set(game["ranking"])
                last_uid = next((uid for uid in game["participants"] if uid not in ranked_set), None)
                if last_uid:
                    game["ranking"].append(last_uid)

                game["phase"] = "looting"
                game["current_turn"] = 0

                status_text = get_status_text(game)
                loot_keyboard = build_loot_keyboard(game["remaining_loot"])

                await message.answer_photo(
                    photo=FSInputFile(IMAGE_LOOTING),
                    caption="🏆 <b>ГРАБУЄМО!</b>\n"
                            "Переходимо до пограбування сейфів \n",
                    parse_mode="HTML"
                )

                new_status = await message.answer(
                    text=status_text,
                    reply_markup=loot_keyboard,
                    parse_mode="HTML"
                )
                game["status_msg_id"] = new_status.message_id

            else:
                game["current_round"] += 1
                game["secret"] = f"{random.randint(0, 99):02d}"

                status_text = get_status_text(game)
                await message.bot.edit_message_text(
                    chat_id=chat_id, message_id=game["status_msg_id"],
                    text=status_text, reply_markup=None, parse_mode="HTML"
                )

                await message.answer(
                    f"🛡️ <b>Раунд {game['current_round']}</b>\n"
                    "Пишіть рівно 2 цифри в чат.\n",
                    parse_mode="HTML"
                )

    # --- ФАЗА ПОГРАБУВАННЯ ---
    elif phase == "looting":
        # Видаляємо повідомлення тих, хто не є учасником
        if user_id not in game["participants"]:
            try: await message.delete()
            except: pass
            return

        if game["current_turn"] >= len(game["ranking"]):
            return
        current_uid = game["ranking"][game["current_turn"]]
        if user_id != current_uid:
            return
        try: await message.delete()
        except: pass


# =====================================
# ЗАБИРАННЯ ГРОШЕЙ
# =====================================
@router.callback_query(F.data.startswith("pograb_take_"))
async def pograb_take_money(callback: CallbackQuery):
    chat_id = callback.message.chat.id
    user = callback.from_user
    user_id = user.id

    if chat_id not in active_pograb:
        return
    game = active_pograb[chat_id]

    if game["phase"] != "looting" or game["current_turn"] >= len(game["ranking"]):
        await callback.answer("Гра вже завершена", show_alert=True)
        return

    current_uid = game["ranking"][game["current_turn"]]
    if user_id != current_uid:
        await callback.answer("Не твоя черга!", show_alert=True)
        return

    try:
        _, amount_str = callback.data.split("_take_")
        amount = int(amount_str)
    except:
        await callback.answer("Помилка", show_alert=True)
        return

    if amount < 1 or amount > game["remaining_loot"]:
        await callback.answer("Невірна сума!", show_alert=True)
        return

    game["remaining_loot"] -= amount
    game["participants"][user_id]["taken"] += amount

    name = game["participants"][user_id]["name"]
    await callback.message.answer(
        f"💰 <b>{name}</b> забрав <b>{amount} грн</b> з сейфу!\n"
        f"Залишок у банку: <b>{game['remaining_loot']} грн</b>",
        parse_mode="HTML"
    )

    game["current_turn"] += 1

    status_text = get_status_text(game)
    new_keyboard = build_loot_keyboard(game["remaining_loot"]) if game["current_turn"] < len(game["ranking"]) else None

    new_status = await callback.message.answer(
        text=status_text,
        reply_markup=new_keyboard,
        parse_mode="HTML"
    )

    try:
        await callback.bot.delete_message(chat_id=chat_id, message_id=game["status_msg_id"])
    except:
        pass
    game["status_msg_id"] = new_status.message_id

    if game["remaining_loot"] <= 0 or game["current_turn"] >= len(game["ranking"]):
        await callback.message.answer(
            "🏁 <b>ПОГРАБУВАННЯ ЗАВЕРШЕНО!</b>\n"
            "Всі гроші розібрано\n"
            "Дякуємо за гру! 💸",
            parse_mode="HTML"
        )
        active_pograb.pop(chat_id, None)

    await callback.answer(f"✅ Забрав {amount} грн!")