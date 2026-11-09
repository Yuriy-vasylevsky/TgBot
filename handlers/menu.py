from services.promotions import visible_rows
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
          
            ["👥 Список користувачів", "💰 Баланси гравців"],
            ["🤞 Згенерувати промо", "🎯 Winrate"],
            # ["📜 Історія сповіщень"],
            [ "📊 Виграші", "📉 Програші"],
            # [ "💳 Чеки"],
            ["⚙️⚙️⚙️", "⚙️ Адмін панель"],
        ]
    else:
        keyboard = [
          
   
            ["💰 Гаманець", "🎮 Грати" ],
            ["🎲 Фортуна"],
            ["🎟 Ввести промокод", "🐷 Скарбничка"],
            ["👤 Мій кабінет"],
            ["👥 Реферали"],
            ["🎲 Група", "💎 Касир"],
            # ["💫 КОД в посилання", "🏅 Провайдери"],
            # ["💳 Номер карти", "🏅 Провайдери"],
        ]
        # if not user_has_gift:
        #     keyboard.append(["🎁 Подарунок"])

    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=b) for b in row] for row in visible_rows(keyboard)],
        resize_keyboard=True,
    )


# ==========================
# меню чеків
# ==========================


def checks_menu():
    keyboard = [
        # ["🏆 Чек 100 Champion", "🏆 Чек 200 Champion"],
        ["🎰 Чек 100 Superomatic", "🎰 Чек 200 Superomatic"],
        ["➕ Додати промокод"],
        ["📜 Перегляд кодів", "📊 Чеки"],
        ["🔙 Назад до головного меню"]
    ]

    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=b) for b in row] for row in visible_rows(keyboard)],
        resize_keyboard=True
    )


# ==========================
# Адмін-меню
# ==========================
def admin_menu():
    keyboard = [
        ["📢 Розсилка", "🛠 Оновити меню"],
        ["📣 Керування акціями"],
        ["⚙️ Автооплата", "🪙 Криптооплата"],
        ["💰 Каса", "👥 Всі реферали"],
        ["🔒 Сейф",  "💳 Всі оплати"],
        ["🧠 Аналізатор квитанцій"],
        ["💳 Керування картами", "🔙 Назад до головного меню"],
    ]
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=b) for b in row] for row in visible_rows(keyboard)],
        resize_keyboard=True,
    )


# ==========================
# Адмін-меню 2 ⚙️⚙️⚙️
# ==========================
# def admin_menu2():
#     keyboard = [
#         ["🗑 Видалити завдання", "🗓 Додати тижневе завдання"],
#         ["🎮 Ігри", "🎁 Скинути подарунки"],
#         ["🧹 Очистити статистику ігор"],
#         [ "🎮 Грати", "💰 Гаманець" ],
#         ["🚫 Забанити", "🔓 Розбанити"],
#         ["📋 Список банів", "📦 Скачати БД"],
#         ["🔙 Назад до головного меню"],
#     ]
#     return ReplyKeyboardMarkup(
#         keyboard=[[KeyboardButton(text=b) for b in row] for row in visible_rows(keyboard)],
#         resize_keyboard=True,
#     )

def admin_menu2():
    keyboard = [
      
        ["🎮 Грати", "💰 Гаманець"],
        [ "🎮 Ігри","🎡 Колесо фортуни" ],
        ["📊 Статистика","👤 Мій кабінет"],
        ["🚫 Бани", "🏆 Топ гравці"],
        ["➕ Створити промокод", "🎟 Активні Promo"],
        ["📦 Скачати БД", "🔙 Назад до головного меню"],
    ]
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=b) for b in row] for row in visible_rows(keyboard)],
        resize_keyboard=True,
    )


# ==========================
# Меню дій (акцій)
# ==========================
def actions_menu():
    keyboard = [
        ["🔙 Назад до головного меню"],
        # ["🎮 Бонус на Superomatic", "🎲 Сейф", "🎁 Щоденний бонус"],
        ["🎡 Колесо фортуни", "💰 Бездепиш 100"],
        ["🎲 Сейф"],
        ["🃏 Cash Back", "🎟 Промокоди"],
    ]
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=b) for b in row] for row in visible_rows(keyboard)],
        resize_keyboard=True,
    )
