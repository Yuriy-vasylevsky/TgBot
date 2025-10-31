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
            ["🎮 Ігри", "🎡 Колесо фортуни", "🎁 Щоденний бонус"],
            ["➕ Додати код", "📜 Перегляд кодів"],
            ["🤞 Згенерувати промо"],
            ["🎟 Активні промокоди"],
            ["📜 Історія сповіщень"],
            ["🎯 Winrate", "📊 Статистика"],
            ["⚙️ Адмін панель", "⚙️⚙️⚙️"],
        ]
    else:
        keyboard = [
            ["🎟 Ввести промокод"],
            ["🎁 Щоденний бонус", "🎡 Колесо фортуни"],
            ["👤 Мій кабінет", "💳 Номер карти"],
            ["🔹 Акції"],
            ["🎲 Група", "💎 Касир"],
            ["💫 КОД в посилання", "🏅 Провайдери"],
        ]
        if not user_has_gift:
            keyboard.append(["🎁 Подарунок"])

    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=b) for b in row] for row in keyboard],
        resize_keyboard=True,
    )


# ==========================
# Адмін-меню
# ==========================
def admin_menu():
    keyboard = [
        ["📢 Розсилка", "👥 Список користувачів"],
        # ["🗑 Видалити завдання", "🗓 Додати тижневе завдання"],
        # ["🎁 Скинути подарунки", "🧹 Очистити статистику ігор"],
        ["➕ Створити промокод", "🛠 Оновити меню"],
        # ["📊 Статистика"],
        ["💳 Керування картами"],
        # ["🚫 Забанити", "🔓 Розбанити"],
        # ["📋 Список банів", "📦 Скачати БД"],
        ["🔙 Назад до головного меню"],
    ]
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=b) for b in row] for row in keyboard],
        resize_keyboard=True,
    )


# ==========================
# Адмін-меню 2 ⚙️⚙️⚙️
# ==========================
def admin_menu2():
    keyboard = [
        # ["📢 Розсилка", "👥 Список користувачів"],
        ["🗑 Видалити завдання", "🗓 Додати тижневе завдання"],
        ["🎁 Скинути подарунки", "🧹 Очистити статистику ігор"],
        ["➕ Створити промокод", "🛠 Оновити меню"],
        # ["💳 Керування картами"],
        ["🚫 Забанити", "🔓 Розбанити"],
        ["📋 Список банів", "📦 Скачати БД"],
        ["🔙 Назад до головного меню"],
    ]
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
