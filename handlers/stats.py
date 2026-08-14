from aiogram import Router, F, types
from aiogram.utils.keyboard import InlineKeyboardBuilder

# from db import get_all_stats, get_slot_session_stats, clear_game_stats
from db import (
    get_all_stats,
    get_slot_session_stats,
    get_blackjack_session_stats,
    clear_game_stats,
)

import handlers.config as config
from db import get_total_money_won  # зверху

router = Router()
ADMIN_ID = config.ADMIN_ID

ONE_OF_THREE_NAMES = {
    "один з трьох",
    "один із трьох",
    "one of three",
    "1 of 3",
    "1 з 3",
}


def _game_stats_text(icon: str, name: str, total: int, wins: int) -> str:
    win_rate = wins / total * 100 if total else 0
    return (
        f"{icon} <b>{name}</b>\n"
        f"🔹 Усього ігор: {total}\n"
        f"🔹 Виграшних: {wins}\n"
        f"🔹 Відсоток перемог: {win_rate:.1f}%\n\n"
    )


@router.message(F.text == "📊 Статистика")
async def show_stats(message: types.Message):
    # --- Отримуємо статистику з бази ---
    stats = await get_all_stats()
    total_slots, wins_slots = await get_slot_session_stats()
    total_blackjack, wins_blackjack = await get_blackjack_session_stats()

    text = "<b>📊 Статистика ігор</b>\n\n"

    # --- Глобальні підрахунки ---
    total_sessions = 0
    total_wins = 0

    # 🎯 Один з трьох
    total_guess = 0
    wins_guess = 0
    for game_name, total_games, wins in stats:
        if game_name.strip().lower() in ONE_OF_THREE_NAMES:
            total_guess += total_games
            wins_guess += wins

    total_sessions += total_guess + total_slots + total_blackjack
    total_wins += wins_guess + wins_slots + wins_blackjack

    # --- Виводимо кожну гру, навіть якщо для неї ще немає результатів ---
    text += _game_stats_text("🎰", "Слоти", total_slots, wins_slots)
    text += _game_stats_text("🃏", "Blackjack", total_blackjack, wins_blackjack)
    text += _game_stats_text("🎯", "Один з трьох", total_guess, wins_guess)

    # 🌍 --- Глобальна статистика по сесіях ---
    global_rate = total_wins / total_sessions * 100 if total_sessions else 0
    text += (
        "🌍 <b>Загальна статистика всіх ігор</b>\n"
        f"🔹 Усього ігор: <b>{total_sessions}</b>\n"
        f"🔹 Виграшних: <b>{total_wins}</b>\n"
        f"🔹 Відсоток перемог: <b>{global_rate:.1f}%</b>\n\n"
    )

    if total_sessions > 0:

        # 💰 --- ФІНАНСОВА СТАТИСТИКА ---
        total_paid = total_wins * 30
        price_per_coupon = total_paid / total_sessions if total_sessions > 0 else 0
        total_money_won = await get_total_money_won()
        earned_money = (
            total_sessions * 0.8 * 200 - total_money_won - total_paid
        )  # зароблено
        text += (
            "💰 <b>Фінансова статистика</b>\n"
            f"🔹 Витрачено на PROMO: <b>{total_paid:,}</b>\n"
            f"🔹 Виграно в 🎡: <b>{total_money_won:,}</b>\n"
            f"🔹 Ціна за 1 PROMO: <b>{price_per_coupon:.2f}</b>\n\n"
            f"🔹 Зароблено грошей: <b>{earned_money:,}</b>\n"
        )

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
