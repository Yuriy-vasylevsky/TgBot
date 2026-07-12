from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove

from db import get_cards, update_card
from handlers.config import ADMIN_ID
from handlers.menu import admin_menu

router = Router(name="admin_cards")


class CardFSM(StatesGroup):
    waiting_for_bank = State()
    waiting_for_number = State()


@router.message(F.text == "💳 Керування картами")
async def manage_cards(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return

    cards = await get_cards()
    text = "🏦 Поточні картки:\n\n" + "\n".join(
        [f"{bank}: <code>{num}</code>" for bank, num in cards]
    )

    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Карта 1"), KeyboardButton(text="Карта 2")],
            [KeyboardButton(text="❌ Відмінити дію")],
        ],
        resize_keyboard=True,
    )

    await message.answer(
        f"{text}\n\n🔧 Виберіть банк для редагування:", reply_markup=kb
    )
    await state.set_state(CardFSM.waiting_for_bank)


@router.message(CardFSM.waiting_for_bank)
async def ask_new_card(message: types.Message, state: FSMContext):
    bank = message.text
    if bank == "❌ Відмінити дію":
        await state.clear()
        await message.answer("❌ Скасовано.", reply_markup=admin_menu())
        return

    await state.update_data(bank_name=bank)
    await message.answer(
        f"💳 Введіть новий номер картки для {bank}:", reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(CardFSM.waiting_for_number)


@router.message(CardFSM.waiting_for_number)
async def save_new_card(message: types.Message, state: FSMContext):
    data = await state.get_data()
    bank_name = data.get("bank_name")
    new_number = message.text.strip()

    await update_card(bank_name, new_number)
    await message.answer(
        f"✅ Картку для {bank_name} оновлено на:\n<code>{new_number}</code>",
        parse_mode="HTML",
        reply_markup=admin_menu()),
    
    await state.clear()