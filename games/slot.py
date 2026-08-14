import asyncio
import logging
import random
from aiogram import F, types, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

from db import (
    get_winrate,
    has_claimed_gift,
    add_game_win,
    add_slot_session,
)
from db.wallet import add_to_balance, add_daily_game_win, get_available_game_win
from handlers.menu import main_menu
from handlers.config import ADMIN_ID

router = Router()
logging.basicConfig(level=logging.INFO)


class SlotGameFSM(StatesGroup):
    playing = State()


# Клавіатура, що показується ДО першого спіну (з кнопкою повернення)
def _bet_keyboard_with_back() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="1 купон"), KeyboardButton(text="2 купони")],
            [KeyboardButton(text="3 купони")],
            # [KeyboardButton(text="🔙 Повернутись до ігор")],
        ],
        resize_keyboard=True,
    )


# Клавіатура для наступних ставок, КОЛИ ГРА ВЖЕ РОЗПОЧАТА — без кнопки повернення
def _bet_keyboard_no_back() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="1 купон"), KeyboardButton(text="2 купони")],
            [KeyboardButton(text="3 купони")],
        ],
        resize_keyboard=True,
    )


# ====================== СТАРТ СЛОТІВ ======================
@router.message(F.text == "🎰 Слоти")
async def start_slots(message: types.Message, state: FSMContext):
    await state.set_state(SlotGameFSM.playing)
    await state.update_data(
        coupons=10,
        in_spin=False,
        started=False,   # гра ще не розпочата — кнопку "до ігор" можна показувати
    )

    await message.answer(
        f"<b>🎰 Слоти</b>\n\n"
        f"💎 Початковий баланс: <b>10 купонів</b>\n"
        f"Ціль — набрати <b>30 купонів</b>!\n\n"
        f"Обери ставку 👇",
        parse_mode="HTML",
        reply_markup=_bet_keyboard_with_back(),
    )


# ====================== ЛОГІКА СПІНУ ======================
@router.message(SlotGameFSM.playing)
async def slot_spin(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    text = message.text.strip()

    data = await state.get_data()
    started = data.get("started", False)

    if text == "🔙 Повернутись до ігор":
        # Якщо гравець вже зробив хоча б одну ставку — нікуди не випускаємо,
        # бо кнопки вже немає на клавіатурі, а цей текст міг прийти лише вручну.
        if started:
            return await message.answer(
                "⚠️ Гру вже розпочато. Дограй поточний раунд до виграшу або поразки."
            )

        # TODO: якщо у тебе є окреме меню ігор (наприклад games_menu),
        # підстав його тут замість main_menu — зараз веде у головне меню.
        gift_claimed = await has_claimed_gift(user_id)
        await message.answer(
            "🔙 Повертаємось у головне меню.",
            reply_markup=main_menu(
                is_admin=(user_id == ADMIN_ID),
                user_has_gift=gift_claimed
            )
        )
        await state.clear()
        return

    # Захист від подвійного натискання
    if data.get("in_spin", False):
        return await message.answer("⏳ Зачекайте, барабани ще крутяться...")

    try:
        bet = int(text.split()[0])
    except:
        return await message.answer("⚠️ Обери ставку з кнопок.")

    coupons = data.get("coupons", 10)

    if bet > coupons:
        return await message.answer("⚠️ Недостатньо купонів!")

    # Блокуємо спін і позначаємо гру як розпочату — з цього моменту
    # кнопка "🔙 Повернутись до ігор" більше не показується
    await state.update_data(in_spin=True, started=True)

    try:
        # === Winrate ===
        try:
            winrate = await get_winrate()
            if winrate > 1:
                winrate /= 100
        except:
            winrate = 0.33

        is_win = random.random() < winrate

        # === Символи та результат ===
        symbols = ["🍒", "🍋", "🍊", "🍇", "🍉", "🍓", "7️⃣"]

        if is_win:
            roll = random.random()
            if roll < 0.01:  # Джекпот
                sym = "7️⃣"
                reels = [sym, sym, sym]
                multiplier = 20
                outcome = "🎉 ДЖЕКПОТ! Три сімки — x20!"
            elif roll < 0.08:  # Дві сімки
                reels = ["7️⃣", "7️⃣", random.choice([s for s in symbols if s != "7️⃣"])]
                random.shuffle(reels)
                multiplier = 7
                outcome = "💎 Дві сімки — x7!"
            else:  # Пара фруктів
                fruit = random.choice([s for s in symbols if s != "7️⃣"])
                reels = [fruit, fruit, random.choice([s for s in symbols if s != fruit])]
                random.shuffle(reels)
                multiplier = 3
                outcome = f"✨ Пара {fruit} — x3!"
        else:
            reels = random.sample([s for s in symbols if s != "7️⃣"], 3)
            multiplier = 0
            outcome = "❌ Програш"

        win_amount = bet * multiplier
        coupons = coupons - bet + win_amount

        await state.update_data(coupons=coupons)

        # Анімація
        msg = await message.answer("🎰 Крутимо барабани...")
        for _ in range(4):
            spin = f"| {random.choice(symbols)} | {random.choice(symbols)} | {random.choice(symbols)} |"
            try:
                await msg.edit_text(f"🎲 {spin}")
            except:
                pass
            await asyncio.sleep(0.25)

        final_reels = f"| {reels[0]} | {reels[1]} | {reels[2]} |"
        await msg.edit_text(
            f"{final_reels}\n\n"
            f"{outcome}\n\n"
            f"💵 Ставка: {bet}\n"
            f"🏆 Виграш: {win_amount}\n"
            f"🎟 Баланс: <b>{coupons}</b>",
            parse_mode="HTML"
        )

        # === Перевірка закінчення гри ===
        if coupons <= 0:
            await add_slot_session(user_id, "loss", coupons)

            try:
                username = (
                    f"@{message.from_user.username}"
                    if message.from_user.username
                    else f"<a href='tg://user?id={user_id}'>{message.from_user.full_name}</a>"
                )
                await message.bot.send_message(
                    ADMIN_ID,
                    f"🎰 Гравець програв у 'Слоти'\n"
                    f"👤 {message.from_user.full_name} ({username})\n"
                    f"Результат: ПРОГРАВ",
                    parse_mode="HTML",
                )
            except Exception:
                pass

            gift_claimed = await has_claimed_gift(user_id)
            await message.answer(
                "💀 Ви програли всі купони!",
                reply_markup=main_menu(
                    is_admin=(user_id == ADMIN_ID),
                    user_has_gift=gift_claimed
                )
            )
            await state.clear()
            return

        if coupons >= 30:
            await add_slot_session(user_id, "win", coupons)

            # === НОВА СИСТЕМА ПЕРЕВІРКИ ВИГРАШУ ===
            payout = min(30, await get_available_game_win(user_id))

            if payout > 0:
                await add_to_balance(user_id, payout)
                await add_game_win(user_id)
                await add_daily_game_win(user_id, payout)
                from db.winlog import log_win

                await log_win(
                    message.from_user.id, message.from_user.username, message.from_user.full_name,
                    "game", "🎰 Слоти", payout
                )


                
                result_text = f"🎉 Вітаю! +{payout} грн нараховано на баланс!"
                admin_status = f" | +{payout} грн на баланс"
                if payout < 30:
                    result_text += f"\n💸 Решта {30 - payout} грн буде зарахована до депозиту"
                    admin_status += f" | +{30 - payout} грн до депозиту"
            else:
                result_text = "💸 Виграш 30 грн буде зарахований до депозиту"
                admin_status = " | +30 грн до депозиту"

            # Сповіщення адміністратору
            try:
                username = (
                    f"@{message.from_user.username}"
                    if message.from_user.username
                    else f"<a href='tg://user?id={user_id}'>{message.from_user.full_name}</a>"
                )
                await message.bot.send_message(
                    ADMIN_ID,
                    f"🎰 Гравець виграв у 'Слоти'\n"
                    f"👤 {message.from_user.full_name} ({username})\n"
                    f"Результат: ВИГРАВ{admin_status}",
                    parse_mode="HTML",
                )
            except Exception:
                pass

            gift_claimed = await has_claimed_gift(user_id)
            await message.answer(
                result_text,
                reply_markup=main_menu(
                    is_admin=(user_id == ADMIN_ID),
                    user_has_gift=gift_claimed
                )
            )
            await state.clear()
            return

        # Якщо гра продовжується — клавіатура БЕЗ кнопки "до ігор"
        await message.answer(
            f"🎟 Поточний баланс: <b>{coupons}</b> купонів\n"
            f"Обери наступну ставку 👇",
            parse_mode="HTML",
            reply_markup=_bet_keyboard_no_back(),
        )

    finally:
        # Знімаємо блокування спіну (started залишається True до кінця гри)
        await state.update_data(in_spin=False)
