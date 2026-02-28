

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
    User,
)

import aiosqlite                     # ← додай цей
from pathlib import Path

# === Конфіг ===
try:
    from config import ADMIN_ID
except Exception:
    ADMIN_ID = None

# Імпорт з db (тепер усе через єдину функцію)
from db import (
    ensure_users_table_and_columns,
    get_user_data,
    add_money_win,
    save_notification,
)

DB_PATH = Path(__file__).resolve().parent.parent / "users.db"
router = Router(name="fortune")

FORTUNE_BTN = "🎡 Колесо фортуни"
REQUIRED_GAMES = 7

# ==========================
# КОНФІГУРАЦІЯ ПРИЗІВ
# ==========================
PRIZES = [
    {"title": "🤞 30 грн",          "code": "COUPON_5",   "value": 30},
    {"title": "💎 50 грн",          "code": "COUPON_8",   "value": 50},
    {"title": "🔥 60 грн",          "code": "COUPON_10",  "value": 60},
    {"title": "🎉 100 грн",         "code": "COUPON_10",  "value": 100},
    {"title": "🌟 200 грн",         "code": "COUPON_10",  "value": 200},
    {"title": "🎟️ Promo",           "code": "NOTHING",    "value": 0},
    {"title": "🥂 Джекпот 500 грн", "code": "NOTHING",    "value": 500},
    {"title": "🔁 Додаткове обертання", "code": "EXTRA_SPIN", "value": None},
]

WEIGHTS = {
    "🤞 30 грн":                    10,
    "💎 50 грн":                   2,
    "🔥 60 грн":                    0,
    "🎉 100 грн":                   0,
    "🌟 200 грн":                   0,
    "🎟️ Promo":                    2,
    "🥂 Джекпот 500 грн":           0,
    "🔁 Додаткове обертання":      0,
}

DISPLAY_CHANCES = {
    "🤞 30 грн":                    "≈ 25%",
    "💎 50 грн":                    "≈ 20%",
    "🔥 60 грн":                    "≈ 15%",
    "🎉 100 грн":                   "≈ 10%",
    "🌟 200 грн":                   "≈ 5%",
    "🎟️ Promo":                    "15%",
    "🥂 Джекпот 500 грн":           "≈ 1%",
    "🔁 Додаткове обертання":      "≈ 9%",
}

def _validate_config():
    prize_titles = {p["title"] for p in PRIZES}
    if prize_titles != set(WEIGHTS.keys()):
        raise ValueError("❌ Неузгодженість PRIZES і WEIGHTS!")
    if prize_titles != set(DISPLAY_CHANCES.keys()):
        raise ValueError("❌ Неузгодженість PRIZES і DISPLAY_CHANCES!")
    print("✅ Fortune config validated successfully")

_validate_config()

# Глобальний стан
_spinning_users: set[int] = set()
_spin_lock = asyncio.Lock()

# ===============================
# ДОПОМІЖНІ ФУНКЦІЇ
# ===============================
def _kb_main() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Крутити колесо 🎯", callback_data="fortune:spin")],
            [InlineKeyboardButton(text="📜 Список призів і шансів", callback_data="fortune:prizes")],
        ]
    )


def _format_prize_table() -> str:
    lines = ["<b>🎡 Колесо фортуни — призи та шанси</b>\n"]
    for i, prize in enumerate(PRIZES, 1):
        title = prize["title"]
        display_text = DISPLAY_CHANCES[title]
        lines.append(f"{i:>2}. {title} — <code>{display_text}</code>")
    lines.append("\nНатисни «Крутити колесо 🎯», щоб спробувати удачу!")
    return "\n".join(lines)


def _choose_prize() -> dict:
    titles = [p["title"] for p in PRIZES]
    weights_list = [WEIGHTS[t] for t in titles]
    chosen_title = random.choices(titles, weights=weights_list, k=1)[0]
    for prize in PRIZES:
        if prize["title"] == chosen_title:
            return prize
    raise RuntimeError("Приз не знайдено")


async def _animate_spin(message: Message):
    frames = [
        "| 🎯                    ", "|     🎯                ", "|         🎯            ",
        "|             🎯        ", "|                 🎯    ", "|                     🎯",
        "|                 🎯    ", "|             🎯        ", "|         🎯            ",
        "|     🎯                ",
    ]
    for _ in range(2):
        for fr in frames:
            try:
                await message.edit_text(f"<b>Колесо крутиться...</b>\n<code>{fr}</code>", parse_mode="HTML")
            except Exception:
                pass
            await asyncio.sleep(0.22)
    for fr in frames[:5]:
        try:
            await message.edit_text(f"<b>Зупиняється...</b>\n<code>{fr}</code>", parse_mode="HTML")
        except Exception:
            pass
        await asyncio.sleep(0.28)


async def _notify_admin(user: User, prize_title: str, bot):
    if not ADMIN_ID:
        return
    try:
        text = (
            "🎡 <b>Колесо фортуни — 🍀</b>\n"
            f"👤 {('@' + user.username) if user.username else user.full_name}\n"
            f"🔗 <a href='tg://user?id={user.id}'>Профіль</a>\n"
            f"🎁 Приз: <b>{html.escape(prize_title)}</b>"
        )
        await bot.send_message(ADMIN_ID, text, parse_mode="HTML")

        await save_notification(
            user.id,
            user.username or "-",
            user.full_name or "-",
            "fortune",
            f"🎡 Колесо фортуни — {prize_title}",
        )
    except Exception as e:
        print(f"notify_admin error: {e}")


# ===============================
# ОСНОВНА ЛОГІКА СПІНУ
# ===============================
async def perform_spin(cb: CallbackQuery, is_first_spin: bool = True):
    """Універсальна функція для звичайного + додаткового обертання"""
    user_id = cb.from_user.id
    user = cb.from_user

    async with _spin_lock:
        if user_id in _spinning_users:
            await cb.answer("Колесо вже крутиться…", show_alert=True)
            return
        _spinning_users.add(user_id)

    try:
        if is_first_spin:
            await update_last_spin_date(user_id)
            await cb.answer()

        await _animate_spin(cb.message)

        prize = _choose_prize()
        prize_title = prize["title"]

        await cb.message.edit_text(
            f"<b>🎉 Результат:</b>\nТобі випало: <b>{html.escape(prize_title)}</b>",
            parse_mode="HTML",
        )

        await _notify_admin(user, prize_title, cb.bot)

        if prize.get("value") and prize["value"] > 0:
            await add_money_win(user_id, prize["value"])

        if prize["code"] == "EXTRA_SPIN":
            await asyncio.sleep(0.8)
            await cb.message.answer("🔁 Отримано додаткове обертання! Кручу ще раз…")
            await perform_spin(cb, is_first_spin=False)

    finally:
        _spinning_users.discard(user_id)


# ===============================
# ХЕНДЛЕРИ
# ===============================
@router.message(F.text == FORTUNE_BTN)
@router.message(F.text.lower().contains("колесо фортуни"))
@router.message(F.text == "/fortune")
async def fortune_entry(message: Message):
    await ensure_users_table_and_columns()   # ← головний виклик

    text = (
        "<b>🎡 Колесо фортуни</b>\n\n"
        "Тут ти можеш випробувати удачу.\n"
        "Натисни «Крутити колесо 🎯»."
    )
    await message.answer(text, reply_markup=_kb_main(), parse_mode="HTML")


@router.callback_query(F.data == "fortune:prizes")
async def show_prizes(cb: CallbackQuery):
    await cb.answer()
    await cb.message.edit_text(
        _format_prize_table(), reply_markup=_kb_main(), parse_mode="HTML"
    )


@router.callback_query(F.data == "fortune:spin")
async def spin(cb: CallbackQuery):
    user_id = cb.from_user.id
    await ensure_users_table_and_columns()   # ← головний виклик

    # Перевірка кількості ігор
    try:
        user_data = await get_user_data(user_id)
        games_played = user_data.get("games_played", 0) if user_data else 0
    except Exception:
        games_played = 0

    if games_played < REQUIRED_GAMES:
        await cb.answer()
        await cb.message.answer(
            f"⚠️ Зберіть {REQUIRED_GAMES} PROMO 🎟️ щоб відкрити доступ\n"
            f"🎮 У вас зараз: <b>{games_played} 🎟️</b>\n\n"
            f"🔓 Оновлюється щопонеділка",
            parse_mode="HTML",
        )
        return

    # Перевірка дати
    last_spin_date = await get_last_spin_date(user_id)
    today = datetime.date.today().isoformat()

    if last_spin_date == today:
        await cb.answer()
        await cb.message.answer(
            "⚠️ Ви вже крутили колесо сьогодні!\n\n"
            "🕒 Наступна спроба — після 03:00 нового дня.",
            parse_mode="HTML",
        )
        return

    await perform_spin(cb, is_first_spin=True)


# ===============================
# РОБОТА З БД
# ===============================
async def get_last_spin_date(user_id: int) -> str | None:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT last_fortune_date FROM users WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None


async def update_last_spin_date(user_id: int):
    today_str = datetime.date.today().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO users (user_id, last_fortune_date)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET last_fortune_date = excluded.last_fortune_date
            """,
            (user_id, today_str),
        )
        await db.commit()
