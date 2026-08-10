from aiogram import F, Router, types
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from db import get_piggy_bank_state, update_piggy_bank_setting
from handlers.config import ADMIN_ID


router = Router(name="admin_piggy_bank")

SETTING_LABELS = {
    "limit": "ліміт",
    "player_prize": "виграш гравця",
    "admin_prize": "виграш адміна",
}


class PiggyBankAdminFSM(StatesGroup):
    waiting_for_value = State()


def piggy_admin_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🎯 Змінити ліміт", callback_data="piggy_admin:set:limit"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🏆 Виграш гравця",
                    callback_data="piggy_admin:set:player_prize",
                ),
                InlineKeyboardButton(
                    text="👑 Виграш адміна",
                    callback_data="piggy_admin:set:admin_prize",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🔄 Оновити", callback_data="piggy_admin:refresh"
                )
            ],
        ]
    )


def piggy_admin_text(state: dict, notice: str | None = None) -> str:
    reserve = state["limit"] - state["player_prize"] - state["admin_prize"]
    text = (
        "🐷 <b>Керування скарбничкою</b>\n\n"
        f"💰 Баланс: <b>{state['balance']} грн</b>\n"
        f"🎯 Ліміт: <b>{state['limit']} грн</b>\n"
        f"🏆 Гравцю: <b>{state['player_prize']} грн</b>\n"
        f"👑 Фіксований виграш адміну: <b>{state['admin_prize']} грн</b>\n"
        f"🔁 Раунд: <b>№{state['round_number']}</b>\n"
        f"🐽 Залишок при точному заповненні: <b>{reserve} грн</b> "
        "(також адміну)"
    )
    return f"{notice}\n\n{text}" if notice else text


@router.message(F.text == "🐷 Керування скарбничкою")
async def open_piggy_admin(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    state = await get_piggy_bank_state()
    await message.answer(
        piggy_admin_text(state),
        parse_mode="HTML",
        reply_markup=piggy_admin_keyboard(),
    )


@router.callback_query(F.data == "piggy_admin:refresh")
async def refresh_piggy_admin(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Немає доступу", show_alert=True)
        return
    state = await get_piggy_bank_state()
    try:
        await callback.message.edit_text(
            piggy_admin_text(state),
            parse_mode="HTML",
            reply_markup=piggy_admin_keyboard(),
        )
    except TelegramBadRequest as error:
        if "message is not modified" not in str(error).lower():
            raise
    await callback.answer("Оновлено")


@router.callback_query(F.data.startswith("piggy_admin:set:"))
async def ask_piggy_setting(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Немає доступу", show_alert=True)
        return
    setting = callback.data.rsplit(":", 1)[1]
    if setting not in SETTING_LABELS:
        await callback.answer("Невідоме налаштування", show_alert=True)
        return

    await state.set_state(PiggyBankAdminFSM.waiting_for_value)
    await state.update_data(piggy_setting=setting)
    cancel_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="❌ Скасувати", callback_data="piggy_admin:cancel"
                )
            ]
        ]
    )
    await callback.message.edit_text(
        f"Введіть нове значення для поля <b>{SETTING_LABELS[setting]}</b>.\n\n"
        "Сума має бути кратною 10 грн.",
        parse_mode="HTML",
        reply_markup=cancel_keyboard,
    )
    await callback.answer()


@router.message(PiggyBankAdminFSM.waiting_for_value)
async def save_piggy_setting(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    data = await state.get_data()
    setting = data.get("piggy_setting")
    try:
        value = int((message.text or "").strip())
    except ValueError:
        await message.answer("❌ Введіть ціле число, кратне 10.")
        return

    result = await update_piggy_bank_setting(setting, value)
    if not result["success"]:
        reasons = {
            "invalid_value": "Сума має бути невід’ємною та кратною 10 грн.",
            "below_balance": (
                "Ліміт не може бути нижчим за поточний баланс скарбнички."
            ),
            "invalid_prize_total": (
                "Сума виграшів має бути більшою за 0 і не перевищувати ліміт."
            ),
        }
        error_text = reasons.get(result["reason"], "Некоректне значення.")
        await message.answer(f"❌ {error_text}")
        return

    await state.clear()
    await message.answer(
        piggy_admin_text(result["state"], "✅ <b>Налаштування збережено.</b>"),
        parse_mode="HTML",
        reply_markup=piggy_admin_keyboard(),
    )


@router.callback_query(F.data == "piggy_admin:cancel")
async def cancel_piggy_setting(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Немає доступу", show_alert=True)
        return
    await state.clear()
    current = await get_piggy_bank_state()
    await callback.message.edit_text(
        piggy_admin_text(current),
        parse_mode="HTML",
        reply_markup=piggy_admin_keyboard(),
    )
    await callback.answer("Скасовано")
