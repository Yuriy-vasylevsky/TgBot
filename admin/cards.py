from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove

from db import (
    add_payment_verification_iban,
    delete_payment_verification_iban,
    get_cards,
    get_payment_verification_ibans,
    update_card,
)
from handlers.config import ADMIN_ID
from handlers.menu import admin_menu

router = Router(name="admin_cards")


class CardFSM(StatesGroup):
    waiting_for_bank = State()
    waiting_for_display_name = State()
    waiting_for_number = State()
    waiting_for_iban = State()
    waiting_for_iban_delete = State()


@router.message(F.text == "💳 Керування картами")
async def manage_cards(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return

    cards = await get_cards()
    ibans = await get_payment_verification_ibans()
    text = "🏦 Поточні картки:\n\n" + "\n".join(
        [
            f"Карта {index}: {bank}: <code>{num}</code>"
            for index, (bank, num) in enumerate(cards, start=1)
        ]
    )
    hidden_ibans = "\n".join(
        f"IBAN {index}: <code>{iban}</code>"
        for index, (_, iban) in enumerate(ibans, start=1)
    ) or "ще не додані"
    text += (
        "\n\n🔐 Приховані IBAN для перевірки квитанцій "
        "(користувачі їх не бачать):\n"
        f"{hidden_ibans}"
    )

    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Карта 1"), KeyboardButton(text="Карта 2")],
            [
                KeyboardButton(text="➕ Додати IBAN"),
                KeyboardButton(text="🗑 Видалити IBAN"),
            ],
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
    bank = (message.text or "").strip()
    if bank == "❌ Відмінити дію":
        await state.clear()
        await message.answer("❌ Скасовано.", reply_markup=admin_menu())
        return

    if bank == "➕ Додати IBAN":
        await message.answer(
            "🔐 Введіть повний IBAN. Він використовуватиметься лише для "
            "перевірки квитанцій і не показуватиметься користувачам:",
            reply_markup=ReplyKeyboardRemove(),
        )
        await state.set_state(CardFSM.waiting_for_iban)
        return

    if bank == "🗑 Видалити IBAN":
        ibans = await get_payment_verification_ibans()
        if not ibans:
            await message.answer("ℹ️ Прихованих IBAN ще немає.")
            return
        buttons = []
        delete_mapping = {}
        for index, (iban_id, iban) in enumerate(ibans, start=1):
            label = f"IBAN {index}: …{iban[-6:]}"
            buttons.append([KeyboardButton(text=label)])
            delete_mapping[label] = iban_id
        buttons.append([KeyboardButton(text="❌ Відмінити дію")])
        await state.update_data(iban_delete_mapping=delete_mapping)
        await message.answer(
            "🗑 Виберіть IBAN, який треба видалити:",
            reply_markup=ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True),
        )
        await state.set_state(CardFSM.waiting_for_iban_delete)
        return

    if bank not in {"Карта 1", "Карта 2"}:
        await message.answer("❌ Виберіть Карту 1, Карту 2 або дію з IBAN.")
        return

    await state.update_data(bank_name=bank)
    await message.answer(
        f"🏦 Введіть назву банку для {bank}:",
        reply_markup=ReplyKeyboardRemove(),
    )
    await state.set_state(CardFSM.waiting_for_display_name)


@router.message(CardFSM.waiting_for_display_name)
async def ask_new_card_number(message: types.Message, state: FSMContext):
    display_name = (message.text or "").strip()
    if not display_name:
        await message.answer("❌ Назва банку не може бути порожньою. Введіть назву:")
        return

    await state.update_data(display_name=display_name)
    await message.answer(f"💳 Введіть новий номер картки для {display_name}:")
    await state.set_state(CardFSM.waiting_for_number)


@router.message(CardFSM.waiting_for_number)
async def save_new_card(message: types.Message, state: FSMContext):
    data = await state.get_data()
    bank_name = data.get("bank_name")
    display_name = data.get("display_name")
    new_number = message.text.strip()

    await update_card(bank_name, display_name, new_number)
    await message.answer(
        f"✅ {bank_name} оновлено:\n"
        f"🏦 {display_name}: <code>{new_number}</code>",
        parse_mode="HTML",
        reply_markup=admin_menu()),
    
    await state.clear()


@router.message(CardFSM.waiting_for_iban)
async def save_verification_iban(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    value = (message.text or "").strip()
    if value == "❌ Відмінити дію":
        await state.clear()
        await message.answer("❌ Скасовано.", reply_markup=admin_menu())
        return

    result = await add_payment_verification_iban(value)
    if not result["ok"]:
        if result["reason"] == "exists":
            await message.answer("ℹ️ Цей IBAN уже доданий. Введіть інший IBAN:")
        else:
            await message.answer(
                "❌ Некоректний IBAN. Перевірте всі символи та контрольні цифри "
                "і надішліть повний номер ще раз:"
            )
        return

    await state.clear()
    await message.answer(
        f"✅ Прихований IBAN додано:\n<code>{result['iban']}</code>\n\n"
        "Він доступний боту для перевірки квитанцій, але не показується "
        "користувачам.",
        parse_mode="HTML",
        reply_markup=admin_menu(),
    )


@router.message(CardFSM.waiting_for_iban_delete)
async def remove_verification_iban(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    selection = (message.text or "").strip()
    if selection == "❌ Відмінити дію":
        await state.clear()
        await message.answer("❌ Скасовано.", reply_markup=admin_menu())
        return

    data = await state.get_data()
    iban_id = (data.get("iban_delete_mapping") or {}).get(selection)
    if iban_id is None:
        await message.answer("❌ Виберіть IBAN кнопкою зі списку.")
        return

    deleted = await delete_payment_verification_iban(iban_id)
    await state.clear()
    await message.answer(
        "✅ IBAN видалено." if deleted else "ℹ️ IBAN уже був видалений.",
        reply_markup=admin_menu(),
    )
