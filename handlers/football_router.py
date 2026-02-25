
# from aiogram import Router, F
# from aiogram.filters import Command
# from aiogram.types import Message, ContentType
# import logging
# import random
# import string

# from config import ADMIN_ID
# from db import add_promocode   # ← імпорт для видачі промокоду

# router = Router(name="group_football")

# # Працюємо тільки в групах
# router.message.filter(F.chat.type.in_({"group", "supergroup"}))

# # chat_id → {user_id: кількість голів}
# active_football_games = {}


# def generate_promocode(length: int = 8) -> str:
#     """Генерація промокоду (використовуємо ту саму логіку, що і в main.py)"""
#     characters = string.ascii_uppercase + string.digits
#     return "".join(random.choices(characters, k=length))


# # ==========================
# # ЗАПУСК ГРИ (тільки адмін)
# # ==========================
# @router.message(Command("football"))
# async def start_football(message: Message):
#     if message.from_user.id != ADMIN_ID:
#         try:
#             await message.delete()
#         except:
#             pass
#         return

#     chat_id = message.chat.id
#     active_football_games[chat_id] = {}

#     logging.info(f"⚽ ФУТБОЛ ЗАПУЩЕНО в чаті {chat_id}")

#     await message.answer(
#         "⚽ <b>ФУТБОЛ СТАРТУВАВ!</b> 🏆\n\n"
#         "Кидайте ⚽ в чат!\n"
#         "Перший, хто заб'є <b>4 голи</b> — отримує 🎟️ PROMO!"
#     )

#     await message.bot.send_dice(chat_id=chat_id, emoji="⚽")


# # ==========================
# # ОБРОБКА КИДКІВ ⚽
# # ==========================
# @router.message(F.content_type == ContentType.DICE, F.dice.emoji == "⚽")
# async def handle_football_dice(message: Message):
#     chat_id = message.chat.id
#     user = message.from_user
#     user_id = user.id

#     if chat_id not in active_football_games:
#         try:
#             await message.delete()
#         except:
#             pass
#         return

#     game = active_football_games[chat_id]

#     if user_id not in game:
#         game[user_id] = 0

#     score = message.dice.value

#     if score >= 3:          # 3, 4, 5 = гол
#         game[user_id] += 1
#         goals = game[user_id]

#         if goals >= 4:      # 4 голи = ПЕРЕМОГА + ПРИЗ
#             del active_football_games[chat_id]

#             # === АВТОВИДАЧА ПРИЗУ ===
#             promo = generate_promocode()
#             await add_promocode(promo)

#             # Відправляємо промокод в ЛС переможцю
#             try:
#                 await message.bot.send_message(
#                     chat_id=user_id,
#                     text=(
#                         f"🎉 <b>Вітаємо з перемогою в Футболі!</b>\n\n"
#                         f"Твій приз:\n"
#                         f"<code>{promo}</code>\n\n"
#                         f"Використовуй його в боті 👇\n"
#                         f"Натисни кнопку «Ввести промокод»"
#                     ),
#                     parse_mode="HTML"
#                 )
#             except Exception:
#                 logging.warning(f"Не вдалося надіслати промокод гравцю {user_id} (ЛС закритий)")

#             # Повідомлення в групі
#             await message.answer(
#                 f"🎉 <b>ПЕРЕМОЖЕЦЬ!</b> 🏆\n\n"
#                 f"{user.mention_html()} забив <b>4 голи</b>!\n"
#                 f"Приз (промокод) надіслано в особисті повідомлення 🎁",
#                 parse_mode="HTML"
#             )
#             return

#         # Прогрес в групі
#         await message.answer(
#             f"⚽ {user.mention_html()} — <b>{goals}/4 голів</b>",
#             parse_mode="HTML"
#         )


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

    logging.info(f"⚽ ФУТБОЛ ЗАПУЩЕНО в чаті {chat_id}")

    await message.answer(
        "⚽ <b>ФУТБОЛ СТАРТУВАВ!</b> 🏆\n\n"
        "Кидайте ⚽ в чат!\n"
        "Перший, хто заб'є <b>4 голи</b> — отримує промокод!\n"
        "⚠️ Після перемоги — 1 година кулдауну ⚠️"
    )

    await message.bot.send_dice(chat_id=chat_id, emoji="⚽")


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

    game = active_football_games[chat_id]

    if user_id not in game:
        game[user_id] = 0

    score = message.dice.value

    if score >= 3:          # 3, 4, 5 = гол
        game[user_id] += 1
        goals = game[user_id]

        if goals >= 4:      # 4 голи = перемога
            # === ПЕРЕВІРКА КУЛДАУНУ ===
            if user_id in winner_cooldown:
                time_passed = datetime.now() - winner_cooldown[user_id]
                if time_passed < timedelta(hours=1):
                    minutes_left = 60 - int(time_passed.total_seconds() // 60)
                    await message.answer(
                        f"⏳ {user.mention_html()}, ти вже виграв!\n"
                        f"Наступна перемога доступна через <b>{minutes_left} хв</b>",
                        parse_mode="HTML"
                    )
                    return  # не даємо перемогу вдруге

            # === АВТОВИДАЧА ПРИЗУ ===
            promo = generate_promocode()
            await add_promocode(promo)

            # Записуємо час перемоги
            winner_cooldown[user_id] = datetime.now()

            # Відправляємо промокод в ЛС
            try:
                await message.bot.send_message(
                    chat_id=user_id,
                    text=(
                        f"🎉 <b>Вітаємо з перемогою в Футболі!</b>\n\n"
                        f"Твій приз:\n"
                        f"<code>{promo}</code>\n\n"
                        f"Використовуй його в боті 👇"
                    ),
                    parse_mode="HTML"
                )
            except:
                logging.warning(f"Не вдалося надіслати промокод гравцю {user_id}")

            # Повідомлення в групі
            await message.answer(
                f"🎉 <b>ПЕРЕМОЖЕЦЬ!</b> 🏆\n\n"
                f"{user.mention_html()} забив <b>4 голи</b>!\n"
                f"Приз надіслано в особисті повідомлення 🎁\n"
                f"Наступна перемога — через 1 годину",
                parse_mode="HTML"
            )

            del active_football_games[chat_id]
            return

        # Прогрес
        await message.answer(
            f"⚽ {user.mention_html()} — <b>{goals}/4 голів</b>",
            parse_mode="HTML"
        )