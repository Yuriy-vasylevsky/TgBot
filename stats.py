from aiogram import Router, F, types
from aiogram.utils.keyboard import InlineKeyboardBuilder

# from db import get_all_stats, get_slot_session_stats, clear_game_stats
from db import (
    get_all_stats,
    get_slot_session_stats,
    get_blackjack_session_stats,
    clear_game_stats,
)

import config

router = Router()
ADMIN_ID = config.ADMIN_ID


@router.message(F.text == "📊 Статистика")
async def show_stats(message: types.Message):
    # --- Отримуємо статистику з бази ---
    stats = await get_all_stats()
    total_slots, wins_slots = await get_slot_session_stats()
    total_blackjack, wins_blackjack = await get_blackjack_session_stats()

    text = "<b>📊 Загальна статистика ігор</b>\n\n"

    # --- Глобальні підрахунки ---
    total_sessions = 0
    total_wins = 0

    # 🎯 Один з трьох
    total_guess = 0
    wins_guess = 0
    for game_name, total_games, wins in stats:
        if game_name.lower() in ["один з трьох", "one of three", "1 of 3"]:
            total_guess += total_games
            wins_guess += wins

    total_sessions += total_guess + total_slots + total_blackjack
    total_wins += wins_guess + wins_slots + wins_blackjack

    # --- Виводимо детально кожну гру ---
    if total_guess > 0:
        rate_guess = wins_guess / total_guess * 100
        text += (
            f"🎯 <b>Один з трьох</b>\n"
            f"🔹 Сесій: {total_guess}\n"
            f"🔹 Виграно: {wins_guess}\n"
            f"🔹 Відсоток перемог: {rate_guess:.1f}%\n\n"
        )

    if total_slots > 0:
        slot_rate = wins_slots / total_slots * 100
        text += (
            f"🎰 <b>Слоти</b>\n"
            f"🔹 Сесій: {total_slots}\n"
            f"🔹 Виграно: {wins_slots}\n"
            f"🔹 Відсоток перемог: {slot_rate:.1f}%\n\n"
        )

    if total_blackjack > 0:
        blackjack_rate = wins_blackjack / total_blackjack * 100
        text += (
            f"🃏 <b>Blackjack</b>\n"
            f"🔹 Сесій: {total_blackjack}\n"
            f"🔹 Виграно: {wins_blackjack}\n"
            f"🔹 Відсоток перемог: {blackjack_rate:.1f}%\n\n"
        )

    # 🌍 --- Глобальна статистика по сесіях ---
    if total_sessions > 0:
        global_rate = total_wins / total_sessions * 100
        text += (
            "🌍 <b>Глобальна статистика</b>\n"
            f"🔹 Усього сесій: <b>{total_sessions}</b>\n"
            f"🔹 Виграно: <b>{total_wins}</b>\n"
            f"🔹 Середній відсоток перемог: <b>{global_rate:.1f}%</b>\n\n"
        )

        # 💰 --- ФІНАНСОВА СТАТИСТИКА ---
        total_paid = total_wins * 30
        price_per_coupon = total_paid / total_sessions if total_sessions > 0 else 0

        text += (
            "💰 <b>Фінансова статистика</b>\n"
            f"🔹 Заплачено грошей: <b>{total_paid:,}</b>\n"
            f"🔹 Ціна за купон: <b>{price_per_coupon:.2f}</b>\n"
        )
    else:
        text += "Немає даних для відображення."

    # --- Кнопка очищення тільки для адміна ---
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
