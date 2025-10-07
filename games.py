import random
import re
from aiogram import types, F
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from db import (
    get_user_access, add_game_result,
    add_slot_session
)



# FSM для ігор (локально в цьому модулі)
class CouponGameFSM(StatesGroup):
    playing = State()

class SlotGameFSM(StatesGroup):
    playing = State()

def games_menu():
    keyboard = [
        [ "🎰 Слоти"],
        [ "🎯 Один з трьох"]
        # ["🔙 Назад до головного меню"]
    ]
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=b) for b in row] for row in keyboard],
        resize_keyboard=True
    )

async def register_game_handlers(dp, bot, main_menu, ADMIN_ID):
    """
    Реєструє хендлери ігор на переданий Dispatcher.
    main_menu — callable main_menu(is_admin: bool) -> ReplyKeyboardMarkup
    """
    # --- Купон ---
    @dp.message(F.text == "🎯 Один з трьох")
    async def start_coupon_game(message: types.Message, state: FSMContext):
        if not await get_user_access(message.from_user.id):
            await message.answer("⛔ У вас немає доступу. Активуйте промокод!")
            return

        await state.set_state(CouponGameFSM.playing)
        await message.answer(
            "🎯 <b>Гра Купон!</b>\n\n"
            "Правила прості:\n"
            "У тебе є 3 кнопки. Лише одна виграшна ✅\n"
            "Можна грати тільки один раз.\n\n"
            "Обери свій варіант:",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[
                    [KeyboardButton(text="🎁 Варіант 1")],
                    [KeyboardButton(text="🎁 Варіант 2")],
                    [KeyboardButton(text="🎁 Варіант 3")],
                ],
                resize_keyboard=True
            )
        )

    @dp.message(CouponGameFSM.playing)
    async def coupon_game_choice(message: types.Message, state: FSMContext):
        winning_button = random.choice(["🎁 Варіант 1", "🎁 Варіант 2", "🎁 Варіант 3"])
        user_choice = message.text

        if user_choice == winning_button:
            result_text = "🎉 Вітаю! Ви виграли 30 грн! Адмін вам сам напише і видасть код✅"
            outcome = "ВИГРАВ ✅"
            is_win = True
        else:
            result_text = f"❌ На жаль, ви програли.\nВиграш був у кнопці: {winning_button}"
            outcome = "ПРОГРАВ ❌"
            is_win = False

        # повідомляємо адміна у будь-якому випадку
        await bot.send_message(
            ADMIN_ID,
            f"🎯 Гравець зіграв у 'Гра Купон'\n\n"
            f"ID: {message.from_user.id}\n"
            f"Username: @{message.from_user.username or '---'}\n"
            f"Ім'я: {message.from_user.full_name}\n"
            f"Вибір: {user_choice}\n"
            f"Результат: {outcome}"
        )

        # Запис результату в БД (агрегована статистика по грі "Купон")
        try:
            await add_game_result("Купон", is_win)
        except Exception as e:
            # логування у головному модулі може обробити
            print("Error saving coupon game stat:", e)

        await message.answer(
            result_text + "\n\n🔙 Повертаємось у головне меню.",
            reply_markup=main_menu(is_admin=(message.from_user.id == ADMIN_ID))
        )
        await state.clear()

    # --- Слоти ---
    @dp.message(F.text == "🎰 Слоти")
    async def start_slots(message: types.Message, state: FSMContext):
        if not await get_user_access(message.from_user.id):
            await message.answer("⛔ У вас немає доступу. Активуйте промокод!")
            return

        await state.set_state(SlotGameFSM.playing)
        await state.update_data(coupons=10)
        await show_slot_menu(message, state)

    async def show_slot_menu(message: types.Message, state: FSMContext):
        data = await state.get_data()
        coupons = data.get("coupons", 10)

        await message.answer(
            f"Баланс: <b>{coupons}</b> 🎟 \n",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[
                    [KeyboardButton(text="1 купон"), KeyboardButton(text="2 купони")],
                    [ KeyboardButton(text="3 купони")],
                ],
                resize_keyboard=True
            )
        )

    @dp.message(SlotGameFSM.playing)
    async def slot_spin(message: types.Message, state: FSMContext):
        text = (message.text or "").strip()

        # Вихід
        if text == "🔙 Вийти з гри":
            await message.answer("❌ Ви вийшли з гри.", reply_markup=main_menu(is_admin=(message.from_user.id == ADMIN_ID)))
            await state.clear()
            return

        # Забрати виграш
        if text == "💰 Забрати виграш":
            data = await state.get_data()
            coupons = data.get("coupons", 10)
            await message.answer(f"💰 Ви забрали {coupons} купонів!", reply_markup=main_menu(is_admin=(message.from_user.id == ADMIN_ID)))
            await bot.send_message(
                ADMIN_ID,
                f"👤 <b>@{message.from_user.username or message.from_user.full_name}</b> забрав {coupons} купонів у слотах 🎰"
            )
            await state.clear()
            return

        # Обробка ставки
        try:
            bet = int(text.split()[0])
        except Exception:
            await message.answer("⚠️ Виберіть ставку з кнопок.")
            return

        data = await state.get_data()
        coupons = data.get("coupons", 10)

        if bet > coupons:
            await message.answer("⚠️ Недостатньо купонів для цієї ставки.")
            return

        # Символи
        symbols = ["🍒", "🍋", "🍊", "🍇", "🍉", "🍓", "🍍", "🥭",  "💎","🃏", "7️⃣", "🍀" ]
        reels = [random.choice(symbols) for _ in range(3)]

        seven_count = reels.count("7️⃣")

        # Перевірка на три однакових символи (включно з трьома 7️⃣)
        if reels[0] == reels[1] == reels[2]:
            multiplier = 12
            outcome = "🎉 Джекпот! 3 однакових символи!"
        else:
            has_pair = (
                reels[0] == reels[1]
                or reels[1] == reels[2]
                or reels[0] == reels[2]
            )

            if seven_count == 3:
                seven_multiplier = 15
                seven_text = "🔥 Три 7️⃣! МЕГА-ЩАСТЯ!"
            elif seven_count == 2:
                seven_multiplier = 7
                seven_text = "💎 Подвійна удача! 2 сімки!"
            elif seven_count == 1:
                seven_multiplier = 1
                seven_text = "🍀 Щаслива 7️⃣!"
            else:
                seven_multiplier = 0
                seven_text = ""

            if has_pair:
                pair_multiplier = 3
                if pair_multiplier >= seven_multiplier:
                    multiplier = pair_multiplier
                    outcome = "✨ Є пара символів!"
                else:
                    multiplier = seven_multiplier
                    outcome = seven_text
            else:
                multiplier = seven_multiplier
                outcome = seven_text if seven_text else "❌ Програш!"

        win_amount = int(bet * multiplier)
        coupons = coupons - bet + win_amount

        await state.update_data(coupons=coupons)

        await message.answer(
            f"| {reels[0]} | {reels[1]} | {reels[2]} |\n\n"
            f"{outcome}\n"
            f"Ставка: {bet}\n"
            f"Виграш: {win_amount}\n"
        )

        # Записуємо результат у статистику по грі "Слоти" (агрегована)
        try:
            await add_game_result("Слоти", multiplier > 0)
        except Exception as e:
            print("Error saving slots game stat:", e)

        # Програш (0 купонів) -> запис партії як 'lose'
        if coupons <= 0:
            try:
                await add_slot_session(message.from_user.id, "lose", coupons)
            except Exception as e:
                print("Error saving slot session (lose):", e)

            await message.answer("💀 Ви програли всі купони! Гра завершена.", reply_markup=main_menu(is_admin=(message.from_user.id == ADMIN_ID)))
            await bot.send_message(
                ADMIN_ID,
                f"💀 <b>@{message.from_user.username or message.from_user.full_name}</b> програв усі купони в слотах."
            )
            await state.clear()
            return

        # Перемога (30 купонів) -> запис партії як 'win'
        if coupons >= 30:
            try:
                await add_slot_session(message.from_user.id, "win", coupons)
            except Exception as e:
                print("Error saving slot session (win):", e)

            await message.answer("🎉 Ви досягли максимального виграшу (30 купонів)! Гра завершена 🎯", reply_markup=main_menu(is_admin=(message.from_user.id == ADMIN_ID)))
            await bot.send_message(
                ADMIN_ID,
                f"🏆 <b>@{message.from_user.username or message.from_user.full_name}</b> виграв {coupons} купонів у слотах (досяг максимуму)."
            )
            await state.clear()
            return

        # Якщо ще не кінець — показати меню знову
        await show_slot_menu(message, state)



