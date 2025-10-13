from aiogram import Router, F, types
from aiogram.utils.keyboard import InlineKeyboardBuilder
from db import get_all_stats, get_slot_session_stats, clear_game_stats
import config

router = Router()
ADMIN_ID = config.ADMIN_ID


@router.message(F.text == "📊 Статистика")
async def show_stats(message: types.Message):
    stats = await get_all_stats()
    total_slots, wins_slots = await get_slot_session_stats()

    text = "<b>📊 Загальна статистика ігор</b>\n\n"

    if not stats and total_slots == 0:
        text += "Немає даних для відображення."
    else:
        for game_name, total_games, wins in stats:
            win_rate = (wins / total_games * 100) if total_games > 0 else 0
            text += (
                f"🎮 <b>{game_name}</b>\n"
                f"🔹 Ігор: {total_games}\n"
                f"🔹 Виграшів: {wins}\n"
                f"🔹 Відсоток перемог: {win_rate:.1f}%\n\n"
            )

        if total_slots > 0:
            slot_rate = (wins_slots / total_slots * 100) if total_slots > 0 else 0
            text += (
                f"🎰 <b>Вінрейт слотів</b>\n"
                f"🔹 Ігор: {total_slots}\n"
                f"🔹 Виграшів: {wins_slots}\n"
                f"🔹 Відсоток перемог: {slot_rate:.1f}%\n"
            )

    # --- Кнопка очищення тільки для адміна
    kb = InlineKeyboardBuilder()
    if message.from_user.id == ADMIN_ID:
        kb.button(text="🧹 Очистити статистику", callback_data="confirm_clear_stats")
    kb.adjust(1)

    await message.answer(text, parse_mode="HTML", reply_markup=kb.as_markup())


# ========================
# Підтвердження очищення
# ========================
@router.callback_query(F.data == "confirm_clear_stats")
async def confirm_clear_stats(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Лише для адміністратора.", show_alert=True)
        return

    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Так, очистити", callback_data="do_clear_stats")
    kb.button(text="❌ Скасувати", callback_data="cancel_clear_stats")
    kb.adjust(2)

    await callback.message.answer(
        "⚠️ Ви впевнені, що хочете очистити усю статистику ігор?",
        reply_markup=kb.as_markup(),
    )
    await callback.answer()


# ========================
# Виконання очищення
# ========================
@router.callback_query(F.data == "do_clear_stats")
async def do_clear_stats(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Лише для адміністратора.", show_alert=True)
        return

    try:
        await clear_game_stats()
        await callback.message.answer("✅ Уся статистика успішно очищена.")
    except Exception as e:
        await callback.message.answer(f"⚠️ Помилка при очищенні статистики: {e}")
    await callback.answer()


# ========================
# Скасування очищення
# ========================
@router.callback_query(F.data == "cancel_clear_stats")
async def cancel_clear_stats(callback: types.CallbackQuery):
    await callback.message.answer("❌ Очищення скасовано.")
    await callback.answer()
