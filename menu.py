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
            ["🎮 Ігри"],
            ["➕ Додати код", "📜 Перегляд кодів"],
            ["➕ Створити промокод", "🎟 Активні промокоди"],
            ["🎁 Скинути подарунки"],
            # ["📊 Статистика"],
            # ["🎯 Winrate"],
            ["⚙️ Адмін панель"],
        ]
    else:
        keyboard = [
            ["🎟 Ввести промокод"],
            ["🔹 Акції"],
            ["💳 Номер карти"],
            ["🎲 Група", "💎 Касир"],
            ["💫 КОД в посилання", "🏅 Провайдери"],
            # [ "💥 Демо гра"],
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
        # ["➕ Створити промокод", "🎟 Активні промокоди"],
        # ["🎟 Активні промокоди"],
        ["📊 Статистика"],
        ["🎯 Winrate"],
        ["🚫 Забанити по ID", "🔓 Розбанити по ID"],
        ["📋 Список банів"],
        ["🔙 Назад до головного меню"],
    ]
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=b) for b in row] for row in keyboard],
        resize_keyboard=True,
    )
