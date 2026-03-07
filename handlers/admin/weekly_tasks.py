import aiosqlite
from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from db import add_weekly_task, get_active_tasks, DB_PATH
from handlers.menu import main_menu
from handlers.config import ADMIN_ID

router = Router(name="admin_weekly_tasks")


class TaskFSM(StatesGroup):
    waiting_title = State()
    waiting_description = State()
    waiting_reward = State()
    waiting_duration = State()


# ===============================
#   Створення тижневого завдання
# ===============================
@router.message(F.text == "🗓 Додати тижневе завдання")
async def ask_task_title(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer("📝 Введіть назву завдання:")
    await state.set_state(TaskFSM.waiting_title)


@router.message(TaskFSM.waiting_title)
async def ask_task_description(message: types.Message, state: FSMContext):
    await state.update_data(title=message.text)
    await message.answer("📖 Введіть опис завдання:")
    await state.set_state(TaskFSM.waiting_description)


@router.message(TaskFSM.waiting_description)
async def ask_task_reward(message: types.Message, state: FSMContext):
    await state.update_data(description=message.text)
    await message.answer("🎁 Введіть нагороду за виконання:")
    await state.set_state(TaskFSM.waiting_reward)


@router.message(TaskFSM.waiting_reward)
async def ask_task_duration(message: types.Message, state: FSMContext):
    await state.update_data(reward=message.text)
    await message.answer(
        "⏰ Вкажіть час на виконання (наприклад: 7 днів, до неділі, або дата):"
    )
    await state.set_state(TaskFSM.waiting_duration)


@router.message(TaskFSM.waiting_duration)
async def save_task(message: types.Message, state: FSMContext):
    data = await state.get_data()
    await add_weekly_task(
        data["title"],
        data["description"],
        data["reward"],
        message.text,
    )
    await state.clear()
    await message.answer(
        "✅ Завдання успішно додано!", reply_markup=main_menu(is_admin=True)
    )


# ===============================
#   Видалення тижневого завдання
# ===============================
@router.message(F.text == "🗑 Видалити завдання")
async def show_tasks_to_delete(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    tasks = await get_active_tasks()
    if not tasks:
        await message.answer("ℹ️ Немає активних тижневих завдань для видалення.")
        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"{t['title'][:40]} 🗑", callback_data=f"delete_task:{t['id']}"
                )
            ]
            for t in tasks
        ]
    )

    await message.answer(
        "🗓 <b>Активні тижневі завдання:</b>\nНатисніть на завдання, щоб видалити його.",
        reply_markup=keyboard,
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("delete_task:"))
async def delete_selected_task(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Тільки для адміна", show_alert=True)
        return

    task_id = int(callback.data.split(":")[1])
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM weekly_tasks WHERE id = ?", (task_id,))
        await db.execute("DELETE FROM user_tasks WHERE task_id = ?", (task_id,))
        await db.commit()

    await callback.message.edit_text(
        f"✅ Завдання <b>ID {task_id}</b> видалено.", parse_mode="HTML"
    )
    await callback.answer("Завдання видалено!")