# from aiogram import Router, F
# from aiogram.filters import Command
# from aiogram.types import Message, ContentType

# from config import ADMIN_ID

# router = Router(name="group_bowling")

# # Працюємо тільки в групах
# router.message.filter(F.chat.type.in_({"group", "supergroup"}))

# # Глобальний словник активних ігор (chat_id → True/False)
# active_bowling_games = {}

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
#     active_bowling_games[chat_id] = True

#     await message.answer(
#         "🎳 <b>БОУЛІНГ СТАРТУВАВ!</b> 🏆\n\n"
#         "Кидайте 🎳 в чат!\n"
#         "<b>Перший, хто виб'є STRIKE (6)</b> — переможець!"
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

#     # Якщо гра не активна — видаляємо повідомлення
#     if chat_id not in active_bowling_games or not active_bowling_games[chat_id]:
#         try:
#             await message.delete()
#         except:
#             pass
#         return

#     # Гра активна
#     score = message.dice.value  # 1-6

#     if score == 6:  # STRIKE!
#         active_bowling_games[chat_id] = False  # завершуємо гру

#         await message.answer(
#             f"🎉 <b>ПЕРЕМОЖЕЦЬ!</b> 🏆\n\n"
#             f"{user.mention_html()} вибив STRIKE (6)!\n"
#             f"Вітаємо! Приз буде видано в кабінеті 🎁",
#             parse_mode="HTML"
#         )

#         # Можна додати видачу промокоду пізніше

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, ContentType

from config import ADMIN_ID

router = Router(name="group_bowling")

# Працюємо тільки в групах
router.message.filter(F.chat.type.in_({"group", "supergroup"}))

# chat_id → {user_id: кількість_страйків}
active_bowling_games = {}


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

    await message.answer(
        "🎳 <b>БОУЛІНГ СТАРТУВАВ!</b> 🏆\n\n"
        "Кидайте 🎳 в чат!\n"
        "<b>Перший, хто виб’є ДВА СТРАЙКИ </b> — переможець!"
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
            del active_bowling_games[chat_id]   # завершуємо гру

            await message.answer(
                f"🎉 <b>ПЕРЕМОЖЕЦЬ!</b> 🏆\n\n"
                f"{user.mention_html()} вибив <b>ДВА СТРАЙКИ</b>!\n"
                f"Вітаємо! Приз буде видано негайно",
                parse_mode="HTML"
            )
            return

        # Показуємо поточний прогрес
        await message.answer(
            f"🔥 {user.mention_html()} — <b>{strikes}/2 страйків</b>",
            parse_mode="HTML"
        )

    # Якщо не 6 — нічого не пишемо, щоб не засмічувати чат