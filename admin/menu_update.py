import asyncio
import aiosqlite
from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.utils.keyboard import InlineKeyboardBuilder
from handlers.config import ADMIN_ID
from handlers.menu import main_menu
from db import has_claimed_gift
from db.core import DB_PATH
router = Router(name="admin_menu_update")


class MenuUpdate(StatesGroup):
    waiting_for_text = State()


@router.message(F.text == "🛠 Оновити меню")
async def start_menu_update(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await state.set_state(MenuUpdate.waiting_for_text)

    cancel_kb = InlineKeyboardBuilder()
    cancel_kb.button(text="❌ Скасувати", callback_data="cancel_menu_update")

    await message.answer(
        "✍️ Введіть текст, який буде надіслано всім користувачам разом з новим меню.\n\n"
        "Натисніть «❌ Скасувати», щоб вийти.",
        reply_markup=cancel_kb.as_markup(),
    )


@router.message(MenuUpdate.waiting_for_text)
async def process_menu_update_text(message: types.Message, state: FSMContext):
    text = message.text

    confirm_kb = InlineKeyboardBuilder()
    confirm_kb.button(text="✅ Надіслати", callback_data="confirm_menu_update")
    confirm_kb.button(text="❌ Скасувати", callback_data="cancel_menu_update")

    await state.update_data(update_text=text)
    await message.answer(
        f"📨 <b>Підтвердіть оновлення меню</b>\n\nТекст повідомлення:\n\n{text}",
        parse_mode="HTML",
        reply_markup=confirm_kb.as_markup(),
    )


@router.callback_query(F.data == "confirm_menu_update")
async def confirm_menu_update(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    text = data.get("update_text", "")

    await callback.message.answer("📤 Починаю оновлення меню...")

    async with aiosqlite.connect(DB_PATH) as conn:  # або DB_PATH, якщо імпортуєш
        async with conn.execute("SELECT user_id FROM users") as cur:
            rows = await cur.fetchall()

    total = len(rows)
    success = 0
    failed = 0

    for (user_id,) in rows:
        gift_claimed = await has_claimed_gift(user_id)
        try:
            await callback.bot.send_message(
                user_id,
                text,
                reply_markup=main_menu(
                    is_admin=(user_id == ADMIN_ID),
                    user_has_gift=gift_claimed
                ),
                parse_mode="HTML",
            )
            success += 1
            await asyncio.sleep(0.05)
        except Exception:
            failed += 1
            continue

    await callback.message.answer(
        f"✅ Оновлення меню завершено!\n\n"
        f"📬 Успішно: <b>{success}</b>\n"
        f"⚠️ Помилок: <b>{failed}</b>\n"
        f"👥 Всього користувачів: <b>{total}</b>",
        parse_mode="HTML",
    )

    await state.clear()
    await callback.answer()


@router.callback_query(F.data == "cancel_menu_update")
async def cancel_menu_update(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer("❌ Оновлення меню скасовано.")
    await callback.answer()