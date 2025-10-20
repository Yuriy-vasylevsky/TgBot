import asyncio
import random
from aiogram import F, types, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

from db import add_game_result, get_winrate, has_claimed_gift
from menu import main_menu
from config import ADMIN_ID

router = Router()


class CouponGameFSM(StatesGroup):
    playing = State()


def games_menu():
    keyboard = [["🎰 Слоти"], ["🎯 Один з трьох"]]
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=b) for b in row] for row in keyboard],
        resize_keyboard=True,
    )


@router.message(F.text == "🎯 Один з трьох")
async def start_coupon_game(message: types.Message, state: FSMContext):
    buttons = [
        [types.KeyboardButton(text="🎁 Варіант 1")],
        [types.KeyboardButton(text="🎁 Варіант 2")],
        [types.KeyboardButton(text="🎁 Варіант 3")],
        [types.KeyboardButton(text="🔙 Повернутись до ігор")],
    ]
    keyboard = types.ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
    await message.answer(
        "🎯 <b>Один з трьох!</b>\n\n"
        "Правила прості:\n"
        "👉 Є три варіанти, лише один виграшний.\n"
        "👉 Якщо пощастить — виграєш купон 💸\n\n"
        "🔹 Обери свій варіант:",
        reply_markup=keyboard,
    )
    await state.set_state(CouponGameFSM.playing)


@router.message(CouponGameFSM.playing)
async def coupon_game_choice(message: types.Message, state: FSMContext):
    if message.text == "🔙 Повернутись до ігор":
        await message.answer("🔹 Повертаємось у меню ігор.", reply_markup=games_menu())
        await state.clear()
        return

    video_msg = await message.answer_video(
        types.FSInputFile("videos/loading.mp4"), caption="💫 Перевіряю..."
    )
    await asyncio.sleep(2)
    try:
        await message.bot.delete_message(
            chat_id=message.chat.id, message_id=video_msg.message_id
        )
    except Exception as e:
        print("⚠️ Не вдалося видалити відео:", e)

    # --- Отримуємо актуальний winrate ---
    try:
        winrate = await get_winrate()  # повинно повертати float від 0 до 1
        if winrate > 1:  # якщо зберігаєш як 0–100
            winrate = winrate / 100
    except Exception as e:
        print("❌ Помилка get_winrate:", e)
        winrate = 0.33  # запасне значення

    # Ймовірність виграшу
    is_win = random.random() < winrate

    options = ["🎁 Варіант 1", "🎁 Варіант 2", "🎁 Варіант 3"]
    user_choice = message.text.strip()

    if is_win:
        winning_button = user_choice
        result_text = (
            "🎉 Вітаю! Ви виграли 30 грн! 💸\nОберіть, який тип коду бажаєте отримати:"
        )
        outcome = "ВИГРАВ ✅"

        # Кнопки для отримання виграшу
        kb = types.InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    types.InlineKeyboardButton(
                        text="🏆 Champion",
                        callback_data=f"choose_reward:champion:{message.from_user.id}",
                    ),
                    types.InlineKeyboardButton(
                        text="🎰 Superomatic",
                        callback_data=f"choose_reward:superomatic:{message.from_user.id}",
                    ),
                ]
            ]
        )
        await message.answer(result_text, reply_markup=kb)

    else:
        possible = [o for o in options if o != user_choice]
        winning_button = random.choice(possible)
        result_text = f"❌ На жаль, ви програли.\nВиграш був у кнопці: {winning_button}"
        outcome = "ПРОГРАВ ❌"
        await message.answer(result_text)

    # --- Повідомлення адміну ---
    await message.bot.send_message(
        ADMIN_ID,
        f"🎯 <b>Гравець зіграв у 'Один із трьох'</b>\n\n"
        f"👤 Ім'я: {message.from_user.full_name}\n"
        f"💬 Username: @{message.from_user.username or 'Немає'}\n"
        f"📊 Winrate: {winrate * 100:.1f}%\n"
        f"🏁 Результат: {outcome}",
    )

    # --- Збереження результату ---
    try:
        await add_game_result("Один з трьох", is_win)
    except Exception as e:
        print("❌ Error saving game result:", e)

    # --- Перевірка подарунка та формування головного меню ---
    gift_claimed = await has_claimed_gift(message.from_user.id)
    keyboard = main_menu(
        is_admin=(message.from_user.id == ADMIN_ID), user_has_gift=gift_claimed
    )

    # --- Відповідь користувачу ---
    if not is_win:
        await message.answer(
            result_text + "\n\n🔙 Повертаємось у головне меню.",
            reply_markup=keyboard,
        )
    await state.clear()
