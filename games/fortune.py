

# import asyncio
# import random
# import html
# import datetime
# from aiogram import Router, F, types
# from aiogram.types import (
#     InlineKeyboardMarkup,
#     InlineKeyboardButton,
#     Message,
#     CallbackQuery,
# )

# # === Конфіг ===
# try:
#     from config import ADMIN_ID
# except Exception:
#     ADMIN_ID = None

# try:
#     from menu import main_menu  # type: ignore
# except Exception:
#     main_menu = None

# router = Router(name="fortune")

# FORTUNE_BTN = "🎡 Колесо фортуни"

# # === Кількість ігор, необхідна для доступу ===
# REQUIRED_GAMES = 1
# TIME = 86400
# # 86400: 24 години
# # === Призи та шанси ===
# PRIZES = [
#     {"title": "30 грн ", "weight": 24, "code": "COUPON_5", "value": 5},
#     {"title": "50 грн ", "weight": 20, "code": "COUPON_8", "value": 8},
#     {"title": "60 грн ", "weight": 20, "code": "COUPON_10", "value": 10},
#     {"title": "100 грн ", "weight": 5, "code": "COUPON_10", "value": 10},
#     {"title": "200 грн ", "weight": 1, "code": "COUPON_10", "value": 10},
#     {"title": "❌ Нічого", "weight": 20, "code": "NOTHING", "value": 0},
#     {
#         "title": "🔁 Додаткове обертання",
#         "weight": 10,
#         "code": "EXTRA_SPIN",
#         "value": None,
#     },
# ]

# # Активні гравці + обмеження часу
# _spinning_users: set[int] = set()
# _last_spin_time: dict[int, datetime.datetime] = {}  # {user_id: datetime}


# # ===== Допоміжні =====
# def _kb_main() -> InlineKeyboardMarkup:
#     return InlineKeyboardMarkup(
#         inline_keyboard=[
#             [
#                 InlineKeyboardButton(
#                     text="Крутити колесо 🎯", callback_data="fortune:spin"
#                 )
#             ],
#             [
#                 InlineKeyboardButton(
#                     text="📜 Список призів і шансів", callback_data="fortune:prizes"
#                 )
#             ],
#         ]
#     )


# def _kb_back_to_menu() -> InlineKeyboardMarkup:
#     return InlineKeyboardMarkup(
#         inline_keyboard=[
#             [
#                 InlineKeyboardButton(
#                     text="⬅️ Назад до меню", callback_data="fortune:back"
#                 )
#             ],
#             [
#                 InlineKeyboardButton(
#                     text="🔄 Крутити ще раз", callback_data="fortune:spin"
#                 )
#             ],
#         ]
#     )


# def _format_prize_table() -> str:
#     total_weight = sum(p["weight"] for p in PRIZES)
#     lines = ["<b>🎡 Колесо фортуни — призи та шанси</b>"]
#     for i, p in enumerate(PRIZES, start=1):
#         prob = (p["weight"] / total_weight) * 100
#         lines.append(f"{i:>2}. {p['title']} — <code>{prob:.1f}%</code>")
#     lines.append("\nНатисни «Крутити колесо 🎯» щоб спробувати удачу!")
#     return "\n".join(lines)


# def _choose_prize() -> dict:
#     weights = [p["weight"] for p in PRIZES]
#     return random.choices(PRIZES, weights=weights, k=1)[0]


# async def _animate_spin(cb: CallbackQuery) -> None:
#     frames = [
#         "| 🎯                    ",
#         "|     🎯                ",
#         "|         🎯            ",
#         "|             🎯        ",
#         "|                 🎯    ",
#         "|                     🎯",
#         "|                 🎯    ",
#         "|             🎯        ",
#         "|         🎯            ",
#         "|     🎯                ",
#     ]
#     for _ in range(2):
#         for fr in frames:
#             try:
#                 await cb.message.edit_text(
#                     f"<b>Колесо крутиться...</b>\n<code>{fr}</code>", parse_mode="HTML"
#                 )
#             except Exception:
#                 pass
#             await asyncio.sleep(0.22)
#     for fr in frames[:5]:
#         try:
#             await cb.message.edit_text(
#                 f"<b>Зупиняється...</b>\n<code>{fr}</code>", parse_mode="HTML"
#             )
#         except Exception:
#             pass
#         await asyncio.sleep(0.28)


# async def _notify_admin(user: types.User, prize_title: str, bot):
#     if not ADMIN_ID:
#         return
#     try:
#         text = (
#             "🧑‍🎰 <b>Колесо фортуни — виграш</b>\n"
#             f"👤 Користувач: <a href='tg://user?id={user.id}'>{html.escape(user.full_name)}</a>\n"
#             f"🆔 ID: <code>{user.id}</code>\n"
#             f"🎁 Приз: <b>{html.escape(prize_title)}</b>"
#         )
#         await bot.send_message(ADMIN_ID, text, parse_mode="HTML")
#     except Exception:
#         pass


# # ===== Хендлери =====
# @router.message(F.text == FORTUNE_BTN)
# @router.message(F.text.lower().contains("колесо фортуни"))
# @router.message(F.text == "/fortune")
# async def fortune_entry(message: Message):
#     text = (
#         "<b>🎡 Колесо фортуни</b>\n\n"
#         "Тут ти можеш випробувати удачу. Натисни «Крутити колесо 🎯».\n"
#         "За бажанням — подивись список призів та шансів."
#     )
#     await message.answer(text, reply_markup=_kb_main(), parse_mode="HTML")


# @router.callback_query(F.data == "fortune:prizes")
# async def show_prizes(cb: CallbackQuery):
#     await cb.answer()
#     await cb.message.edit_text(
#         _format_prize_table(), reply_markup=_kb_main(), parse_mode="HTML"
#     )


# @router.callback_query(F.data == "fortune:back")
# async def back_to_menu(cb: CallbackQuery):
#     await cb.answer()
#     if main_menu:
#         await cb.message.edit_text(
#             "Головне меню:", reply_markup=main_menu(is_admin=False)
#         )
#     else:
#         await cb.message.edit_text("Повернувся до меню. Обери дію.")


# @router.callback_query(F.data == "fortune:spin")
# async def spin(cb: CallbackQuery):
#     user_id = cb.from_user.id

#     # === 1️⃣ Перевірка доступу за кількістю ігор ===
#     try:
#         from db import get_user_data

#         user_data = await get_user_data(user_id)
#         games_played = user_data.get("games_played", 0) if user_data else 0
#     except Exception:
#         games_played = 0

#     if games_played < REQUIRED_GAMES:
#         await cb.answer()
#         await cb.message.answer(
#             f"⚠️ Доступ до колеса фортуни відкривається після {REQUIRED_GAMES} зіграних ігор.\n"
#             f"🎮 У вас зараз: <b>{games_played}</b>.\n"
#             f"Зіграйте ще <b>{REQUIRED_GAMES - games_played}</b>, щоб отримати доступ!",
#             parse_mode="HTML",
#         )
#         return

#     # === 2️⃣ Перевірка на час (1 раз на 24 години) ===
#     now = datetime.datetime.now()
#     if user_id in _last_spin_time:
#         diff = now - _last_spin_time[user_id]

#         if diff.total_seconds() < TIME:
#             next_time = _last_spin_time[user_id] + datetime.timedelta(hours=24)
#             await cb.answer()
#             await cb.message.answer(
#                 f"⚠️ Ви вже крутили колесо сьогодні!\n"
#                 f"🕒 Наступна спроба буде доступна завтра о <b>{next_time.strftime('%H:%M')}</b>",
#                 parse_mode="HTML",
#             )
#             return

#     if user_id in _spinning_users:
#         await cb.answer("Зачекай, колесо вже крутиться…", show_alert=False)
#         return

#     _spinning_users.add(user_id)
#     _last_spin_time[user_id] = now

#     try:
#         await cb.answer()
#         await _animate_spin(cb)

#         prize = _choose_prize()
#         prize_title = prize["title"]

#         result_text = (
#             "<b>🎉 Результат:</b>\n" f"Тобі випало: <b>{html.escape(prize_title)}</b>"
#         )
#         await cb.message.edit_text(
#             result_text, reply_markup=_kb_back_to_menu(), parse_mode="HTML"
#         )

#         await _notify_admin(cb.from_user, prize_title, cb.message.bot)

#         # Якщо випало додаткове обертання
#         if prize["code"] == "EXTRA_SPIN":
#             await asyncio.sleep(0.5)
#             await cb.message.answer("🔁 Отримано додаткове обертання! Кручу ще раз…")
#             await spin_again(cb)
#     finally:
#         _spinning_users.discard(user_id)


# async def spin_again(cb: CallbackQuery):
#     """Повторне обертання без виклику cb.answer(), щоб уникнути RuntimeError."""
#     user_id = cb.from_user.id
#     _spinning_users.add(user_id)
#     try:
#         await _animate_spin(cb)
#         prize = _choose_prize()
#         prize_title = prize["title"]
#         result_text = (
#             "<b>🎉 Результат:</b>\n" f"Тобі випало: <b>{html.escape(prize_title)}</b>"
#         )
#         await cb.message.edit_text(
#             result_text, reply_markup=_kb_back_to_menu(), parse_mode="HTML"
#         )
#         await _notify_admin(cb.from_user, prize_title, cb.message.bot)
#     finally:
#         _spinning_users.discard(user_id)


import asyncio
import random
import html
import datetime
from aiogram import Router, F, types
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    Message,
    CallbackQuery,
)

# === Конфіг ===
try:
    from config import ADMIN_ID
except Exception:
    ADMIN_ID = None

try:
    from menu import main_menu  # type: ignore
except Exception:
    main_menu = None

router = Router(name="fortune")

FORTUNE_BTN = "🎡 Колесо фортуни"

# === Налаштування ===
REQUIRED_GAMES = 1        # скільки ігор потрібно для доступу
TIME = 86400              # 86400 секунд = 24 години

# === Призи та шанси ===
PRIZES = [
    {"title": "30 грн", "weight": 24, "code": "COUPON_5", "value": 5},
    {"title": "50 грн", "weight": 20, "code": "COUPON_8", "value": 8},
    {"title": "60 грн", "weight": 20, "code": "COUPON_10", "value": 10},
    {"title": "100 грн", "weight": 5, "code": "COUPON_10", "value": 10},
    {"title": "200 грн", "weight": 1, "code": "COUPON_10", "value": 10},
    {"title": "❌ Нічого", "weight": 20, "code": "NOTHING", "value": 0},
    {"title": "🔁 Додаткове обертання", "weight": 10, "code": "EXTRA_SPIN", "value": None},
]

_spinning_users: set[int] = set()
_last_spin_time: dict[int, datetime.datetime] = {}


# ===== Допоміжні =====
def _kb_main() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Крутити колесо 🎯", callback_data="fortune:spin")],
            [InlineKeyboardButton(text="📜 Список призів і шансів", callback_data="fortune:prizes")],
        ]
    )


def _format_prize_table() -> str:
    total_weight = sum(p["weight"] for p in PRIZES)
    lines = ["<b>🎡 Колесо фортуни — призи та шанси</b>"]
    for i, p in enumerate(PRIZES, start=1):
        prob = (p["weight"] / total_weight) * 100
        lines.append(f"{i:>2}. {p['title']} — <code>{prob:.1f}%</code>")
    lines.append("\nНатисни «Крутити колесо 🎯», щоб спробувати удачу!")
    return "\n".join(lines)


def _choose_prize() -> dict:
    weights = [p["weight"] for p in PRIZES]
    return random.choices(PRIZES, weights=weights, k=1)[0]


async def _animate_spin(cb: CallbackQuery) -> None:
    frames = [
        "| 🎯                    ",
        "|     🎯                ",
        "|         🎯            ",
        "|             🎯        ",
        "|                 🎯    ",
        "|                     🎯",
        "|                 🎯    ",
        "|             🎯        ",
        "|         🎯            ",
        "|     🎯                ",
    ]
    for _ in range(2):
        for fr in frames:
            try:
                await cb.message.edit_text(
                    f"<b>Коло крутиться...</b>\n<code>{fr}</code>", parse_mode="HTML"
                )
            except Exception:
                pass
            await asyncio.sleep(0.22)
    for fr in frames[:5]:
        try:
            await cb.message.edit_text(
                f"<b>Зупиняється...</b>\n<code>{fr}</code>", parse_mode="HTML"
            )
        except Exception:
            pass
        await asyncio.sleep(0.28)


async def _notify_admin(user: types.User, prize_title: str, bot):
    """Надсилає адміну повідомлення про виграш."""
    if not ADMIN_ID:
        return
    try:
        text = (
            "🧑‍🎰 <b>Колесо фортуни — виграш</b>\n"
            f"👤 Користувач: <a href='tg://user?id={user.id}'>{html.escape(user.full_name)}</a>\n"
            f"🆔 ID: <code>{user.id}</code>\n"
            f"🎁 Приз: <b>{html.escape(prize_title)}</b>"
        )
        await bot.send_message(ADMIN_ID, text, parse_mode="HTML")
    except Exception:
        pass


# ===== Хендлери =====
@router.message(F.text == FORTUNE_BTN)
@router.message(F.text.lower().contains("колесо фортуни"))
@router.message(F.text == "/fortune")
async def fortune_entry(message: Message):
    text = (
        "<b>🎡 Колесо фортуни</b>\n\n"
        "Тут ти можеш випробувати удачу. Натисни «Крутити колесо 🎯».\n"
        "За бажанням — подивись список призів та шансів."
    )
    await message.answer(text, reply_markup=_kb_main(), parse_mode="HTML")


@router.callback_query(F.data == "fortune:prizes")
async def show_prizes(cb: CallbackQuery):
    await cb.answer()
    await cb.message.edit_text(_format_prize_table(), reply_markup=_kb_main(), parse_mode="HTML")


@router.callback_query(F.data == "fortune:spin")
async def spin(cb: CallbackQuery):
    user_id = cb.from_user.id

    # === 1️⃣ Перевірка доступу за кількістю ігор ===
    try:
        from db import get_user_data
        user_data = await get_user_data(user_id)
        games_played = user_data.get("games_played", 0) if user_data else 0
    except Exception:
        games_played = 0

    if games_played < REQUIRED_GAMES:
        await cb.answer()
        await cb.message.answer(
            f"⚠️ Доступ до колеса фортуни відкривається після {REQUIRED_GAMES} зіграних ігор.\n"
            f"🎮 У вас зараз: <b>{games_played}</b>.\n"
            f"Зіграйте ще <b>{REQUIRED_GAMES - games_played}</b>, щоб отримати доступ!",
            parse_mode="HTML",
        )
        return

    # === 2️⃣ Перевірка — 1 раз на 24 години ===
    now = datetime.datetime.now()
    if user_id in _last_spin_time:
        diff = now - _last_spin_time[user_id]
        if diff.total_seconds() < TIME:
            next_time = _last_spin_time[user_id] + datetime.timedelta(seconds=TIME)
            await cb.answer()
            await cb.message.answer(
                f"⚠️ Ви вже крутили колесо сьогодні!\n"
                f"🕒 Наступна спроба буде доступна завтра о <b>{next_time.strftime('%H:%M')}</b>",
                parse_mode="HTML",
            )
            return

    if user_id in _spinning_users:
        await cb.answer("Зачекай, колесо вже крутиться…", show_alert=False)
        return

    _spinning_users.add(user_id)
    _last_spin_time[user_id] = now

    try:
        await cb.answer()
        await _animate_spin(cb)

        prize = _choose_prize()
        prize_title = prize["title"]

        # === Показуємо тільки результат (без кнопок) ===
        result_text = (
            "<b>🎉 Результат:</b>\n"
            f"Тобі випало: <b>{html.escape(prize_title)}</b>"
        )
        await cb.message.edit_text(result_text, parse_mode="HTML")

        # Повідомлення адміну
        await _notify_admin(cb.from_user, prize_title, cb.message.bot)

        # Якщо випало додаткове обертання
        if prize["code"] == "EXTRA_SPIN":
            await asyncio.sleep(0.5)
            await cb.message.answer("🔁 Отримано додаткове обертання! Кручу ще раз…")
            await spin_again(cb)
    finally:
        _spinning_users.discard(user_id)


async def spin_again(cb: CallbackQuery):
    """Повторне обертання без виклику cb.answer()."""
    user_id = cb.from_user.id
    _spinning_users.add(user_id)
    try:
        await _animate_spin(cb)
        prize = _choose_prize()
        prize_title = prize["title"]
        result_text = (
            "<b>🎉 Результат:</b>\n"
            f"Тобі випало: <b>{html.escape(prize_title)}</b>"
        )
        await cb.message.edit_text(result_text, parse_mode="HTML")
        await _notify_admin(cb.from_user, prize_title, cb.message.bot)
    finally:
        _spinning_users.discard(user_id)
