from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def games_menu():
    keyboard = [["🎰 Слоти"], ["🎯 Один з трьох"]]
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=b) for b in row] for row in keyboard],
        resize_keyboard=True,
    )
