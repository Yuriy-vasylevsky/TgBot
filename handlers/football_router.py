from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, ContentType
import logging
import random
import string
from datetime import datetime, timedelta

from config import ADMIN_ID
from db import add_promocode

router = Router(name="group_football")

# Працюємо тільки в групах
router.message.filter(F.chat.type.in_({"group", "supergroup"}))

# chat_id → {user_id: кількість голів}
active_football_games = {}

# chat_id → список message_id, які можна видалити після закінчення гри
football_messages = {}

# Коoldown: user_id → час останньої перемоги
winner_cooldown = {}


def generate_promocode(length: int = 8) -> str:
    characters = string.ascii_uppercase + string.digits
    return "".join(random.choices(characters, k=length))


# ==========================
# ЗАПУСК ГРИ (тільки адмін)
# ==========================
@router.message(Command("football"))
async def start_football(message: Message):
    if message.from_user.id != ADMIN_ID:
        try:
            await message.delete()
        except:
            pass
        return

    chat_id = message.chat.id

    active_football_games[chat_id] = {}
    football_messages[chat_id] = []

    logging.info(f"⚽ ФУТБОЛ ЗАПУЩЕНО в чаті {chat_id}")

    start_msg = await message.answer(
        "⚽ <b>ФУТБОЛ СТАРТУВАВ!</b> ⚽\n\n"
        "🏆 Приз —  🎟️ промокод!\n\n",

        parse_mode="HTML"
    )
    football_messages[chat_id].append(start_msg.message_id)  # 0 — стартове, захищене

    # Перший кидок від бота
    dice_msg = await message.bot.send_dice(chat_id=chat_id, emoji="⚽")
    football_messages[chat_id].append(dice_msg.message_id)

    # Видаляємо команду /football
    try:
        await message.delete()
    except:
        pass


# ==========================
# ОБРОБКА КИДКІВ ⚽
# ==========================
@router.message(F.content_type == ContentType.DICE, F.dice.emoji == "⚽")
async def handle_football_dice(message: Message):
    chat_id = message.chat.id
    user = message.from_user
    user_id = user.id

    if chat_id not in active_football_games:
        try:
            await message.delete()
        except:
            pass
        return

    football_messages.setdefault(chat_id, []).append(message.message_id)

    game = active_football_games[chat_id]

    if user_id not in game:
        game[user_id] = 0

    score = message.dice.value

    if score < 3:
        return

    game[user_id] += 1
    goals = game[user_id]

    if goals >= 5:
        # Кулдаун
        if user_id in winner_cooldown:
            time_passed = datetime.now() - winner_cooldown[user_id]
            if time_passed < timedelta(hours=12):
                minutes_left = 720 - int(time_passed.total_seconds() // 60)
                hours_left = minutes_left // 60
                mins_left = minutes_left % 60
                cd_msg = await message.answer(
                    f"{user.mention_html()}, ти вже виграв!\n"
                    f"⏳ <b>{hours_left} год {mins_left} хв</b> ⏳",
                    parse_mode="HTML"
                )
                football_messages[chat_id].append(cd_msg.message_id)
                return

        # Промокод
        promo = generate_promocode()
        await add_promocode(promo)
        winner_cooldown[user_id] = datetime.now()

        # Надсилання в приват + fallback
        sent_to_private = False
        try:
            await message.bot.send_message(
                chat_id=user_id,
                text=(
                    f"🎉 <b>Вітаємо з перемогою в Футболі!</b>\n\n"
                    f"Твій приз:\n"
                    f"<code>{promo}</code>\n\n"
                    "Використовуй його в боті 👇\n"
             
                ),
                parse_mode="HTML"
            )
            sent_to_private = True
        except Exception as e:
            logging.warning(f"Не вдалося надіслати промокод гравцю {user_id}: {e}")

        # Повідомлення про перемогу
        if sent_to_private:
            win_text = (
                f"🎉 <b>ПЕРЕМОЖЕЦЬ!</b> 🏆\n\n"
                f"{user.mention_html()} забив <b>5 голів</b>!\n\n"
                f"⚽ ⚽ ⚽ ⚽ ⚽"
            )
        else:
            win_text = (
                f"🎉 <b>ПЕРЕМОЖЕЦЬ!</b> 🏆\n\n"
                f"{user.mention_html()} забив <b>5 голів</b>!\n\n"
                f"Вам потрібно активувати бота\n\n"
     
            )

        win_message = await message.answer(win_text, parse_mode="HTML")
        football_messages[chat_id].append(win_message.message_id)  # додаємо для захисту

        # Очищення: залишаємо ТІЛЬКИ стартове + повідомлення про перемогу
        if chat_id in football_messages:
            protected = [
                football_messages[chat_id][0],           # стартове
                win_message.message_id                   # перемога
            ]

            for msg_id in football_messages[chat_id]:
                if msg_id in protected:
                    continue
                try:
                    await message.bot.delete_message(chat_id=chat_id, message_id=msg_id)
                except:
                    pass

            # Оновлюємо список — тільки захищені
            football_messages[chat_id] = protected

        # Завершуємо гру
        if chat_id in active_football_games:
            del active_football_games[chat_id]

        return

    # Прогрес
    progress_msg = await message.answer(
        f"⚽ {user.mention_html()} — <b>{goals}/5 голів</b>",
        parse_mode="HTML"
    )
    football_messages[chat_id].append(progress_msg.message_id)