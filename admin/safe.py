from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from html import escape

from group_games.group_safe import load_state, save_state, get_win_cell, TOTAL_CELLS
from db import close_safe_round_and_credit
from handlers.config import ADMIN_ID

router = Router(name="admin_safe")


class SafeFSM(StatesGroup):
    waiting_for_win_cell = State()


def safe_admin_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🗑 Очистити сейф", callback_data="safe:clear")],
            [
                InlineKeyboardButton(
                    text="🔢 Встановити виграшне число", callback_data="safe:set_win"
                )
            ],
            [
                InlineKeyboardButton(
                    text="👁 Поточне виграшне число", callback_data="safe:view_win"
                )
            ],
            [InlineKeyboardButton(text="📊 Стан сейфа", callback_data="safe:status")],
        ]
    )


@router.message(F.text == "🔒 Сейф")
async def safe_admin_panel(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer(
        "🔒 <b>Керування сейфом</b>",
        parse_mode="HTML",
        reply_markup=safe_admin_keyboard(),
    )


# --- Очистити сейф ---
@router.callback_query(F.data == "safe:clear")
async def safe_clear_confirm(cb: CallbackQuery):
    if cb.from_user.id != ADMIN_ID:
        return
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Так, очистити", callback_data="safe:clear_confirm"
                ),
                InlineKeyboardButton(text="❌ Скасувати", callback_data="safe:back"),
            ]
        ]
    )
    await cb.message.edit_text(
        "⚠️ Очистити всі відкриті клітинки та почати новий раунд?", reply_markup=kb
    )
    await cb.answer()


@router.callback_query(F.data == "safe:clear_confirm")
async def safe_clear_do(cb: CallbackQuery):
    if cb.from_user.id != ADMIN_ID:
        return
    win_cell = await get_win_cell()
    awards = await close_safe_round_and_credit(win_cell)
    awards_text = ""
    if awards:
        lines = [
            f"{place}. {escape(award['display_name'])} — {award['amount']} грн"
            for place, award in enumerate(awards, 1)
        ]
        awards_text = "\n\n💰 <b>Автоматично нараховано як депозит:</b>\n" + "\n".join(lines)

    await cb.message.edit_text(
        f"✅ <b>Сейф очищено!</b>\nНовий раунд розпочато.\n"
        f"Виграшна клітинка залишається: <b>{win_cell}</b>{awards_text}",
        parse_mode="HTML",
        reply_markup=safe_admin_keyboard(),
    )

    for award in awards:
        try:
            await cb.bot.send_message(
                award["user_id"],
                f"🏆 Ви увійшли до топ-5 сейфа!\n"
                f"💰 На депозит автоматично нараховано {award['amount']} грн.",
            )
        except Exception:
            pass
    await cb.answer("✅ Сейф очищено!")


# --- Встановити виграшне число ---
@router.callback_query(F.data == "safe:set_win")
async def safe_set_win_ask(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id != ADMIN_ID:
        return
    await state.set_state(SafeFSM.waiting_for_win_cell)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text="❌ Скасувати", callback_data="safe:cancel_fsm")
        ]]
    )
    await cb.message.edit_text(
        f"🔢 Введіть нове виграшне число (від 1 до {TOTAL_CELLS}):", reply_markup=kb
    )
    await cb.answer()


@router.message(SafeFSM.waiting_for_win_cell)
async def safe_set_win_save(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        cell = int(message.text.strip())
        if cell < 1 or cell > TOTAL_CELLS:
            raise ValueError
    except ValueError:
        await message.answer(f"❌ Введіть число від 1 до {TOTAL_CELLS}")
        return

    state_data = await load_state()
    await save_state(state_data.get("opened", []), win_cell=cell)
    await state.clear()
    await message.answer(
        f"✅ <b>Виграшну клітинку встановлено: {cell}</b>",
        parse_mode="HTML",
        reply_markup=safe_admin_keyboard(),
    )


@router.callback_query(F.data == "safe:cancel_fsm")
async def safe_cancel_fsm(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await cb.message.edit_text(
        "🔒 <b>Керування сейфом</b>",
        parse_mode="HTML",
        reply_markup=safe_admin_keyboard(),
    )
    await cb.answer("❌ Скасовано")


# --- Переглянути виграшне число ---
@router.callback_query(F.data == "safe:view_win")
async def safe_view_win(cb: CallbackQuery):
    if cb.from_user.id != ADMIN_ID:
        return
    win_cell = await get_win_cell()
    await cb.answer(f"🏆 Виграшна клітинка: {win_cell}", show_alert=True)


# --- Стан сейфа ---
@router.callback_query(F.data == "safe:status")
async def safe_status(cb: CallbackQuery):
    if cb.from_user.id != ADMIN_ID:
        return
    state = await load_state()
    opened = state.get("opened", [])
    win_cell = state.get("win_cell", "?")
    text = (
        f"📊 <b>Стан сейфа</b>\n\n"
        f"Відкрито: <b>{len(opened)}</b> / {TOTAL_CELLS}\n"
        f"Виграшна клітинка: <b>{win_cell}</b>\n"
        f"Залишилось: <b>{TOTAL_CELLS - len(opened)}</b>"
    )
    await cb.message.edit_text(
        text, parse_mode="HTML", reply_markup=safe_admin_keyboard()
    )
    await cb.answer()


# --- Назад ---
@router.callback_query(F.data == "safe:back")
async def safe_back(cb: CallbackQuery):
    await cb.message.edit_text(
        "🔒 <b>Керування сейфом</b>",
        parse_mode="HTML",
        reply_markup=safe_admin_keyboard(),
    )
    await cb.answer()
