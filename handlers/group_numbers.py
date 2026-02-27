from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
import logging
import random

from config import ADMIN_ID

router = Router(name="group_numbers")

# Працюємо тільки в групах
router.message.filter(F.chat.type.in_({"group", "supergroup"}))

# chat_id → {"secret": "1234", "revealed": ["❓", "❓", "❓", "❓"]}
active_numbers_games = {}


# ==========================
# ЗАПУСК ГРИ
# ==========================
@router.message(Command("numbers"))
async def start_numbers(message: Message):
    if message.from_user.id != ADMIN_ID:
        try:
            await message.delete()
        except:
            pass
        return

    chat_id = message.chat.id
    secret = f"{random.randint(0, 9999):04d}"

    active_numbers_games[chat_id] = {
        "secret": secret,
        "revealed": ["❓"] * 4
    }

    logging.info(f"🔢 ЦИФРИ ЗАПУЩЕНО в чаті {chat_id} | Число: {secret}")

    await message.answer(
        "🔢 <b>ЦИФРИ СТАРТУВАЛИ!</b> 🎯\n\n"
        "Я загадав 4-значне число (від 0000 до 9999).\n"
        "Просто пишіть 4 цифри в чат!\n\n"
        "🟩 — цифра на правильному місці\n"
        "🟨 — цифра є, але не там\n"
        "⬛ — такої цифри немає\n\n"
        "Правильно вгадані цифри **зберігаються** назавжди!\n\n"
        "Перший, хто вгадає число — переможець! 🏆",
        parse_mode="HTML"
    )


def get_feedback(guess: str, secret: str) -> str:
    result = ['⬛'] * 4
    secret_list = list(secret)

    # Точні збіги (зелені)
    for i in range(4):
        if guess[i] == secret_list[i]:
            result[i] = '🟩'
            secret_list[i] = None

    # Жовті (є, але не там)
    for i in range(4):
        if result[i] == '⬛' and guess[i] in secret_list:
            result[i] = '🟨'
            secret_list[secret_list.index(guess[i])] = None

    return ''.join(result)


# ==========================
# ОБРОБКА ВІДГАДОК
# ==========================
@router.message(
    F.text,
    lambda m: len(m.text.strip()) == 4 and m.text.strip().isdigit()
)
async def handle_numbers_guess(message: Message):
    chat_id = message.chat.id
    user = message.from_user
    guess = message.text.strip()

    if chat_id not in active_numbers_games:
        return

    game = active_numbers_games[chat_id]
    secret = game["secret"]
    revealed = game["revealed"]          # накопичувана підказка

    feedback = get_feedback(guess, secret)

    # Оновлюємо накопичену підказку (фіксуємо правильно вгадані цифри)
    for i in range(4):
        if feedback[i] == '🟩' and revealed[i] == "❓":
            revealed[i] = guess[i]

    if guess == secret:  # ПЕРЕМОГА!
        del active_numbers_games[chat_id]

        await message.answer(
            f"🎉 <b>ПЕРЕМОЖЕЦЬ!</b> 🏆\n\n"
            f"{user.mention_html()} вгадав число!\n"
            f"Загадане число: <b>{secret}</b>\n\n"
            f"Вітаємо! Ви виграли 🎁",
            parse_mode="HTML"
        )
        return

    # Симетричний вивід
    feedback_spaced = ' '.join(feedback)
    current_revealed = ' '.join(revealed)

    await message.answer(
        f"{user.mention_html()} → <b>{guess}</b>\n"
        f"{feedback_spaced}\n"
        f"{current_revealed}",
        parse_mode="HTML"
    )