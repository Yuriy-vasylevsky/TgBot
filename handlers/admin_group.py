from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message

from config import ADMIN_ID

router = Router(name="admin_group")

# Працюємо тільки в групах
router.message.filter(F.chat.type.in_({"group", "supergroup"}))

# ==========================
# ЗАХИСТ: видалення + попередження в ЛС
# ==========================
@router.message(
    Command(commands=["start", "bowling", "start@Kassa_4444_bot", "basketball", "football", "open", "safe",]),
    F.from_user.id != ADMIN_ID
)
async def delete_and_warn(message: Message):
    # Видаляємо команду з групи
    try:
        await message.delete()
    except:
        pass

    # Попередження в особисті
    warning_text = (
        "🚫 <b>Не балуйся, бо буде бан!</b> \n\n"
        "Ці команди доступні <b>тільки адміністратору</b>.\n"
    )

    try:
        await message.bot.send_message(
            chat_id=message.from_user.id,
            text=warning_text,
            parse_mode="HTML"
        )
    except:
        pass  # приват закритий — мовчимо


# =============================================
# ПОВНІСТЮ БЛОКУЄМО /start В ГРУПІ ДЛЯ ЗВИЧАЙНИХ КОРИСТУВАЧІВ
# =============================================
@router.message(
    Command("start"),
    F.chat.type.in_({"group", "supergroup"}),
    F.from_user.id != ADMIN_ID
)
async def block_start_in_group(message: Message):
    try:
        await message.delete()          
    except:
        pass                            



