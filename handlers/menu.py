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
            ["🎮 Ігри", "🎯 Winrate"],
            ["🤞 Згенерувати промо", "🎟 Активні Promo"],
            ["👥 Список користувачів"],
            ["📜 Історія сповіщень", "💰 Гаманець"],
            ["➕ Додати код"],
            ["⚙️⚙️⚙️", "⚙️ Адмін панель"],
        ]
    else:
        keyboard = [
            ["🎟 Ввести промокод"],
            ["🎡 Колесо фортуни", "💰 Бездепиш 100"],
            ["💳 Номер карти", "🔹 Акції"],
            ["👤 Мій кабінет"],
            ["🎲 Група", "💎 Касир"],
            ["💫 КОД в посилання", "🏅 Провайдери"],
        ]
        # if not user_has_gift:
        #     keyboard.append(["🎁 Подарунок"])

    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=b) for b in row] for row in keyboard],
        resize_keyboard=True,
    )


# ==========================
# Адмін-меню
# ==========================
def admin_menu():
    keyboard = [
        ["📢 Розсилка", "🛠 Оновити меню"],
        ["🎡 Колесо фортуни", "🎁 Щоденний бонус"],
        ["🔒 Сейф"],
        ["➕ Створити промокод"],
        ["📊 Статистика"],
        ["💳 Керування картами"],
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
        ["🗑 Видалити завдання", "🗓 Додати тижневе завдання"],
        ["🎁 Скинути подарунки"],
        ["🧹 Очистити статистику ігор"],
        ["📜 Перегляд кодів"],
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
        # ["🎮 Бонус на Superomatic", "🎲 Сейф", "🎁 Щоденний бонус"],
        ["🎲 Сейф"],
        ["🃏 Cash Back", "🎟 Промокоди"],
    ]
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=b) for b in row] for row in keyboard],
        resize_keyboard=True,
    )
