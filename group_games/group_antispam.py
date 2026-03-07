from aiogram import Router, F
from aiogram.types import Message, ContentType
import logging

from handlers.config import ADMIN_ID

router = Router(name="group_antispam")

# Працюємо тільки в групах
router.message.filter(F.chat.type.in_({"group", "supergroup"}))

# Імпортуємо словники активних ігор з усіх твоїх ігор
from .group_bowling import active_bowling_games
from .group_basketball import active_basketball_games
from .football_router import active_football_games

# Список смайлів, які блокуємо поза грою
BLOCKED_EMOJIS = {"⚽", "🏀", "🎾", "🎳", "🎯"}   # ← сюди додавай нові (наприклад "🏈", "🏐" тощо)

@router.message(F.content_type == ContentType.DICE)
async def antispam_dice(message: Message):
    emoji = message.dice.emoji

    if emoji not in BLOCKED_EMOJIS:
        return  # це не наш ігровий смайл — ігноруємо

    chat_id = message.chat.id

    # Перевіряємо, чи активна хоч одна гра в цьому чаті
    is_game_active = (
        chat_id in active_bowling_games or
        chat_id in active_basketball_games or
        chat_id in active_football_games
    )

    if not is_game_active:
        try:
            await message.delete()
            logging.info(f"🛡️ Антиспам: видалено {emoji} від {message.from_user.id} в чаті {chat_id}")
        except Exception as e:
            logging.error(f"Не вдалося видалити смайл: {e}")