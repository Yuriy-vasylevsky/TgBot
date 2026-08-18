import asyncio
import random
import weakref

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
    has_claimed_gift,
    add_blackjack_session,
    add_game_win,
)
from db.wallet import add_to_balance, add_daily_game_win, get_available_game_win
from handlers.menu import main_menu
from handlers.config import ADMIN_ID

router = Router()


class BlackjackFSM(StatesGroup):
    choosing_bet = State()
    in_round = State()
    resolving = State()


# Aiogram's in-memory FSM storage does not serialize updates for one user.  Keep
# a per-player lock as well as an explicit intermediate state so that two
# updates received in the same event-loop tick cannot both settle one round.
_player_locks: weakref.WeakValueDictionary[
    tuple[int, int], asyncio.Lock
] = weakref.WeakValueDictionary()


def _player_lock(message: types.Message) -> asyncio.Lock:
    key = (message.chat.id, message.from_user.id)
    lock = _player_locks.get(key)
    if lock is None:
        lock = asyncio.Lock()
        _player_locks[key] = lock
    return lock


def _blackjack_states() -> set[str]:
    return {
        BlackjackFSM.choosing_bet.state,
        BlackjackFSM.in_round.state,
        BlackjackFSM.resolving.state,
    }


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
    lock = _player_lock(message)
    if lock.locked():
        return

    async with lock:
        if await state.get_state() in _blackjack_states():
            await message.answer("⚠️ Поточна гра в Blackjack ще не завершена.")
            return

        deck = create_deck(num_decks=2)
        await state.clear()
        await state.update_data(balance=10, deck=deck)
        await state.set_state(BlackjackFSM.choosing_bet)
        await message.answer(
            f"🃏 <b>Blackjack (21)</b>\n\n"
            f"Стартовий баланс: <b>10 купонів</b>\n\n"
            f"Оберіть ставку:",
            parse_mode="HTML",
            reply_markup=bet_keyboard(10),
        )


@router.message(BlackjackFSM.choosing_bet)
async def handle_bet_choice(message: types.Message, state: FSMContext):
    text = (message.text or "").strip()
    if text not in ("💵 5 купонів", "💰 10 купонів"):
        return

    lock = _player_lock(message)
    if lock.locked():
        return

    async with lock:
        if await state.get_state() != BlackjackFSM.choosing_bet.state:
            return

        # Claim the bet before the first yielding operation below. This also
        # prevents another Telegram update from being routed as a bet choice.
        await state.set_state(BlackjackFSM.resolving)

        bet = 5 if "5" in text else 10
        data = await state.get_data()
        balance = data.get("balance", 10)
        deck = data.get("deck") or create_deck(num_decks=2)

        if bet > balance:
            await state.set_state(BlackjackFSM.choosing_bet)
            await message.answer("⚠️ Недостатньо купонів.")
            return

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
            await finish_round(message, state, busted=False)
            return

        await state.set_state(BlackjackFSM.in_round)
        await message.answer(
            f"💵 Ставка: <b>{bet} купонів</b>\n\n"
            f"🧑‍🎓 Твої карти: {show_cards(user_cards)} = <b>{user_total}</b>\n"
            f"🤵‍♂️ Карта дилера: {dealer_cards[0]} ❓",
            parse_mode="HTML",
            reply_markup=in_game_keyboard(),
        )


@router.message(BlackjackFSM.in_round)
async def in_round_handler(message: types.Message, state: FSMContext):
    text = (message.text or "").strip()
    if text not in ("➕ Взяти ще", "🛑 Досить"):
        return

    lock = _player_lock(message)
    if lock.locked():
        return

    async with lock:
        if await state.get_state() != BlackjackFSM.in_round.state:
            return

        # Switch state before reading or changing cards. Repeated button presses
        # are ignored while this action (including the dealer animation) runs.
        await state.set_state(BlackjackFSM.resolving)

        if text == "➕ Взяти ще":
            data = await state.get_data()
            deck = data["deck"]
            user_cards = data["user_cards"]

            if not deck:
                deck = create_deck(num_decks=2)
            card = deck.pop()
            user_cards.append(card)
            await state.update_data(deck=deck, user_cards=user_cards)

            user_total = calc_total(user_cards)
            if user_total <= 21:
                # Restore the playable state before sending the informational
                # message. The lock still suppresses presses until it is sent.
                await state.set_state(BlackjackFSM.in_round)
            await message.answer(
                f"🃏 Ти взяв: {card}\n"
                f"Твої карти: {show_cards(user_cards)} = <b>{user_total}</b>",
                parse_mode="HTML",
            )

            if user_total > 21:
                await finish_round(message, state, busted=True)
            return

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

    # === Перевірка завершення гри ===
    if balance >= 30 or balance <= 0:
        await add_blackjack_session(is_win=balance >= 30)

        admin_status = ""

        if balance >= 30:
            # Нова система перевірки
            payout = min(30, await get_available_game_win(message.from_user.id))

            if payout > 0:
                await add_to_balance(message.from_user.id, payout)
                await add_game_win(message.from_user.id)
                await add_daily_game_win(message.from_user.id, payout)



                from db.winlog import log_win
                await log_win(
                    message.from_user.id, message.from_user.username, message.from_user.full_name,
                    "game", "🃏 Blackjack", payout
                )




                final_text = f"🎉 Вітаю! +{payout} грн нараховано на баланс!"
                admin_status = f" | +{payout} грн на баланс"
                if payout < 30:
                    final_text += f"\n💸 Решта {30 - payout} грн буде зарахована до депозиту"
                    admin_status += f" | +{30 - payout} грн до депозиту"
            else:
                final_text = "💸 Виграш 30 грн буде зарахований до депозиту"
                admin_status = " | +30 грн до депозиту"
        else:
            final_text = "💀 Баланс 0. Гра завершена."

        # Сповіщення адміністратору
        try:
            username = f"@{message.from_user.username}" if message.from_user.username else f"<a href='tg://user?id={message.from_user.id}'>{message.from_user.full_name}</a>"
            outcome = "ВИГРАВ" if balance >= 30 else "ПРОГРАВ"
            
            await message.bot.send_message(
                ADMIN_ID,
                f"🃏 Гравець зіграв у 'Blackjack'\n"
                f"👤 {message.from_user.full_name} ({username})\n"
                f"Результат: {outcome}{admin_status}",
                parse_mode="HTML",
            )
        except Exception:
            pass

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
