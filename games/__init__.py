from .slot import router as slot_router
from .one_of_three import router as one_of_three_router
from .rewards import router as rewards_router
from .blackjack import router as blackjack_router
from .fortune import router as fortune_router
from .daily_bonus import router as daily_bonus_router
# dp.include_router(blackjack_router)


# Якщо games_menu() тобі потрібна
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def games_menu():
    keyboard = [["🎰 Слоти"], ["🎯 Один з трьох"], ["🃏 Blackjack"]]
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=b) for b in row] for row in keyboard],
        resize_keyboard=True,
    )
