from aiogram import Router, F, types
from aiogram.types import ReplyKeyboardRemove
from handlers.menu import admin_menu, admin_menu2, main_menu
from handlers.config import ADMIN_ID

router = Router(name="admin_base")


# ==========================
# ⚙️ Адмін панель
# ==========================
@router.message(F.text == "⚙️ Адмін панель")
async def admin_panel(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer("🔐 Адмін панель", reply_markup=admin_menu())
    else:
        await message.answer("⛔ У вас немає доступу")


# ==========================
#             ⚙️⚙️⚙️
# ==========================
@router.message(F.text == "⚙️⚙️⚙️")
async def admin_panel2(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer("🔐 Адмін панель", reply_markup=admin_menu2())
    else:
        await message.answer("⛔ У вас немає доступу")



