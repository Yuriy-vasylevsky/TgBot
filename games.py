import asyncio
import random

from aiogram import F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup
from db import (
    add_game_result,
    add_slot_session,
    get_user_access,
    get_winrate,
    set_winrate,
    has_claimed_gift,
)


class CouponGameFSM(StatesGroup):
    playing = State()


class SlotGameFSM(StatesGroup):
    playing = State()


def games_menu():
    keyboard = [["🎰 Слоти"], ["🎯 Один з трьох"]]
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=b) for b in row] for row in keyboard],
        resize_keyboard=True,
    )


async def register_game_handlers(dp, bot, main_menu, ADMIN_ID):

    @dp.message(F.text == "🎯 Один з трьох")
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

    # --- Обробка вибору ---
    @dp.message(CouponGameFSM.playing)
    async def coupon_game_choice(message: types.Message, state: FSMContext):
        if message.text == "🔙 Повернутись до ігор":
            await message.answer(
                "🔹 Повертаємось у меню ігор.", reply_markup=games_menu()
            )
            await state.clear()
            return

        video_msg = await message.answer_video(
            types.FSInputFile("videos/loading.mp4"), caption="💫 Перевіряю..."
        )
        await asyncio.sleep(2)
        try:
            await bot.delete_message(
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
                "🎉 Вітаю! Ви виграли 30 грн! 💸\nАдмін сам напише і видасть код ✅"
            )
            outcome = "ВИГРАВ ✅"
        else:
            possible = [o for o in options if o != user_choice]
            winning_button = random.choice(possible)
            result_text = (
                f"❌ На жаль, ви програли.\nВиграш був у кнопці: {winning_button}"
            )
            outcome = "ПРОГРАВ ❌"

        # --- Повідомлення адміну ---
        await bot.send_message(
            ADMIN_ID,
            f"🎯 <b>Гравець зіграв у 'Один із трьох'</b>\n\n"
            f"👤 Ім'я: {message.from_user.full_name}\n"
            f"💬 Username: @{message.from_user.username or 'Немає'}\n"
            # f"🎲 Вибір: {user_choice}\n"
            f"📊 Winrate: {winrate * 100:.1f}%\n" f"🏁 Результат: {outcome}",
        )

        # --- Збереження результату ---
        try:
            await add_game_result("Один з трьох", is_win)
        except Exception as e:
            print("❌ Error saving game result:", e)

        # --- Результат користувачу ---
        # await message.answer(
        #     result_text + "\n\n🔙 Повертаємось у головне меню.",
        #     reply_markup=main_menu(is_admin=(message.from_user.id == ADMIN_ID)),
        # )

        gift_claimed = await has_claimed_gift(message.from_user.id)

        # Формуємо головне меню з актуальним станом подарунка
        keyboard = main_menu(
            is_admin=(message.from_user.id == ADMIN_ID), user_has_gift=gift_claimed
        )

        # Відповідь користувачу
        await message.answer(
            result_text + "\n\n🔙 Повертаємось у головне меню.", reply_markup=keyboard
        )
        await state.clear()

    # ===================== СЛОТИ =====================
    @dp.message(F.text == "🎰 Слоти")
    async def start_slots(message: types.Message, state: FSMContext):
        if message.from_user.id != ADMIN_ID and not await get_user_access(
            message.from_user.id
        ):
            await message.answer("⛔ У вас немає доступу. Активуйте промокод!")
            return

        await state.set_state(SlotGameFSM.playing)
        await state.update_data(coupons=10, first_bet=False)

        # 🧾 Гарний вступний опис гри
        await message.answer(
            "🎰 <b>Ласкаво просимо у слот-машину!</b>\n\n"
            "💎 Твоя ціль — набити 30купонів! (1 🎟  = 1 грн)\n\n"
            "🎟 Початковий баланс: <b>10 купонів</b>.\n\n"
            "Обирай ставку, крути барабани — і нехай удача буде з тобою 🍀\n\n",
            # "Натисни <b>ℹ️ Правила та комбінації</b>, щоб побачити виграшні варіанти:",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[
                    [KeyboardButton(text="▶️ Почати гру")],
                    [KeyboardButton(text="ℹ️ Правила та комбінації")],
                    [KeyboardButton(text="🔙 Повернутись до ігор")],
                ],
                resize_keyboard=True,
            ),
        )

    # Детальний опис правил
    @dp.message(F.text == "ℹ️ Правила та комбінації")
    async def show_slot_rules(message: types.Message):
        rules_text = (
            "🎰 <b>Правила гри у слоти:</b>\n\n"
            "• На початку ти маєш <b>10 купонів</b>.\n"
            "• Обери ставку (1, 2 або 3 купони) і крути барабани.\n"
            "• Отримуй виграш залежно від комбінації символів:\n\n"
            "💥 <b>3 однакових символи</b> — ×12 до ставки!\n"
            "💎 <b>3 сімки (7️⃣)</b> — ×15 (МЕГА-ДЖЕКПОТ)!\n"
            "🍀 <b>2 сімки</b> — ×7\n"
            "🔥 <b>2 однакові символи</b> — ×3\n"
            "✨ <b>1 сімка</b> — ×1 (повертає ставку)\n\n"
            "❌ Якщо жодного збігу — ставка згорає.\n\n"
            "🎯 Гра закінчується, коли:\n"
            "• Баланс падає до 0 купонів — ти програв 💀\n"
            "• Баланс досягає 30 купонів — ти отримуєш код в нашому казино 🏆\n\n"
            "🔹 Повернись до гри кнопкою нижче:"
        )
        await message.answer(
            rules_text,
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[
                    [KeyboardButton(text="▶️ Почати гру")],
                    [KeyboardButton(text="🔙 Повернутись до ігор")],
                ],
                resize_keyboard=True,
            ),
        )

    # Початок самої гри після перегляду опису
    @dp.message(F.text == "▶️ Почати гру")
    async def enter_slot_game(message: types.Message, state: FSMContext):
        await show_slot_menu(message, state)

    async def show_slot_menu(message: types.Message, state: FSMContext):
        data = await state.get_data()
        coupons = data.get("coupons", 10)
        first_bet = data.get("first_bet", False)

        keyboard = [
            [KeyboardButton(text="1 купон"), KeyboardButton(text="2 купони")],
            [KeyboardButton(text="3 купони")],
        ]
        if not first_bet:
            keyboard.append([KeyboardButton(text="🔙 Повернутись до ігор")])

        await message.answer(
            f"💰 Баланс: <b>{coupons}</b> 🎟\n" f"Обери суму ставки:",
            reply_markup=ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True),
        )

    @dp.message(SlotGameFSM.playing)
    async def slot_spin(message: types.Message, state: FSMContext):
        data = await state.get_data()
        coupons = data.get("coupons", 10)
        first_bet = data.get("first_bet", False)
        text = message.text.strip()

        if not first_bet and text == "🔙 Повернутись до ігор":
            await message.answer(
                "🔹 Повертаємось у меню ігор.", reply_markup=games_menu()
            )
            await state.clear()
            return

        try:
            bet = int(text.split()[0])
        except Exception:
            await message.answer("⚠️ Виберіть ставку з кнопок.")
            return

        if bet > coupons:
            await message.answer("⚠️ Недостатньо купонів для цієї ставки.")
            return

        if not first_bet:
            await state.update_data(first_bet=True)

        symbols = [
            "🍒",
            "🍋",
            "🍊",
            "🍇",
            "🍉",
            "🍓",
            "🍍",
            "🥭",
            "💎",
            "🃏",
            "7️⃣",
            "🍀",
        ]
        reels = [random.choice(symbols) for _ in range(3)]
        seven_count = reels.count("7️⃣")

        if reels[0] == reels[1] == reels[2]:
            multiplier = 12
            outcome = "🎉 Джекпот! 3 однакових символи!"
        else:
            has_pair = (
                reels[0] == reels[1] or reels[1] == reels[2] or reels[0] == reels[2]
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

        try:
            await add_game_result("Слоти", multiplier > 0)
        except Exception as e:
            print("Error saving slots game stat:", e)
        if coupons <= 0:
            # 🔍 Перевіряємо, чи користувач уже отримав подарунок
            gift_claimed = await has_claimed_gift(message.from_user.id)

            # 🧭 Формуємо головне меню відповідно до стану подарунка
            keyboard = main_menu(
                is_admin=(message.from_user.id == ADMIN_ID), user_has_gift=gift_claimed
            )

            await message.answer(
                "💀 Ви програли всі купони! Гра завершена.",
                reply_markup=keyboard,
            )

            await bot.send_message(
                ADMIN_ID,
                f"💀 @{message.from_user.username or message.from_user.full_name} програв усі купони в слотах.",
            )

            await add_slot_session(message.from_user.id, "lose", coupons)
            await state.clear()
            return

        if coupons >= 30:
            await message.answer(
                "🎉 Ви досягли максимального виграшу (30 купонів)! Гра завершена 🎯",
                reply_markup=main_menu(is_admin=(message.from_user.id == ADMIN_ID)),
            )
            await bot.send_message(
                ADMIN_ID,
                f"🏆 @{message.from_user.username or message.from_user.full_name} виграв {coupons} купонів у слотах (максимум).",
            )
            await add_slot_session(message.from_user.id, "win", coupons)
            await state.clear()
            return

        await show_slot_menu(message, state)
