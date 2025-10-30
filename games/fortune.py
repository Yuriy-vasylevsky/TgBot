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
import aiosqlite
from pathlib import Path

# === Конфіг ===
try:
    from config import ADMIN_ID
except Exception:
    ADMIN_ID = None

try:
    from menu import main_menu  # type: ignore
except Exception:
    main_menu = None

from db import get_user_data  # імпорт даних користувача

DB_PATH = Path(__file__).resolve().parent.parent / "users.db"
router = Router(name="fortune")

FORTUNE_BTN = "🎡 Колесо фортуни"

# === Налаштування ===
REQUIRED_GAMES = 7  # скільки ігор потрібно для доступу

PRIZES = [
    {"title": "🤞 30 грн", "weight": 17, "code": "COUPON_5", "value": 30},
    {"title": "💎 50 грн", "weight": 17, "code": "COUPON_8", "value": 50},
    {"title": "🔥 60 грн", "weight": 15, "code": "COUPON_10", "value": 60},
    {"title": "🎉 100 грн", "weight": 5, "code": "COUPON_10", "value": 100},
    {"title": "🌟 200 грн", "weight": 1, "code": "COUPON_10", "value": 200},
    {"title": "🎟️ Promo", "weight": 7, "code": "NOTHING", "value": 0},
    {"title": "🥂 Джекпот 500 грн", "weight": 0.1, "code": "NOTHING", "value": 500},
    {
        "title": "🔁 Додаткове обертання",
        "weight": 10,
        "code": "EXTRA_SPIN",
        "value": None,
    },
]

_spinning_users: set[int] = set()


# ===============================
#  ФУНКЦІЇ ДЛЯ РОБОТИ З БД
# ===============================
async def ensure_fortune_column():
    """Додає колонку last_fortune_date у таблицю users, якщо її ще нема."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("PRAGMA table_info(users)") as cursor:
            cols = [row[1] for row in await cursor.fetchall()]
        if "last_fortune_date" not in cols:
            await db.execute("ALTER TABLE users ADD COLUMN last_fortune_date TEXT")
            await db.commit()


async def get_last_spin_date(user_id: int) -> str | None:
    """Отримує дату останнього обертання у форматі YYYY-MM-DD."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT last_fortune_date FROM users WHERE user_id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        await cursor.close()
        return row[0] if row and row[0] else None


async def update_last_spin_date(user_id: int):
    """Оновлює дату останнього обертання (зберігає поточну)."""
    today_str = datetime.date.today().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO users (user_id, last_fortune_date)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET last_fortune_date=excluded.last_fortune_date
            """,
            (user_id, today_str),
        )
        await db.commit()


# ===============================
#  ДОПОМОЖНІ ФУНКЦІЇ
# ===============================
def _kb_main() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Крутити колесо 🎯", callback_data="fortune:spin"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📜 Список призів і шансів", callback_data="fortune:prizes"
                )
            ],
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


# ===============================
#  ХЕНДЛЕРИ
# ===============================
@router.message(F.text == FORTUNE_BTN)
@router.message(F.text.lower().contains("колесо фортуни"))
@router.message(F.text == "/fortune")
async def fortune_entry(message: Message):
    await ensure_fortune_column()
    text = (
        "<b>🎡 Колесо фортуни</b>\n\n"
        "Тут ти можеш випробувати удачу. Натисни «Крутити колесо 🎯».\n"
        "За бажанням — подивись список призів та шансів."
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
    await ensure_fortune_column()

    # === 1️⃣ Перевірка кількості ігор ===
    try:
        user_data = await get_user_data(user_id)
        games_played = user_data.get("games_played", 0) if user_data else 0
    except Exception:
        games_played = 0

    if games_played < REQUIRED_GAMES:
        await cb.answer()
        await cb.message.answer(
            f"⚠️ Зберіть {REQUIRED_GAMES} 🎟️ щоб відкрити доступ\n"
            f"🎮 У вас зараз: <b>{games_played} 🎟️</b>\n\n"
            f"🔓 Оновлюється щопонеділка 🔓",
            parse_mode="HTML",
        )
        return

    # === 2️⃣ Перевірка дати останнього спіну ===
    last_spin_date = await get_last_spin_date(user_id)
    today = datetime.date.today().isoformat()

    if last_spin_date == today:
        await cb.answer()
        await cb.message.answer(
            f"⚠️ Ви вже крутили колесо сьогодні!\n\n"
            f"🕒 Наступна спроба буде доступна <b> після 03:00 нового дня</b>.",
            parse_mode="HTML",
        )
        return

    if user_id in _spinning_users:
        await cb.answer("Зачекай, колесо вже крутиться…", show_alert=False)
        return

    _spinning_users.add(user_id)
    await update_last_spin_date(user_id)

    try:
        await cb.answer()
        await _animate_spin(cb)

        prize = _choose_prize()
        prize_title = prize["title"]

        result_text = (
            f"<b>🎉 Результат:</b>\nТобі випало: <b>{html.escape(prize_title)}</b>"
        )
        await cb.message.edit_text(result_text, parse_mode="HTML")

        await _notify_admin(cb.from_user, prize_title, cb.message.bot)

        if prize["code"] == "EXTRA_SPIN":
            await asyncio.sleep(0.5)
            await cb.message.answer("🔁 Отримано додаткове обертання! Кручу ще раз…")
            await spin_again(cb)
    finally:
        _spinning_users.discard(user_id)


async def spin_again(cb: CallbackQuery):
    """Повторне обертання без cb.answer()."""
    user_id = cb.from_user.id
    _spinning_users.add(user_id)
    try:
        await _animate_spin(cb)
        prize = _choose_prize()
        prize_title = prize["title"]
        result_text = (
            f"<b>🎉 Результат:</b>\nТобі випало: <b>{html.escape(prize_title)}</b>"
        )
        await cb.message.edit_text(result_text, parse_mode="HTML")
        await _notify_admin(cb.from_user, prize_title, cb.message.bot)
    finally:
        _spinning_users.discard(user_id)
