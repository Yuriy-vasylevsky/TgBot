from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.types import ReplyKeyboardRemove
from db import get_winrate, set_winrate
from handlers.states import WinrateFSM
from handlers.menu import main_menu
from handlers.config import ADMIN_ID

router = Router(name="admin_winrate")


# ==========================
# 🎯 Winrate
# ==========================
@router.message(F.text == "🎯 Winrate")
async def show_winrate(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    current = await get_winrate()
    percent = round(current * 100)
    await message.answer(
        f"🎯 Поточний winrate: <b>{percent}%</b>\n\n"
        f"Введіть новий відсоток виграшу (0–100):",
        reply_markup=ReplyKeyboardRemove(),
    )
    await state.set_state(WinrateFSM.waiting_for_value)


@router.message(WinrateFSM.waiting_for_value)
async def set_new_winrate(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        val = int(message.text.strip())
        if not (0 <= val <= 100):
            raise ValueError
        await set_winrate(val / 100)
        await message.answer(
            f"✅ Новий winrate збережено: {val}%",
            reply_markup=main_menu(is_admin=True),
        )
    except ValueError:
        await message.answer(
            "❌ Введіть число від 0 до 100.",
            reply_markup=main_menu(is_admin=True),
        )
    await state.clear()