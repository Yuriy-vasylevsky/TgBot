from html import escape

from aiogram import F, Router, types
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from db import (
    ALLOWED_CONTRIBUTIONS,
    contribute_to_piggy_bank,
    get_piggy_bank_state,
)
from handlers.config import ADMIN_ID


router = Router(name="piggy_bank")


def piggy_bank_keyboard(state: dict) -> InlineKeyboardMarkup:
    remaining = state["limit"] - state["balance"]
    buttons = [
        InlineKeyboardButton(
            text=f"➕ {amount} грн", callback_data=f"piggy:add:{amount}"
        )
        for amount in ALLOWED_CONTRIBUTIONS
        if amount <= remaining
    ]
    rows = [buttons] if buttons else []
    rows.append(
        [InlineKeyboardButton(text="🔄 Оновити", callback_data="piggy:refresh")]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def piggy_bank_text(state: dict, notice: str | None = None) -> str:
    remaining = state["limit"] - state["balance"]
    text = (
        "🐷 <b>Скарбничка</b>\n\n"
        # f"💰 Зібрано: <b>{state['balance']} / {state['limit']} грн</b>\n"
        f"🏆 Виграш: <b>{state['player_prize']} грн</b>\n"
        # f"🎯 До заповнення: <b>{remaining} грн</b>\n\n"
        "Обери суму внеску. Якщо твій внесок заповнить скарбничку, "
        "виграш одразу надійде на твій баланс."
    )
    if notice:
        text = f"{notice}\n\n{text}"
    return text


async def edit_piggy_bank_message(
    callback: types.CallbackQuery, state: dict, notice: str | None = None
) -> None:
    try:
        await callback.message.edit_text(
            piggy_bank_text(state, notice),
            parse_mode="HTML",
            reply_markup=piggy_bank_keyboard(state),
        )
    except TelegramBadRequest as error:
        if "message is not modified" not in str(error).lower():
            raise


@router.message(F.text == "🐷 Скарбничка")
async def open_piggy_bank(message: types.Message):
    state = await get_piggy_bank_state()
    await message.answer(
        piggy_bank_text(state),
        parse_mode="HTML",
        reply_markup=piggy_bank_keyboard(state),
    )


@router.callback_query(F.data == "piggy:refresh")
async def refresh_piggy_bank(callback: types.CallbackQuery):
    state = await get_piggy_bank_state()
    await edit_piggy_bank_message(callback, state)
    await callback.answer("Оновлено")


@router.callback_query(F.data.startswith("piggy:add:"))
async def add_to_piggy_bank(callback: types.CallbackQuery):
    try:
        amount = int(callback.data.rsplit(":", 1)[1])
    except (AttributeError, ValueError):
        await callback.answer("Некоректна сума", show_alert=True)
        return

    result = await contribute_to_piggy_bank(
        callback.from_user.id, amount, ADMIN_ID
    )
    if not result["success"]:
        state = result.get("state") or await get_piggy_bank_state()
        if result["reason"] == "insufficient_funds":
            notice = (
                "❌ <b>Недостатньо коштів.</b> "
                f"Ваш баланс: {result.get('balance', 0)} грн."
            )
        elif result["reason"] == "over_limit":
            notice = "⚠️ Цей внесок уже не вміщується. Оберіть меншу суму."
        else:
            notice = "❌ Не вдалося зробити внесок."
        await edit_piggy_bank_message(callback, state, notice)
        await callback.answer("Внесок не виконано", show_alert=True)
        return

    state = result["state"]
    if result["triggered"]:
        notice = (
            "🎉 <b>Скарбничку заповнено!</b>\n"
            f"Ви отримали <b>{state['player_prize']} грн</b>. "
            f"Ваш баланс: <b>{result['balance']} грн</b>."
        )
    else:
        notice = (
            f"✅ Внесено <b>{amount} грн</b>. "
            f"Ваш баланс: <b>{result['balance']} грн</b>."
        )

    await edit_piggy_bank_message(callback, state, notice)
    await callback.answer("Готово")

    if result["triggered"] and ADMIN_ID != callback.from_user.id:
        username = (
            f"@{escape(callback.from_user.username)}"
            if callback.from_user.username
            else escape(callback.from_user.full_name)
        )
        try:
            await callback.bot.send_message(
                ADMIN_ID,
                "🐷 <b>Скарбничку заповнено</b>\n\n"
                f"Переможець: {username} (<code>{callback.from_user.id}</code>)\n"
                f"Гравцю: <b>{state['player_prize']} грн</b>\n"
                f"Адміну: <b>{state['admin_prize']} грн</b>",
                parse_mode="HTML",
            )
        except Exception:
            pass
