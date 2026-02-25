from aiogram import Router, F
from aiogram.types import Message
from datetime import datetime
import zoneinfo
import logging

from config import ADMIN_ID

router = Router(name="group_night_mode")

# Працюємо тільки в групах
router.message.filter(F.chat.type.in_({"group", "supergroup"}))

# Київський часовий пояс
try:
    KIEV_TZ = zoneinfo.ZoneInfo("Europe/Kiev")
except:
    from datetime import timezone, timedelta
    KIEV_TZ = timezone(timedelta(hours=2))  # fallback на EET


@router.message()
async def night_mode_antispam(message: Message):
    if message.from_user.id == ADMIN_ID:
        return  # адмін може писати завжди

    now = datetime.now(KIEV_TZ)
    hour = now.hour

    # Нічний режим: 00:00 — 08:59 включно
    if 0 <= hour < 9:
        try:
            await message.delete()
            logging.info(f"🌙 Нічний режим: видалено повідомлення від {message.from_user.id} о {hour}:00")
        except Exception as e:
            logging.error(f"Не вдалося видалити повідомлення: {e}")



