import re
from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from db import add_casino_code
from handlers.config import ADMIN_ID
from handlers.states import AddCodeFSM

router = Router(name="admin_casino_codes")


class AddCodeFSM(StatesGroup):
    waiting_for_type = State()
    waiting_for_code = State()


# ======================
# ДОДАВАННЯ КОДУ (для адміна)
# ======================
@router.message(F.text == "➕ Додати промокод")
async def ask_code_type(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ Тільки адміністратор.")
        return

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🏆 Champion", callback_data="add_code_type:champion"
                ),
                InlineKeyboardButton(
                    text="🎰 Superomatic", callback_data="add_code_type:superomatic"
                ),
            ]
        ]
    )
    await message.answer("Виберіть тип коду для додавання:", reply_markup=kb)


@router.callback_query(F.data.startswith("add_code_type:"))
async def on_choose_add_type(cb: CallbackQuery, state: FSMContext):
    _, code_type = cb.data.split(":")
    await state.update_data(casino_type=code_type)
    await state.set_state(AddCodeFSM.waiting_for_code)
    await cb.message.answer(f"Введіть новий код для {code_type}:")
    await cb.answer()


@router.message(AddCodeFSM.waiting_for_code)
async def add_code_receive(message: Message, state: FSMContext):
    data = await state.get_data()
    casino_type = data.get("casino_type")
    code = message.text.strip()

    if not re.fullmatch(r"(\d{2}-){6}\d{2}", code):
        await message.answer("❌ Невірний формат! Приклад: 11-36-36-50-20-11-33")
        return

    await add_casino_code(code, casino_type)

    await message.answer(
        f"✅ Код <code>{code}</code> додано до {casino_type}.", 
        parse_mode="HTML"
    )
    await state.clear()


# ++++++++++++++++++ Авто генерація посилань при надсиланні коду +++++++++++++++++++++++++++++++++

@router.message(F.text.regexp(r"^\d{2}(?:-\d{2}){6}$"))
async def auto_generate_links(message: Message, state: FSMContext):
    current_state = await state.get_state()

    # якщо зараз адмін додає код вручну — пропускаємо
    if current_state == AddCodeFSM.waiting_for_code.state:
        return

    code = message.text.strip().replace("-", "")
    await message.answer(f"🏆 Champion:\nhttps://spinplanet.net/?login_code={code}")
    # await message.answer(f"🎰 Superomatic:\nhttps://code.greenhost.pw/?c={code}")