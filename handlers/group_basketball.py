from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, ContentType
import logging
from datetime import datetime, timedelta

from config import ADMIN_ID

router = Router(name="group_basketball")

# Працюємо тільки в групах
router.message.filter(F.chat.type.in_({"group", "supergroup"}))

# chat_id → {user_id: кількість влучань}
active_basketball_games = {}

# Коoldown: user_id → час останньої перемоги
basketball_winner_cooldown = {}


# ==========================
# ЗАПУСК ГРИ (тільки адмін)
# ==========================
@router.message(Command("basketball"))
async def start_basketball(message: Message):
    if message.from_user.id != ADMIN_ID:
        try:
            await message.delete()
        except:
            pass
        return

    chat_id = message.chat.id
    active_basketball_games[chat_id] = {}

    logging.info(f"🏀 БАСКЕТБОЛ ЗАПУЩЕНО в чаті {chat_id}")

    await message.answer(
        "🏀 <b>БАСКЕТБОЛ СТАРТУВАВ!</b> 🏀\n\n"
        "Кидайте 🏀 в чат!\n\n"
        "🏆Перший, хто влучить <b>4 рази</b> — отримує 50 грн!\n"
        "❗ Лише для гравців хто робив депозит протягом 24 годин\n",
        parse_mode="HTML"
    )

    await message.bot.send_dice(chat_id=chat_id, emoji="🏀")


# ==========================
# ОБРОБКА КИДКІВ 🏀
# ==========================
@router.message(F.content_type == ContentType.DICE, F.dice.emoji == "🏀")
async def handle_basketball_dice(message: Message):
    chat_id = message.chat.id
    user = message.from_user
    user_id = user.id

    # Якщо гра не активна — видаляємо кидок
    if chat_id not in active_basketball_games:
        try:
            await message.delete()
        except:
            pass
        return

    game = active_basketball_games[chat_id]

    if user_id not in game:
        game[user_id] = 0

    score = message.dice.value

    if score >= 4:          # 4 і 5 = влучний кидок
        game[user_id] += 1
        hits = game[user_id]

        if hits >= 4:       # ← ЗМІНЕНО НА 4
            # === ПЕРЕВІРКА КУЛДАУНУ ===
            if user_id in basketball_winner_cooldown:
                time_passed = datetime.now() - basketball_winner_cooldown[user_id]
                if time_passed < timedelta(hours=12):
                    minutes_left = 720 - int(time_passed.total_seconds() // 60)
                    hours_left = minutes_left // 60
                    mins_left = minutes_left % 60
                    await message.answer(
                        f"{user.mention_html()}, дай шанс іншим гравцям\n"
                        f"⏳ <b>{hours_left} год {mins_left} хв</b>⏳",
                        parse_mode="HTML"
                    )
                    return  # не даємо перемогу вдруге

            # === ФІКСАЦІЯ ПЕРЕМОГИ ===
            basketball_winner_cooldown[user_id] = datetime.now()
            del active_basketball_games[chat_id]

            await message.answer(
                f"🎉 <b>ПЕРЕМОЖЕЦЬ!</b> 🏆\n\n"
                f"{user.mention_html()} влучив <b>4 рази</b> в кошик!\n"
                f"Вітаємо! Ви виграли 50 грн 🎁\n",
                # f"Наступна перемога — через 12 годин",
                parse_mode="HTML"
            )
            return

        # Прогрес
        await message.answer(
            f"🏀 {user.mention_html()} — <b>{hits}/4 влучних кидків</b>",
            parse_mode="HTML"
        )

    # Промах (1-3) — мовчимо