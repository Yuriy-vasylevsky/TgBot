import asyncio
import logging
import random
from aiogram import F, types, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    KeyboardButton,
    ReplyKeyboardMarkup,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from db import (
    add_game_result,
    add_slot_session,
    get_user_access,
    get_winrate,
    has_claimed_gift,
)
from menu import main_menu
from config import ADMIN_ID
from db import increment_games_played

# після збереження результату сесії


router = Router()
logging.basicConfig(level=logging.INFO)


# ==============================
#   FSM стан гри
# ==============================
class SlotGameFSM(StatesGroup):
    playing = State()
    spinning = State()


# ==============================
#   Меню ігор
# ==============================
def games_menu():
    keyboard = [["🎰 Слоти"], ["🎯 Один з трьох"]]
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=b) for b in row] for row in keyboard],
        resize_keyboard=True,
    )


# ==============================
#   СТАРТ СЛОТІВ
# ==============================
@router.message(F.text == "🎰 Слоти")
async def start_slots(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID and not await get_user_access(
        message.from_user.id
    ):
        await message.answer("⛔ У вас немає доступу. Активуйте промокод!")
        return

    await state.set_state(SlotGameFSM.playing)
    await state.update_data(coupons=10, first_bet=False, slot_msg_id=None)

    text = (
        "🎰 <b>Ласкаво просимо у слот-машину!</b>\n\n"
        "💎 Твоя ціль — набити <b>30 купонів</b>! (1 🎟 = 1 грн)\n\n"
        "🎟 Початковий баланс: <b>10 купонів</b>.\n\n"
        "🎯 Обери ставку та крути барабани — удачі! 🍀"
    )

    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="▶️ Почати гру")],
            [KeyboardButton(text="ℹ️ Правила та комбінації")],
            [KeyboardButton(text="🔙 Повернутись до ігор")],
        ],
        resize_keyboard=True,
    )
    await message.answer(text, reply_markup=keyboard)


# ==============================
#   ПРАВИЛА
# ==============================
@router.message(F.text == "ℹ️ Правила та комбінації")
async def show_slot_rules(message: types.Message):
    rules = (
        "🎰 <b>Правила гри у слоти:</b>\n\n"
        "• Початковий баланс — <b>10 купонів</b>.\n"
        "• Обери ставку (1, 2 або 3 купони) та крути барабани.\n\n"
        "💥 3 однакових символи — ×12\n"
        "💎 3 сімки (7️⃣) — ×15\n"
        "🍀 2 сімки — ×7\n"
        "🔥 2 однакові символи — ×3\n"
        "✨ 1 сімка — ×1 (повертає ставку)\n\n"
        "❌ Якщо немає збігів — ставка згорає.\n\n"
        "🎯 Гра закінчується, коли:\n"
        "• Баланс = 0 — програв 💀\n"
        "• Баланс ≥ 30 — виграш 🏆"
    )
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="▶️ Почати гру")],
            [KeyboardButton(text="🔙 Повернутись до ігор")],
        ],
        resize_keyboard=True,
    )
    await message.answer(rules, reply_markup=keyboard)


# ==============================
#   ПОЧАТОК ГРИ
# ==============================
@router.message(F.text == "▶️ Почати гру")
async def enter_slot_game(message: types.Message, state: FSMContext):
    await show_slot_menu(message, state)


# ==============================
#   МЕНЮ СТАВОК
# ==============================
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

    msg = await message.answer(
        f"💰 Баланс: <b>{coupons}</b> 🎟\nОбери суму ставки:",
        reply_markup=ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True),
    )
    await state.update_data(slot_msg_id=msg.message_id)


# ==============================
#   ГОЛОВНА ЛОГІКА СПІНУ
# ==============================


@router.message(SlotGameFSM.playing)
async def slot_spin(message: types.Message, state: FSMContext):
    # перевірка, щоб не спамили кнопки під час анімації
    current_state = await state.get_state()
    if current_state == SlotGameFSM.spinning.state:
        return

    data = await state.get_data()
    coupons = data.get("coupons", 10)
    first_bet = data.get("first_bet", False)
    text = message.text.strip()

    if not first_bet and text == "🔙 Повернутись до ігор":
        await message.answer("🔹 Повертаємось у меню ігор.", reply_markup=games_menu())
        await state.clear()
        return

    try:
        bet = int(text.split()[0])
    except Exception:
        return await message.answer("⚠️ Виберіть ставку з кнопок.")

    if bet > coupons:
        return await message.answer("⚠️ Недостатньо купонів для цієї ставки.")

    if not first_bet:
        await state.update_data(first_bet=True)

    # встановлюємо стан обертання
    await state.set_state(SlotGameFSM.spinning)

    # --- Отримання winrate ---
    try:
        winrate = await get_winrate()
        if winrate > 1:
            winrate /= 100
    except Exception as e:
        logging.error(f"Помилка get_winrate: {e}")
        winrate = 0.33

    is_win = random.random() < winrate
    symbols = ["🍒", "🍋", "🍊", "🍇", "🍉", "🍓", "🍍", "🥭", "7️⃣"]

    # --- Формування комбінації ---
    if is_win:
        roll = random.random()
        if roll < 0.03:
            sym = random.choice(symbols)
            reels = [sym, sym, sym]
            multiplier = 20
            outcome = f"🎉 ТРИ {sym} — x20! Джекпот!"
        elif roll < 0.07:
            other = random.choice([s for s in symbols if s != "7️⃣"])
            reels = ["7️⃣", "7️⃣", other]
            random.shuffle(reels)
            multiplier = 7
            outcome = "💎 Подвійна удача! 2 сімки — x7!"
        else:
            fruit = random.choice([s for s in symbols if s != "7️⃣"])
            third = random.choice([s for s in symbols if s != fruit])  # ⚡ не той самий
            reels = [fruit, fruit, third]
            random.shuffle(reels)
            multiplier = 3
            outcome = f"✨ Пара {fruit} — x3!"
    else:
        reels = random.sample(symbols[:-1], 3)
        multiplier = 0
        outcome = "❌ Програш!"

    # --- Розрахунок ---
    win_amount = bet * multiplier
    coupons = coupons - bet + win_amount
    await state.update_data(coupons=coupons)

    # --- Анімація барабанів ---
    msg = await message.answer("🎰 Крутимо барабани...")
    last_text = None
    for _ in range(5):  # кілька кадрів плавної анімації
        spin = f"| {random.choice(symbols)} | {random.choice(symbols)} | {random.choice(symbols)} |"
        new_text = f"🎲 {spin}"
        if new_text != last_text:
            try:
                await msg.edit_text(new_text)
                last_text = new_text
            except Exception:
                pass
        await asyncio.sleep(0.1)

    # --- Показ фінального результату ---
    final_reels = f"| {reels[0]} | {reels[1]} | {reels[2]} |"
    result_text = (
        f"{final_reels}\n\n"
        f"{outcome}\n\n"
        f"💵 Ставка: {bet}\n"
        f"🏆 Виграш: {win_amount}\n"
        f"🎟 Баланс: <b>{coupons}</b>"
    )

    try:
        await msg.edit_text(result_text)
    except Exception:
        await message.answer(result_text)

    # --- Збереження результату ---
    try:
        await add_game_result("Слоти", multiplier > 0)
    except Exception as e:
        logging.error(f"Error saving slots result: {e}")

    # --- Кінець гри або продовження ---
    if coupons <= 0:
        gift_claimed = await has_claimed_gift(message.from_user.id)
        keyboard = main_menu(
            is_admin=(message.from_user.id == ADMIN_ID), user_has_gift=gift_claimed
        )
        await message.answer("💀 Ви програли всі купони!", reply_markup=keyboard)
        await message.bot.send_message(
            ADMIN_ID,
            f"💀 @{message.from_user.username or message.from_user.full_name} програв усі купони у слотах.",
        )
        await add_slot_session(message.from_user.id, "lose", 0)
        await state.clear()
        return

    if coupons >= 30:
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🏆 Champion",
                        callback_data=f"choose_reward:champion:{message.from_user.id}",
                    ),
                    InlineKeyboardButton(
                        text="🎰 Superomatic",
                        callback_data=f"choose_reward:superomatic:{message.from_user.id}",
                    ),
                ]
            ]
        )
        await message.answer("🎉 Вітаю! Ви виграли. Оберіть тип коду:", reply_markup=kb)
        await message.bot.send_message(
            ADMIN_ID,
            f"🏆 @{message.from_user.username or message.from_user.full_name} виграв {coupons} купонів у слотах!",
        )
        await add_slot_session(message.from_user.id, "win", coupons)
        await state.clear()
        return
    # 🧨 Гравець програв усі купони
    # 💀 Якщо гравець програв усі купони

    # --- Повертаємо меню ставок після результату ---
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="1 купон"), KeyboardButton(text="2 купони")],
            [KeyboardButton(text="3 купони")],
        ],
        resize_keyboard=True,
    )
    await message.answer("🎯 Оберіть наступну ставку:", reply_markup=keyboard)
    await state.set_state(SlotGameFSM.playing)
