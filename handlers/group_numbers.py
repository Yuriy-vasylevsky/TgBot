# from aiogram import Router, F
# from aiogram.filters import Command
# from aiogram.types import Message
# import logging
# import random

# from config import ADMIN_ID

# router = Router(name="group_numbers")
# router.message.filter(F.chat.type.in_({"group", "supergroup"}))

# active_numbers_games = {}


# @router.message(Command("numbers"))
# async def start_numbers(message: Message):
#     if message.from_user.id != ADMIN_ID:
#         try: await message.delete()
#         except: pass
#         return

#     chat_id = message.chat.id
#     secret = f"{random.randint(0, 99999):05d}"

#     active_numbers_games[chat_id] = {"secret": secret, "revealed": ["❓"] * 5}

#     logging.info(f"🔢 NUMBERS ЗАПУЩЕНО | Число: {secret}")

#     await message.answer(
#         "🔑<b>Secret code</b>🔑\n\n"
#         "Я загадав 5-значне число.\nПиши рівно 5 цифр!\n\n"
#         "🟩 — на місці\n🟨 — є, але не там\n⬛ — немає\n\n"
#         "Хто перший вгадає — переможець! 🏆",
#         parse_mode="HTML"
#     )


# def get_feedback(guess: str, secret: str) -> str:
#     result = ['⬛'] * 5
#     secret_list = list(secret)
#     for i in range(5):
#         if guess[i] == secret_list[i]:
#             result[i] = '🟩'
#             secret_list[i] = None
#     for i in range(5):
#         if result[i] == '⬛' and guess[i] in secret_list:
#             result[i] = '🟨'
#             secret_list[secret_list.index(guess[i])] = None
#     return ''.join(result)


# # ЄДИНИЙ обробник для всіх текстових повідомлень у цій грі
# @router.message(
#     F.text,
#     lambda m: m.chat.id in active_numbers_games   # ← найважливіший фільтр
# )
# async def handle_numbers(message: Message):
#     chat_id = message.chat.id
#     user = message.from_user
#     text = message.text.strip()

#     if len(text) != 5 or not text.isdigit():
#         await message.answer(
#             f"❌ {user.mention_html()}, треба **рівно 5 цифр**!",
#             parse_mode="HTML"
#         )
#         return

#     game = active_numbers_games[chat_id]
#     secret = game["secret"]
#     revealed = game["revealed"]

#     feedback = get_feedback(text, secret)

#     for i in range(5):
#         if feedback[i] == '🟩' and revealed[i] == "❓":
#             revealed[i] = text[i]

#     if text == secret:
#         del active_numbers_games[chat_id]
#         await message.answer(
#             f"🎉 <b>ПЕРЕМОЖЕЦЬ!</b> 🏆\n\n"
#             f"{user.mention_html()} вгадав число!\n"
#             f"Загадане: <b>{secret}</b>",
#             parse_mode="HTML"
#         )
#         return

#     await message.answer(
#         f"{user.mention_html()} → <b>{text}</b>\n"
#         f"{' '.join(feedback)}\n"
#         f"{' '.join(revealed)}",
#         parse_mode="HTML"
#     )

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
import logging
import random

from config import ADMIN_ID

router = Router(name="group_numbers")

router.message.filter(F.chat.type.in_({"group", "supergroup"}))

# chat_id → {"secret": str, "revealed": list[str], "messages": list[int]}
active_numbers_games = {}


@router.message(Command("numbers"))
async def start_numbers(message: Message):
    if message.from_user.id != ADMIN_ID:
        try:
            await message.delete()
        except:
            pass
        return

    chat_id = message.chat.id
    secret = f"{random.randint(0, 99999):05d}"

    active_numbers_games[chat_id] = {
        "secret": secret,
        "revealed": ["❓"] * 5,
        "messages": []
    }

    logging.info(f"🔢 NUMBERS ЗАПУЩЕНО в {chat_id} | Число: {secret}")

    start_msg = await message.answer(
        "🔑 <b>SECRET CODE</b> 🔑\n\n"
        "Я загадав 5-значне число (від 00000 до 99999).\n"
        "Пишіть рівно 5 цифр у чат!\n\n"
        "🟩 — цифра на правильному місці\n"
        "🟨 — цифра є, але не там\n"
        "⬛ — такої цифри немає\n\n"
        "<b>Перший, хто вгадає — переможець!</b> 🏆\n"
        "Після перемоги чат буде очищено (залишиться тільки старт + перемога).",
        parse_mode="HTML"
    )

    # Зберігаємо ID стартового повідомлення — його не видаляти
    active_numbers_games[chat_id]["messages"].append(start_msg.message_id)

    # Видаляємо команду /numbers
    try:
        await message.delete()
    except:
        pass


def get_feedback(guess: str, secret: str) -> str:
    result = ['⬛'] * 5
    secret_list = list(secret)

    # Спочатку точні збіги (зелені)
    for i in range(5):
        if guess[i] == secret_list[i]:
            result[i] = '🟩'
            secret_list[i] = None  # позначаємо як використану

    # Потім неточні збіги (жовті)
    for i in range(5):
        if result[i] == '⬛' and guess[i] in secret_list:
            result[i] = '🟨'
            secret_list[secret_list.index(guess[i])] = None

    return ''.join(result)


@router.message(
    F.text,
    lambda m: m.chat.id in active_numbers_games
)
async def handle_numbers(message: Message):
    chat_id = message.chat.id
    user = message.from_user
    text = message.text.strip()

    if chat_id not in active_numbers_games:
        return

    game = active_numbers_games[chat_id]
    secret = game["secret"]
    revealed = game["revealed"]
    messages = game["messages"]

    # Зберігаємо повідомлення гравця
    messages.append(message.message_id)

    if len(text) != 5 or not text.isdigit():
        err_msg = await message.answer(
            f"❌ {user.mention_html()}, потрібно **рівно 5 цифр** (00000–99999)",
            parse_mode="HTML"
        )
        messages.append(err_msg.message_id)
        return

    feedback = get_feedback(text, secret)

    # Оновлюємо відкриті цифри
    for i in range(5):
        if feedback[i] == '🟩' and revealed[i] == "❓":
            revealed[i] = text[i]

    # Зберігаємо відповідь бота
    resp_msg = await message.answer(
        f"{user.mention_html()} → <b>{text}</b>\n"
        f"{' '.join(feedback)}\n"
        f"{' '.join(revealed)}",
        parse_mode="HTML"
    )
    messages.append(resp_msg.message_id)

    # Перемога
    if text == secret:
        win_msg = await message.answer(
            f"🎉 <b>ПЕРЕМОЖЕЦЬ!</b> 🏆\n\n"
            f"{user.mention_html()} вгадав число!\n"
            f"Загадане: <b>{secret}</b>\n\n"
            "Гра завершена. Дякую за участь!",
            parse_mode="HTML"
        )
        messages.append(win_msg.message_id)

        # Захищені повідомлення: стартове + перемога
        protected = [messages[0], win_msg.message_id]

        # Видаляємо все інше
        for msg_id in messages:
            if msg_id in protected:
                continue
            try:
                await message.bot.delete_message(chat_id=chat_id, message_id=msg_id)
            except:
                pass  # вже видалено / немає прав / бот заблокований тощо

        # Оновлюємо список (залишаємо тільки захищені)
        active_numbers_games[chat_id]["messages"] = protected

        # Завершуємо гру
        del active_numbers_games[chat_id]
        return


# Опціонально — примусове завершення для адміна
@router.message(Command("numbers_stop"))
async def stop_numbers(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    chat_id = message.chat.id
    if chat_id not in active_numbers_games:
        await message.answer("Активної гри «Secret Code» в цьому чаті немає.")
        return

    messages = active_numbers_games[chat_id].get("messages", [])
    if messages:
        protected = [messages[0]]  # тільки стартове
        for msg_id in messages:
            if msg_id in protected:
                continue
            try:
                await message.bot.delete_message(chat_id=chat_id, message_id=msg_id)
            except:
                pass

    del active_numbers_games[chat_id]
    await message.answer("Гра «Secret Code» примусово завершена та очищена.")
    try:
        await message.delete()
    except:
        pass