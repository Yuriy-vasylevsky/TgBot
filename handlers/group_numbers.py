from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
import logging
import random

from config import ADMIN_ID

router = Router(name="group_numbers")
router.message.filter(F.chat.type.in_({"group", "supergroup"}))

active_numbers_games = {}


@router.message(Command("numbers"))
async def start_numbers(message: Message):
    if message.from_user.id != ADMIN_ID:
        try: await message.delete()
        except: pass
        return

    chat_id = message.chat.id
    secret = f"{random.randint(0, 99999):05d}"

    active_numbers_games[chat_id] = {"secret": secret, "revealed": ["❓"] * 5}

    logging.info(f"🔢 NUMBERS ЗАПУЩЕНО | Число: {secret}")

    await message.answer(
        "🔑<b>Secret code</b>🔑\n\n"
        "Я загадав 5-значне число.\nПиши рівно 5 цифр!\n\n"
        "🟩 — на місці\n🟨 — є, але не там\n⬛ — немає\n\n"
        "Хто перший вгадає — переможець! 🏆",
        parse_mode="HTML"
    )


def get_feedback(guess: str, secret: str) -> str:
    result = ['⬛'] * 5
    secret_list = list(secret)
    for i in range(5):
        if guess[i] == secret_list[i]:
            result[i] = '🟩'
            secret_list[i] = None
    for i in range(5):
        if result[i] == '⬛' and guess[i] in secret_list:
            result[i] = '🟨'
            secret_list[secret_list.index(guess[i])] = None
    return ''.join(result)


# ЄДИНИЙ обробник для всіх текстових повідомлень у цій грі
@router.message(
    F.text,
    lambda m: m.chat.id in active_numbers_games   # ← найважливіший фільтр
)
async def handle_numbers(message: Message):
    chat_id = message.chat.id
    user = message.from_user
    text = message.text.strip()

    if len(text) != 5 or not text.isdigit():
        await message.answer(
            f"❌ {user.mention_html()}, треба **рівно 5 цифр**!",
            parse_mode="HTML"
        )
        return

    game = active_numbers_games[chat_id]
    secret = game["secret"]
    revealed = game["revealed"]

    feedback = get_feedback(text, secret)

    for i in range(5):
        if feedback[i] == '🟩' and revealed[i] == "❓":
            revealed[i] = text[i]

    if text == secret:
        del active_numbers_games[chat_id]
        await message.answer(
            f"🎉 <b>ПЕРЕМОЖЕЦЬ!</b> 🏆\n\n"
            f"{user.mention_html()} вгадав число!\n"
            f"Загадане: <b>{secret}</b>",
            parse_mode="HTML"
        )
        return

    await message.answer(
        f"{user.mention_html()} → <b>{text}</b>\n"
        f"{' '.join(feedback)}\n"
        f"{' '.join(revealed)}",
        parse_mode="HTML"
    )