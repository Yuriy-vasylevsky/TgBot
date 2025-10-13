from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


# ==========================
# Головне меню
# ==========================
def main_menu(is_admin: bool = False, user_has_gift: bool = False):
    """
    Повертає головне меню для користувача або адміністратора.
    """
    if is_admin:
        keyboard = [
            ["⚙️ Адмін панель"],
            ["🎮 Ігри"],
            ["💎 Касир"],
            ["🎲 Група"],
            ["🔹 Акції"],
            ["🎁 Скинути подарунки"],
        ]
    else:
        keyboard = [
            ["🎟 Ввести промокод"],
            ["💳 Номер карти"],
            ["💫 КОД в посилання", "🏅 Провайдери"],
            ["🎲 Група", "💎 Касир"],
            ["🔹 Акції", "💥 Демо гра"],
        ]
        if not user_has_gift:
            keyboard.append(["🎁 Подарунок"])

    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=b) for b in row] for row in keyboard],
        resize_keyboard=True,
    )


# ==========================
# Меню дій (акцій)
# ==========================
def actions_menu():
    keyboard = [
        ["🔙 Назад до головного меню"],
        ["🎮 Бонус на Superomatic", "🎲 Сейф"],
        ["🃏 Cash Back", "🎟 Промокоди"],
    ]
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=b) for b in row] for row in keyboard],
        resize_keyboard=True,
    )


# ==========================
# Адмін-меню
# ==========================
def admin_menu():
    keyboard = [
        ["📢 Розсилка"],
        ["👥 Список користувачів"],
        ["➕ Створити промокод"],
        ["🎟 Активні промокоди"],
        ["📊 Статистика"],
        ["🎯 Winrate"],
        ["🔙 Назад до головного меню"],
    ]
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=b) for b in row] for row in keyboard],
        resize_keyboard=True,
    )
