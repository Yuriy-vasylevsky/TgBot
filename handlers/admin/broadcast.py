import aiosqlite
from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import CallbackQuery

from db import DB_PATH, ensure_users_table_and_columns
from handlers.states import Broadcast
from handlers.config import ADMIN_ID

router = Router(name="admin_broadcast")


class TemplateFSM(StatesGroup):
    waiting_title = State()
    waiting_body = State()


# ========================================================================================================
#                                            📢 Розсилка
# ========================================================================================================

@router.message(F.text == "📢 Розсилка")
async def start_broadcast(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return

    kb = InlineKeyboardBuilder()
    kb.button(text="📄 Створити шаблон", callback_data="create_template")
    kb.button(text="📂 Шаблони", callback_data="show_templates")
    kb.button(text="❌ Скасувати", callback_data="cancel_broadcast")
    kb.adjust(2, 1)

    await state.set_state(Broadcast.waiting_for_text)
    await message.answer(
        "✍️ Введіть текст розсилки або використайте шаблон:",
        reply_markup=kb.as_markup(),
    )


@router.message(Broadcast.waiting_for_text)
async def process_broadcast_text(message: types.Message, state: FSMContext):
    text = message.text
    confirm_kb = InlineKeyboardBuilder()
    confirm_kb.button(text="✅ Надіслати", callback_data="confirm_broadcast")
    confirm_kb.button(text="❌ Скасувати", callback_data="cancel_broadcast")
    await state.update_data(broadcast_text=text)
    await message.answer(
        f"📨 Текст розсилки:\n\n{text}\n\nНадіслати розсилку?",
        reply_markup=confirm_kb.as_markup(),
    )


@router.callback_query(F.data == "confirm_broadcast")
async def confirm_broadcast(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    text = data.get("broadcast_text")
    if not text:
        await callback.answer("❌ Текст розсилки порожній!", show_alert=True)
        return

    await ensure_users_table_and_columns()

    async with aiosqlite.connect(DB_PATH) as conn:
        async with conn.execute("SELECT user_id FROM users") as cur:
            rows = await cur.fetchall()

    count = 0
    failed = 0
    for (user_id,) in rows:
        try:
            await callback.bot.send_message(user_id, text, parse_mode="HTML")
            count += 1
        except Exception:
            failed += 1
            continue

    await callback.message.answer(
        f"✅ Розсилку завершено!\n\n"
        f"✅ Успішно: <b>{count}</b>\n"
        f"❌ Не вдалося: <b>{failed}</b>",
        parse_mode="HTML",
    )
    await state.clear()
    await callback.answer("Розсилка завершена ✅")


@router.callback_query(F.data == "cancel_broadcast")
async def cancel_broadcast(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer("❌ Розсилку скасовано.")
    await callback.answer()


# ======================= Шаблони ======================

@router.callback_query(F.data == "show_templates")
async def show_templates(cb: CallbackQuery, state: FSMContext):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT id,title FROM broadcast_templates ORDER BY id DESC"
        )
        rows = await cur.fetchall()

    kb = InlineKeyboardBuilder()

    if not rows:
        kb.button(text="🔙 Назад", callback_data="back_to_broadcast")
        await cb.message.edit_text("📂 Немає шаблонів.", reply_markup=kb.as_markup())
        await cb.answer()
        return

    for tid, title in rows:
        kb.button(text=title, callback_data=f"use_template:{tid}")
        kb.button(text="🗑", callback_data=f"delete_template:{tid}")

    kb.button(text="🔙 Назад", callback_data="back_to_broadcast")
    kb.adjust(2, 1)

    await cb.message.edit_text("📂 Шаблони:", reply_markup=kb.as_markup())
    await cb.answer()


@router.callback_query(F.data.startswith("use_template:"))
async def use_template(cb: CallbackQuery, state: FSMContext):
    tid = cb.data.split(":")[1]
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT text FROM broadcast_templates WHERE id=?", (tid,)
        )
        row = await cur.fetchone()

    if not row:
        return await cb.answer("Помилка шаблону", show_alert=True)

    text = row[0]
    await state.update_data(broadcast_text=text)

    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Надіслати", callback_data="confirm_broadcast")
    kb.button(text="❌ Скасувати", callback_data="cancel_broadcast")

    await cb.message.edit_text(
        f"📨 Текст розсилки:\n\n{text}\n\nНадіслати?", reply_markup=kb.as_markup()
    )
    await cb.answer()


@router.callback_query(F.data == "create_template")
async def create_template(cb: CallbackQuery, state: FSMContext):
    await state.set_state(TemplateFSM.waiting_title)
    await cb.message.edit_text("📄 Введіть назву шаблону:")
    await cb.answer()


@router.message(TemplateFSM.waiting_title)
async def template_title(message: types.Message, state: FSMContext):
    await state.update_data(template_title=message.text)
    await state.set_state(TemplateFSM.waiting_body)
    await message.answer("✍️ Текст шаблону:")


@router.message(TemplateFSM.waiting_body)
async def template_body(message: types.Message, state: FSMContext):
    data = await state.get_data()
    title = data["template_title"]
    text = message.text

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO broadcast_templates (title,text) VALUES (?,?)", (title, text)
        )
        await db.commit()

    await state.clear()
    await message.answer(f"✅ Шаблон <b>{title}</b> збережено.", parse_mode="HTML")


@router.callback_query(F.data.startswith("delete_template:"))
async def ask_delete_template(cb: CallbackQuery):
    tid = cb.data.split(":")[1]

    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Так", callback_data=f"confirm_delete_template:{tid}")
    kb.button(text="❌ Ні", callback_data="show_templates")
    kb.adjust(2)

    await cb.message.edit_text("Видалити шаблон?", reply_markup=kb.as_markup())
    await cb.answer()


@router.callback_query(F.data.startswith("confirm_delete_template:"))
async def confirm_delete_template(cb: CallbackQuery):
    tid = cb.data.split(":")[1]

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM broadcast_templates WHERE id=?", (tid,))
        await db.commit()

    await cb.answer("✅ Видалено.")
    await show_templates(cb, None)


@router.callback_query(F.data == "back_to_broadcast")
async def back_to_broadcast(cb: CallbackQuery, state: FSMContext):
    await start_broadcast(cb.message, state)
    await cb.answer()