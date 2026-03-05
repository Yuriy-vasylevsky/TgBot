
# from aiogram import Router, F
# from aiogram.filters import Command
# from aiogram.types import Message, ContentType
# import logging
# from datetime import datetime, timedelta

# from config import ADMIN_ID

# router = Router(name="group_bowling")

# # Працюємо тільки в групах
# router.message.filter(F.chat.type.in_({"group", "supergroup"}))

# # chat_id → {user_id: кількість_страйків}
# active_bowling_games = {}

# # Коoldown: user_id → час останньої перемоги
# bowling_winner_cooldown = {}


# # ==========================
# # ЗАПУСК ГРИ (тільки адмін)
# # ==========================
# @router.message(Command("bowling"))
# async def start_bowling(message: Message):
#     if message.from_user.id != ADMIN_ID:
#         try:
#             await message.delete()
#         except:
#             pass
#         return

#     chat_id = message.chat.id
#     active_bowling_games[chat_id] = {}   # скидаємо гру

#     logging.info(f"🎳 БОУЛІНГ ЗАПУЩЕНО в чаті {chat_id}")

#     await message.answer(
#         "🎳 <b>БОУЛІНГ СТАРТУВАВ!</b> 🎳\n\n"
#         "Кидайте 🎳 в чат!\n\n"
#         "🏆<b>Перший, хто виб’є ДВА СТРАЙКИ</b> — отримає 50 грн!\n"
#         "❗ Лише для гравців хто робив депозит протягом 24 годин\n",
#         parse_mode="HTML"
#     )

#     # Бот кидає свій боулінг
#     await message.bot.send_dice(chat_id=chat_id, emoji="🎳")


# # ==========================
# # ОБРОБКА КИДКІВ 🎳
# # ==========================
# @router.message(F.content_type == ContentType.DICE, F.dice.emoji == "🎳")
# async def handle_bowling_dice(message: Message):
#     chat_id = message.chat.id
#     user = message.from_user
#     user_id = user.id

#     # Якщо гра не активна — видаляємо кидок (антиспам)
#     if chat_id not in active_bowling_games:
#         try:
#             await message.delete()
#         except:
#             pass
#         return

#     game = active_bowling_games[chat_id]

#     # Ініціалізуємо гравця, якщо ще немає
#     if user_id not in game:
#         game[user_id] = 0

#     score = message.dice.value

#     if score == 6:
#         game[user_id] += 1
#         strikes = game[user_id]

#         if strikes >= 2:  # ДВА СТРАЙКИ = ПЕРЕМОГА!
#             # === ПЕРЕВІРКА КУЛДАУНУ ===
#             if user_id in bowling_winner_cooldown:
#                 time_passed = datetime.now() - bowling_winner_cooldown[user_id]
#                 if time_passed < timedelta(hours=12):
#                     minutes_left = 720 - int(time_passed.total_seconds() // 60)
#                     hours_left = minutes_left // 60
#                     mins_left = minutes_left % 60
#                     await message.answer(
#                         f"⏳ {user.mention_html()}, ти вже виграв в боулінг!\n"
#                         f"Наступна перемога доступна через <b>{hours_left} год {mins_left} хв</b>",
#                         parse_mode="HTML"
#                     )
#                     return  # не даємо перемогу вдруге

#             # === ФІКСАЦІЯ ПЕРЕМОГИ ===
#             bowling_winner_cooldown[user_id] = datetime.now()
#             del active_bowling_games[chat_id]   # завершуємо гру

#             await message.answer(
#                 f"🎉 <b>ПЕРЕМОЖЕЦЬ!</b> 🏆\n\n"
#                 f"{user.mention_html()} вибив <b>ДВА СТРАЙКИ</b>!\n"
#                 f"Вітаємо! Вивиграли 50 грн 🎁\n",
#                 parse_mode="HTML"
#             )
#             return

#         # Показуємо поточний прогрес
#         await message.answer(
#             f"🔥 {user.mention_html()} — <b>{strikes}/2 страйків</b>",
#             parse_mode="HTML"
#         )

#     # Якщо не 6 — нічого не пишемо, щоб не засмічувати чат

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, ContentType
import logging
import random
from datetime import datetime, timedelta

from config import ADMIN_ID

router = Router(name="group_bowling")

# Працюємо тільки в групах
router.message.filter(F.chat.type.in_({"group", "supergroup"}))

# chat_id → {user_id: кількість страйків}
active_bowling_games = {}

# chat_id → список message_id, які можна видалити після завершення гри
bowling_messages = {}

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

    # Ініціалізація
    active_bowling_games[chat_id] = {}
    bowling_messages[chat_id] = []

    logging.info(f"🎳 БОУЛІНГ ЗАПУЩЕНО в чаті {chat_id}")

    start_msg = await message.answer(
        "🎳 <b>БОУЛІНГ СТАРТУВАВ!</b> 🎳\n\n"
    
        "🏆 <b>Перший, хто виб’є ДВА СТРАЙКИ</b> — Переможець!\n",
        parse_mode="HTML"
    )
    bowling_messages[chat_id].append(start_msg.message_id)  # 0 — стартове, захищене

    # Бот кидає перший боулінг
    bot_dice = await message.bot.send_dice(chat_id=chat_id, emoji="🎳")
    bowling_messages[chat_id].append(bot_dice.message_id)

    # Видаляємо команду /bowling
    try:
        await message.delete()
    except:
        pass


# ==========================
# ОБРОБКА КИДКІВ 🎳
# ==========================
@router.message(F.content_type == ContentType.DICE, F.dice.emoji == "🎳")
async def handle_bowling_dice(message: Message):
    chat_id = message.chat.id
    user = message.from_user
    user_id = user.id

    if chat_id not in active_bowling_games:
        try:
            await message.delete()
        except:
            pass
        return

    # Зберігаємо повідомлення для можливого видалення
    bowling_messages.setdefault(chat_id, []).append(message.message_id)

    game = active_bowling_games[chat_id]

    if user_id not in game:
        game[user_id] = 0

    score = message.dice.value

    if score != 6:
        return  # не страйк — нічого не робимо

    game[user_id] += 1
    strikes = game[user_id]

    if strikes >= 2:
        # Перевірка кулдауну
        if user_id in bowling_winner_cooldown:
            time_passed = datetime.now() - bowling_winner_cooldown[user_id]
            if time_passed < timedelta(hours=12):
                minutes_left = 720 - int(time_passed.total_seconds() // 60)
                hours_left = minutes_left // 60
                mins_left = minutes_left % 60

                cd_msg = await message.answer(
                    f"{user.mention_html()}, дай шанс іншим гравцям!\n"
                    f"⏳ <b>{hours_left} год {mins_left} хв</b> ⏳",
                    parse_mode="HTML"
                )
                bowling_messages[chat_id].append(cd_msg.message_id)

                # Очищаємо все крім стартового та цього повідомлення
                await cleanup_bowling_chat(chat_id, message.bot, protected_extra=cd_msg.message_id)
                del active_bowling_games[chat_id]
                return

        # Перемога!
        bowling_winner_cooldown[user_id] = datetime.now()

        win_msg = await message.answer(
            f"🎉 <b>ПЕРЕМОЖЕЦЬ!</b> 🏆\n\n"
            f"{user.mention_html()} вибив <b>ДВА СТРАЙКИ</b>!\n",
            parse_mode="HTML"
        )
        bowling_messages[chat_id].append(win_msg.message_id)

        # Очищаємо чат — залишаємо тільки стартове + повідомлення про перемогу
        await cleanup_bowling_chat(chat_id, message.bot, protected_extra=win_msg.message_id)

        # Завершуємо гру
        if chat_id in active_bowling_games:
            del active_bowling_games[chat_id]

        return

    # Прогрес (не страйк — не доходимо сюди, але на всяк випадок)
    if strikes > 0:
        progress_msg = await message.answer(
            f"🔥 {user.mention_html()} — <b>{strikes}/2 страйків</b>",
            parse_mode="HTML"
        )
        bowling_messages[chat_id].append(progress_msg.message_id)


async def cleanup_bowling_chat(chat_id: int, bot, protected_extra: int | None = None):
    """Видаляє всі збережені повідомлення крім стартового та protected_extra"""
    if chat_id not in bowling_messages:
        return

    protected = [bowling_messages[chat_id][0]]  # стартове
    if protected_extra:
        protected.append(protected_extra)

    for msg_id in bowling_messages[chat_id]:
        if msg_id in protected:
            continue
        try:
            await bot.delete_message(chat_id=chat_id, message_id=msg_id)
        except:
            pass  # ігноруємо помилки (немає прав, вже видалено тощо)

    # Оновлюємо список — тільки захищені повідомлення
    bowling_messages[chat_id] = [mid for mid in bowling_messages[chat_id] if mid in protected]