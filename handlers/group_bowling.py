
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, ContentType
import logging
from datetime import datetime, timedelta

from config import ADMIN_ID

router = Router(name="group_bowling")

# Працюємо тільки в групах
router.message.filter(F.chat.type.in_({"group", "supergroup"}))

# chat_id → {user_id: кількість_страйків}
active_bowling_games = {}

# Коoldown: user_id → час останньої перемоги
bowling_winner_cooldown = {}


# ==========================
# ЗАПУСК ГРИ (тільки адмін)
# ==========================
@router.message(Command("bowling"))
async def start_bowling(message: Message):
    if message.from_user.id != ADMIN_ID:
        try:
            await message.delete()
        except:
            pass
        return

    chat_id = message.chat.id
    active_bowling_games[chat_id] = {}   # скидаємо гру

    logging.info(f"🎳 БОУЛІНГ ЗАПУЩЕНО в чаті {chat_id}")

    await message.answer(
        "🎳 <b>БОУЛІНГ СТАРТУВАВ!</b> 🎳\n\n"
        "Кидайте 🎳 в чат!\n\n"
        "🏆<b>Перший, хто виб’є ДВА СТРАЙКИ</b> — отримає 50 грн!\n"
        "❗ Лише для гравців хто робив депозит протягом 24 годин\n",
        parse_mode="HTML"
    )

    # Бот кидає свій боулінг
    await message.bot.send_dice(chat_id=chat_id, emoji="🎳")


# ==========================
# ОБРОБКА КИДКІВ 🎳
# ==========================
@router.message(F.content_type == ContentType.DICE, F.dice.emoji == "🎳")
async def handle_bowling_dice(message: Message):
    chat_id = message.chat.id
    user = message.from_user
    user_id = user.id

    # Якщо гра не активна — видаляємо кидок (антиспам)
    if chat_id not in active_bowling_games:
        try:
            await message.delete()
        except:
            pass
        return

    game = active_bowling_games[chat_id]

    # Ініціалізуємо гравця, якщо ще немає
    if user_id not in game:
        game[user_id] = 0

    score = message.dice.value

    if score == 6:
        game[user_id] += 1
        strikes = game[user_id]

        if strikes >= 2:  # ДВА СТРАЙКИ = ПЕРЕМОГА!
            # === ПЕРЕВІРКА КУЛДАУНУ ===
            if user_id in bowling_winner_cooldown:
                time_passed = datetime.now() - bowling_winner_cooldown[user_id]
                if time_passed < timedelta(hours=12):
                    minutes_left = 720 - int(time_passed.total_seconds() // 60)
                    hours_left = minutes_left // 60
                    mins_left = minutes_left % 60
                    await message.answer(
                        f"⏳ {user.mention_html()}, ти вже виграв в боулінг!\n"
                        f"Наступна перемога доступна через <b>{hours_left} год {mins_left} хв</b>",
                        parse_mode="HTML"
                    )
                    return  # не даємо перемогу вдруге

            # === ФІКСАЦІЯ ПЕРЕМОГИ ===
            bowling_winner_cooldown[user_id] = datetime.now()
            del active_bowling_games[chat_id]   # завершуємо гру

            await message.answer(
                f"🎉 <b>ПЕРЕМОЖЕЦЬ!</b> 🏆\n\n"
                f"{user.mention_html()} вибив <b>ДВА СТРАЙКИ</b>!\n"
                f"Вітаємо! Вивиграли 50 грн 🎁\n",
                parse_mode="HTML"
            )
            return

        # Показуємо поточний прогрес
        await message.answer(
            f"🔥 {user.mention_html()} — <b>{strikes}/2 страйків</b>",
            parse_mode="HTML"
        )

    # Якщо не 6 — нічого не пишемо, щоб не засмічувати чат