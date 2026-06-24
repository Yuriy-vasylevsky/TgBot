# import asyncio
# import random
# from aiogram import F, types, Router
# from aiogram.fsm.context import FSMContext
# from aiogram.fsm.state import State, StatesGroup
# from aiogram.types import (
#     KeyboardButton,
#     ReplyKeyboardMarkup,
#     InlineKeyboardMarkup,
#     InlineKeyboardButton,
# )

# from db import (
#     add_game_result,
#     has_claimed_gift,
#     add_blackjack_session,
#     save_notification,
#     add_game_win,
# )
# from handlers.menu import main_menu
# from handlers.config import ADMIN_ID

# router = Router()


# # ================== FSM ==================
# class BlackjackFSM(StatesGroup):
#     choosing_bet = State()
#     in_round = State()


# # ================== Deck & Values ==================
# SUITS = ["♠️", "♥️", "♦️", "♣️"]
# RANKS = ["A", "K", "Q", "J", "10", "9", "8", "7", "6", "5", "4", "3", "2"]
# DECK_TEMPLATE = [f"{r}{s}" for s in SUITS for r in RANKS]
# VALUES = {"A": 11, "K": 10, "Q": 10, "J": 10, **{str(n): n for n in range(2, 11)}}


# # ================== Utility ==================
# def calc_total(cards: list[str]) -> int:
#     total = sum(VALUES.get("".join(ch for ch in c if ch.isalnum()), 0) for c in cards)
#     aces = sum(1 for c in cards if "A" in c)
#     while total > 21 and aces:
#         total -= 10
#         aces -= 1
#     return total


# def show_cards(cards: list[str]) -> str:
#     return "  ".join(cards)


# # ================== UI ==================
# def games_menu_markup():
#     return ReplyKeyboardMarkup(
#         keyboard=[
#             [KeyboardButton(text="🎰 Слоти")],
#             [KeyboardButton(text="🎯 Один з трьох")],
#             [KeyboardButton(text="🃏 Blackjack")],
#         ],
#         resize_keyboard=True,
#     )


# def bet_keyboard(balance: int, show_menu_button: bool = True):
#     """Генерує клавіатуру ставок, без кнопки меню після першої ставки."""
#     buttons = []
#     if balance >= 5:
#         buttons.append(KeyboardButton(text="💵 5 купонів"))
#     if balance >= 10:
#         buttons.append(KeyboardButton(text="💰 10 купонів"))

#     keyboard = [buttons]
#     if show_menu_button:
#         keyboard.append([KeyboardButton(text="🔙 В меню")])

#     return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


# def in_game_keyboard():
#     return ReplyKeyboardMarkup(
#         keyboard=[
#             [KeyboardButton(text="➕ Взяти ще"), KeyboardButton(text="🛑 Досить")]
#         ],
#         resize_keyboard=True,
#     )


# # ================== START ==================
# @router.message(F.text == "🃏 Blackjack")
# async def cmd_blackjack(message: types.Message, state: FSMContext):
#     await state.clear()
#     await state.update_data(balance=10, first_round=True)
#     await message.answer(
#         "🃏 <b>Blackjack (21)</b>\n\n"
#         "🎯 Мета — бути ближче до 21, ніж дилер.\n"
#         "💰 Стартовий баланс: <b>10 купонів</b>.\n\n"
#         "📈 Досягни 30 — виграєш 🎁\n"
#         "📉 0 — гра завершиться ❌\n\n"
#         "Оберіть ставку:",
#         reply_markup=bet_keyboard(10, show_menu_button=True),
#         parse_mode="HTML",
#     )
#     await state.set_state(BlackjackFSM.choosing_bet)


# # ================== BET ==================
# @router.message(BlackjackFSM.choosing_bet)
# async def handle_bet_choice(message: types.Message, state: FSMContext):
#     text = message.text.strip()
#     data = await state.get_data()
#     balance = data.get("balance", 10)
#     first_round = data.get("first_round", True)

#     if text == "🔙 В меню" and first_round:
#         await message.answer(
#             "🔙 Повертаємось у меню ігор.", reply_markup=games_menu_markup()
#         )
#         await state.clear()
#         return

#     if text not in ("💵 5 купонів", "💰 10 купонів"):
#         return

#     bet = 5 if "5" in text else 10
#     if bet > balance:
#         await message.answer("⚠️ Недостатньо купонів.")
#         return

#     # Формуємо колоду
#     deck = DECK_TEMPLATE.copy()
#     random.shuffle(deck)
#     user_cards = [deck.pop(), deck.pop()]
#     dealer_cards = [deck.pop(), deck.pop()]

#     await state.update_data(
#         deck=deck,
#         user_cards=user_cards,
#         dealer_cards=dealer_cards,
#         bet=bet,
#         first_round=False,  # після першої ставки
#     )

#     user_total = calc_total(user_cards)
#     dealer_show = dealer_cards[0]

#     if user_total == 21:
#         await message.answer("🖤 Blackjack!")
#         return await finish_round(message, state, busted=False)

#     await message.answer(
#         f"💵 Ставка: <b>{bet} купонів</b>\n\n"
#         f"🧑‍🎓 <b>Твої карти:</b> {show_cards(user_cards)}  =  <b>{user_total}</b>\n"
#         f"🤵‍♂️ <b>Карта дилера:</b> {dealer_show} ❓",
#         parse_mode="HTML",
#         reply_markup=in_game_keyboard(),
#     )
#     await state.set_state(BlackjackFSM.in_round)


# # ================== IN ROUND ==================
# @router.message(BlackjackFSM.in_round)
# async def in_round_handler(message: types.Message, state: FSMContext):
#     text = message.text.strip()
#     data = await state.get_data()
#     deck = data["deck"]
#     user_cards = data["user_cards"]
#     bet = data["bet"]

#     if text == "➕ Взяти ще":
#         if not deck:
#             deck = DECK_TEMPLATE.copy()
#             random.shuffle(deck)
#         card = deck.pop()
#         user_cards.append(card)
#         await state.update_data(deck=deck, user_cards=user_cards)
#         user_total = calc_total(user_cards)
#         await message.answer(
#             f"🃏 Ти взяв: {card}\n"
#             f"Твої карти: {show_cards(user_cards)} = <b>{user_total}</b>",
#             parse_mode="HTML",
#         )
#         if user_total > 21:
#             await finish_round(message, state, busted=True)
#         return

#     if text == "🛑 Досить":
#         await finish_round(message, state, busted=False)
#         return


# # ================== FINISH ROUND ==================
# async def finish_round(message: types.Message, state: FSMContext, busted: bool):
#     data = await state.get_data()
#     user_cards = data["user_cards"]
#     dealer_cards = data["dealer_cards"]
#     deck = data["deck"]
#     bet = data["bet"]
#     balance = data["balance"]
#     user_total = calc_total(user_cards)

#     # === 1️⃣ Відображаємо дилера (тільки першу карту) ===
#     hidden_card = "❓"
#     shown_cards = [dealer_cards[0], hidden_card]
#     dealer_table = await message.answer(
#         f"🤵‍♂️ <b>Карти дилера:</b> {show_cards(shown_cards)}",
#         parse_mode="HTML",
#     )

#     # Анімаційне повідомлення “Дилер думає…”
#     dealer_action = await message.answer("🤵‍♂️ Дилер думає •", parse_mode="HTML")

#     async def think(text="🤵‍♂️ Дилер думає"):
#         for dots in ["•", "• •", "• • •", "• •"]:
#             try:
#                 await dealer_action.edit_text(f"{text} {dots}", parse_mode="HTML")
#                 await asyncio.sleep(0.3)
#             except Exception:
#                 pass

#     # === 2️⃣ Анімація відкриття карт ===
#     # await think("🤵‍♂️ Дилер перевіряє карти")
#     await asyncio.sleep(0.2)
#     await dealer_action.edit_text(
#         "🤵‍♂️ Дилер відкриває другу карту...", parse_mode="HTML"
#     )
#     await asyncio.sleep(1)

#     # Відкриваємо обидві карти у другому повідомленні
#     dealer_total = calc_total(dealer_cards)
#     await dealer_table.edit_text(
#         f"🤵‍♂️ <b>Карти дилера:</b> {show_cards(dealer_cards)}  =  <b>{dealer_total}</b>",
#         parse_mode="HTML",
#     )
#     await asyncio.sleep(1)

#     # === 3️⃣ Дилер добирає карти ===
#     while dealer_total < 17:
#         await think("🤵‍♂️ Дилер вирішує взяти ще")
#         await asyncio.sleep(0.6)

#         if not deck:
#             deck = DECK_TEMPLATE.copy()
#             random.shuffle(deck)

#         new_card = deck.pop()
#         dealer_cards.append(new_card)
#         dealer_total = calc_total(dealer_cards)

#         # Оновлюємо “стіл” дилера (друге повідомлення)
#         try:
#             await dealer_table.edit_text(
#                 f"🤵‍♂️ <b>Карти дилера:</b> {show_cards(dealer_cards)}  =  <b>{dealer_total}</b>",
#                 parse_mode="HTML",
#             )
#         except Exception:
#             pass

#         await dealer_action.edit_text(
#             f"🤵‍♂️ Дилер бере карту: {new_card}", parse_mode="HTML"
#         )
#         await asyncio.sleep(1.2)

#     # === 4️⃣ Завершення анімації ===
#     await dealer_action.edit_text("🤵‍♂️ Дилер закінчив свій хід.", parse_mode="HTML")
#     await asyncio.sleep(0.6)

#     # === 5️⃣ Показуємо підсумкові карти гравця ===
#     await message.answer(
#         f"🧑‍🎓 <b>Твої карти:</b> {show_cards(user_cards)}  =  <b>{user_total}</b>\n"
#         f"🤵‍♂️ <b>Карти дилера:</b> {show_cards(dealer_cards)}  =  <b>{dealer_total}</b>",
#         parse_mode="HTML",
#     )

#     # ======= Визначаємо результат =======
#     if busted or user_total > 21:
#         is_win = False
#     elif dealer_total > 21 or user_total > dealer_total:
#         is_win = True
#     elif user_total == dealer_total:
#         is_win = None
#     else:
#         is_win = False

#     try:
#         await add_game_result("Blackjack", is_win is True)
#     except Exception:
#         pass

#     # ======= Результат =======
#     if is_win is True:
#         balance += bet
#         result = f"🎉 Ви виграли! +{bet} купонів\nВаш баланс: <b>{balance}</b>"
#     elif is_win is None:
#         result = f"🤝 Нічия! Ставка повернена\nВаш баланс: <b>{balance}</b>"
#     else:
#         balance -= bet
#         result = f"❌ Ви програли! -{bet} купонів\nВаш баланс: <b>{balance}</b>"

#     await state.update_data(balance=balance)
#     await message.answer(result, parse_mode="HTML")

#     # ======= Кінець гри =======
#     if balance >= 30 or balance <= 0:
#         is_session_win = balance >= 30
#         try:
#             if message.from_user.id != ADMIN_ID:
#                 await add_blackjack_session(is_session_win)
#         except Exception as e:
#             print(f"[DB Error] Не вдалося записати сесію Blackjack: {e}")

#         outcome = "✅ ВИГРАВ" if balance >= 30 else "❌ ПРОГРАВ"
#         try:
#             await message.bot.send_message(
#                 ADMIN_ID,
#                 f"🃏 <b>Blackjack фінал</b>\n"
#                 f"👤 {message.from_user.full_name} (🔗: <a href='tg://user?id={message.from_user.id}'>Профіль</a>)\n"
#                 # f"<a href='tg://user?id={message.from_user.id}'>Профіль</a>"
#                 f"🎯 Результат: {outcome}\n",
#                 # f"💵 Остання ставка: {bet}\n"
#                 # f"🏦 Баланс: {balance}",
#                 parse_mode="HTML",
#             )

#             await save_notification(
#                 message.from_user.id,
#                 message.from_user.username or "-",
#                 message.from_user.full_name or "-",
#                 "blackjack",
#                 # f"🃏 Blackjack — {outcome}\n💵 Ставка: {bet}, Баланс: {balance}",
#                 f"🃏 Blackjack — {outcome}",
#             )

#         except Exception:
#             pass

#         if balance >= 30:
#             kb = InlineKeyboardMarkup(
#                 inline_keyboard=[
#                     [
#                         InlineKeyboardButton(
#                             text="🏆 Champion",
#                             callback_data=f"choose_reward:champion:{message.from_user.id}",
#                         ),
#                         InlineKeyboardButton(
#                             text="🎰 Superomatic",
#                             callback_data=f"choose_reward:superomatic:{message.from_user.id}",
#                         ),
#                     ]
#                 ]
#             )
#             await message.answer(
#                 "🎁 Ви досягли 30 купонів! Оберіть тип коду:", reply_markup=kb
#             )
#             await add_game_win(message.from_user.id)
#             await state.clear()
#             return

#         if balance <= 0:
#             gift_claimed = await has_claimed_gift(message.from_user.id)
#             await message.answer(
#                 "💀 Баланс 0 купонів. Гру завершено.",
#                 reply_markup=main_menu(
#                     is_admin=(message.from_user.id == ADMIN_ID),
#                     user_has_gift=gift_claimed,
#                 ),
#             )
#             await state.clear()
#             return

#     # === Якщо гра триває ===
#     await asyncio.sleep(1)
#     await message.answer(
#         "Оберіть ставку:",
#         reply_markup=bet_keyboard(balance, show_menu_button=False),
#         parse_mode="HTML",
#     )
#     await state.set_state(BlackjackFSM.choosing_bet)


import asyncio
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
    has_claimed_gift,
    add_blackjack_session,
    save_notification,
    add_game_win,
)
from db.wallet import get_daily_net, get_yesterday_net, add_to_balance
from handlers.menu import main_menu
from handlers.config import ADMIN_ID
import aiosqlite
from db import DB_PATH

router = Router()


class BlackjackFSM(StatesGroup):
    choosing_bet = State()
    in_round = State()


SUITS = ["♠️", "♥️", "♦️", "♣️"]
RANKS = ["A", "K", "Q", "J", "10", "9", "8", "7", "6", "5", "4", "3", "2"]

def create_deck(num_decks=2):
    deck = [f"{r}{s}" for s in SUITS for r in RANKS] * num_decks
    random.shuffle(deck)
    return deck


VALUES = {"A": 11, "K": 10, "Q": 10, "J": 10, **{str(n): n for n in range(2, 11)}}


def calc_total(cards: list[str]) -> int:
    total = sum(VALUES.get("".join(ch for ch in c if ch.isalnum()), 0) for c in cards)
    aces = sum(1 for c in cards if "A" in c)
    while total > 21 and aces:
        total -= 10
        aces -= 1
    return total


def show_cards(cards: list[str]) -> str:
    return "  ".join(cards)


def bet_keyboard(balance: int):
    buttons = []
    if balance >= 5:
        buttons.append(KeyboardButton(text="💵 5 купонів"))
    if balance >= 10:
        buttons.append(KeyboardButton(text="💰 10 купонів"))
    return ReplyKeyboardMarkup(keyboard=[buttons], resize_keyboard=True)


def in_game_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="➕ Взяти ще"), KeyboardButton(text="🛑 Досить")]],
        resize_keyboard=True,
    )


@router.message(F.text == "🃏 Blackjack")
async def cmd_blackjack(message: types.Message, state: FSMContext):
    deck = create_deck(num_decks=2)
    await state.clear()
    await state.update_data(balance=10, deck=deck)
    await message.answer(
        f"🃏 <b>Blackjack (21)</b>\n\n"
        f"Стартовий баланс: <b>10 купонів</b>\n\n"
        f"Оберіть ставку:",
        parse_mode="HTML",
        reply_markup=bet_keyboard(10),
    )
    await state.set_state(BlackjackFSM.choosing_bet)


@router.message(BlackjackFSM.choosing_bet)
async def handle_bet_choice(message: types.Message, state: FSMContext):
    text = message.text.strip()
    if text not in ("💵 5 купонів", "💰 10 купонів"):
        return

    bet = 5 if "5" in text else 10
    data = await state.get_data()
    balance = data.get("balance", 10)
    deck = data.get("deck")

    if bet > balance:
        return await message.answer("⚠️ Недостатньо купонів.")

    user_cards = [deck.pop(), deck.pop()]
    dealer_cards = [deck.pop(), deck.pop()]

    await state.update_data(
        deck=deck,
        user_cards=user_cards,
        dealer_cards=dealer_cards,
        bet=bet,
        balance=balance,
    )

    user_total = calc_total(user_cards)

    if user_total == 21:
        await message.answer("🖤 Blackjack!")
        return await finish_round(message, state, busted=False)

    await message.answer(
        f"💵 Ставка: <b>{bet} купонів</b>\n\n"
        f"🧑‍🎓 Твої карти: {show_cards(user_cards)} = <b>{user_total}</b>\n"
        f"🤵‍♂️ Карта дилера: {dealer_cards[0]} ❓",
        parse_mode="HTML",
        reply_markup=in_game_keyboard(),
    )
    await state.set_state(BlackjackFSM.in_round)


@router.message(BlackjackFSM.in_round)
async def in_round_handler(message: types.Message, state: FSMContext):
    text = message.text.strip()
    data = await state.get_data()
    deck = data["deck"]
    user_cards = data["user_cards"]

    if text == "➕ Взяти ще":
        if not deck:
            deck = create_deck(num_decks=2)
        card = deck.pop()
        user_cards.append(card)
        await state.update_data(deck=deck, user_cards=user_cards)

        user_total = calc_total(user_cards)
        await message.answer(
            f"🃏 Ти взяв: {card}\n"
            f"Твої карти: {show_cards(user_cards)} = <b>{user_total}</b>",
            parse_mode="HTML",
        )

        if user_total > 21:
            await finish_round(message, state, busted=True)
        return

    if text == "🛑 Досить":
        await finish_round(message, state, busted=False)


async def finish_round(message: types.Message, state: FSMContext, busted: bool):
    data = await state.get_data()
    user_cards = data["user_cards"]
    dealer_cards = data["dealer_cards"]
    deck = data["deck"]
    bet = data["bet"]
    balance = data["balance"]

    user_total = calc_total(user_cards)

    # Показуємо першу карту дилера
    dealer_table = await message.answer(
        f"🤵‍♂️ <b>Карти дилера:</b> {show_cards([dealer_cards[0], '❓'])}",
        parse_mode="HTML",
    )
    dealer_action = await message.answer("🤵‍♂️ Дилер думає •")

    async def think(text="🤵‍♂️ Дилер думає"):
        for dots in ["•", "• •", "• • •", "• •"]:
            try:
                await dealer_action.edit_text(f"{text} {dots}")
                await asyncio.sleep(0.3)
            except Exception:
                pass

    await asyncio.sleep(0.2)
    await dealer_action.edit_text("🤵‍♂️ Дилер відкриває другу карту...")
    await asyncio.sleep(1)

    dealer_total = calc_total(dealer_cards)
    await dealer_table.edit_text(
        f"🤵‍♂️ <b>Карти дилера:</b> {show_cards(dealer_cards)}  =  <b>{dealer_total}</b>",
        parse_mode="HTML",
    )
    await asyncio.sleep(1)

    # Дилер добирає карти
    while dealer_total < 17:
        await think("🤵‍♂️ Дилер вирішує взяти ще")
        await asyncio.sleep(0.6)

        if not deck:
            deck = create_deck(num_decks=2)

        new_card = deck.pop()
        dealer_cards.append(new_card)
        dealer_total = calc_total(dealer_cards)

        try:
            await dealer_table.edit_text(
                f"🤵‍♂️ <b>Карти дилера:</b> {show_cards(dealer_cards)}  =  <b>{dealer_total}</b>",
                parse_mode="HTML",
            )
        except Exception:
            pass

        await dealer_action.edit_text(f"🤵‍♂️ Дилер бере карту: {new_card}")
        await asyncio.sleep(1.2)

    await dealer_action.edit_text("🤵‍♂️ Дилер закінчив свій хід.")
    await asyncio.sleep(0.6)

    await message.answer(
        f"🧑‍🎓 <b>Твої карти:</b> {show_cards(user_cards)}  =  <b>{user_total}</b>\n"
        f"🤵‍♂️ <b>Карти дилера:</b> {show_cards(dealer_cards)}  =  <b>{dealer_total}</b>",
        parse_mode="HTML",
    )

    if busted or user_total > 21:
        is_win = False
    elif dealer_total > 21 or user_total > dealer_total:
        is_win = True
    elif user_total == dealer_total:
        is_win = None
    else:
        is_win = False

    await add_game_result("Blackjack", is_win is True)

    if is_win is True:
        balance += bet
        result = f"🎉 Ви виграли! +{bet} купонів\nБаланс: <b>{balance}</b>"
    elif is_win is None:
        result = f"🤝 Нічия! Ставка повернена\nБаланс: <b>{balance}</b>"
    else:
        balance -= bet
        result = f"❌ Ви програли! -{bet} купонів\nБаланс: <b>{balance}</b>"

    await state.update_data(balance=balance)
    await message.answer(result, parse_mode="HTML")

    if balance >= 30 or balance <= 0:
        today_net = await get_daily_net(message.from_user.id)
        yesterday_net = await get_yesterday_net(message.from_user.id)
        has_contribution = (today_net > 0) or (yesterday_net > 0)

        if balance >= 30 and has_contribution:
            await add_to_balance(message.from_user.id, 30)
            await add_game_win(message.from_user.id)
            final_text = "🎉 Вітаю! +30 грн на баланс!"
        elif balance >= 30:
            final_text = "💸 Виграш буде до депозиту"
        else:
            final_text = "💀 Баланс 0. Гра завершена."

        gift_claimed = await has_claimed_gift(message.from_user.id)
        await message.answer(
            final_text,
            reply_markup=main_menu(
                is_admin=(message.from_user.id == ADMIN_ID),
                user_has_gift=gift_claimed,
            ),
        )
        await state.clear()
        return

    await asyncio.sleep(1.2)
    await message.answer("Оберіть ставку:", reply_markup=bet_keyboard(balance), parse_mode="HTML")
    await state.set_state(BlackjackFSM.choosing_bet)