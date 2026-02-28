import asyncio
import random
import html
import datetime
import aiosqlite
from pathlib import Path
from aiogram import Router, F, types
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    Message,
    CallbackQuery,
)

# Імпорт з db
from db import (
    ensure_users_table_and_columns,
    get_user_data,
    save_notification,
)

DB_PATH = Path(__file__).resolve().parent.parent / "users.db"
router = Router(name="daily_bonus")

BONUS_BTN = "🎁 Щоденний бонус"
REQUIRED_GAMES = 1

# ==========================
# НАГОРОДИ
# ==========================
PRIZES = [
    {"title": "🎟️ 1 промо", "weight": 5, "value": 1},
    {"title": "💰 30 грн", "weight": 5, "value": 5},
    {"title": "✨10% до депозиту", "weight": 40, "value": 40},
    {"title": "✨15% до депозиту", "weight": 15, "value": 50},
    {"title": "✨20% до депозиту", "weight": 10, "value": 100},
    {"title": "🤪 Спробуйте завтра", "weight": 40, "value": 200},
]

_spinning_users: set[int] = set()


# ===============================
# ДОПОМІЖНІ ФУНКЦІЇ
# ===============================
def _kb_bonus() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎯 Отримати бонус", callback_data="bonus:spin")],
            [InlineKeyboardButton(text="📜 Список бонусів", callback_data="bonus:list")],
        ]
    )


def _format_prize_list() -> str:
    total = sum(p["weight"] for p in PRIZES)
    lines = ["<b>🎁 Щоденний бонус — шанси</b>\n"]
    for i, p in enumerate(PRIZES, 1):
        chance = (p["weight"] / total) * 100
        lines.append(f"{i}. {p['title']} — <code>{chance:.1f}%</code>")
    return "\n".join(lines)


def _choose_bonus() -> dict:
    weights = [p["weight"] for p in PRIZES]
    return random.choices(PRIZES, weights=weights, k=1)[0]


async def _animate(cb: CallbackQuery):
    frames = ["🎲          ", "    🎲      ", "        🎲  ", "      🎲    ", "  🎲        "]
    for _ in range(3):
        for f in frames:
            try:
                await cb.message.edit_text(f"<b>Крутиться бонус...</b>\n<code>{f}</code>", parse_mode="HTML")
            except Exception:
                pass
            await asyncio.sleep(0.2)


async def _notify_admin(user: types.User, prize_title: str, bot):
    try:
        from config import ADMIN_ID
        if not ADMIN_ID:
            return
        text = (
            "🎁 <b>Щоденний бонус отримано</b>\n"
            f"👤 {('@'+user.username) if user.username else html.escape(user.full_name)}\n"
            f"🔗 <a href='tg://user?id={user.id}'>Профіль</a>\n"
            f"🏅 Бонус: <b>{html.escape(prize_title)}</b>"
        )
        await bot.send_message(ADMIN_ID, text, parse_mode="HTML")

        await save_notification(
            user.id,
            user.username or "-",
            user.full_name or "-",
            "bonus",
            f"🎁 Щоденний бонус — {html.escape(prize_title)}",
        )
    except Exception as e:
        print("notify_admin daily bonus error:", e)


# ===============================
# ХЕНДЛЕРИ
# ===============================
@router.message(F.text == BONUS_BTN)
@router.message(F.text.lower().contains("бонус"))
@router.message(F.text == "/bonus")
async def bonus_entry(message: Message):
    await ensure_users_table_and_columns()

    text = (
        "<b>🎁 Щоденний бонус</b>\n\n"
        "Отримуй нагороду кожен день! Можна тільки 1 раз на добу.\n"
        "Натисни кнопку нижче, щоб дізнатись, що тобі випаде!"
    )
    await message.answer(text, reply_markup=_kb_bonus(), parse_mode="HTML")


@router.callback_query(F.data == "bonus:list")
async def show_bonus_list(cb: CallbackQuery):
    await cb.answer()
    await cb.message.edit_text(_format_prize_list(), reply_markup=_kb_bonus(), parse_mode="HTML")


@router.callback_query(F.data == "bonus:spin")
async def spin_bonus(cb: CallbackQuery):
    user_id = cb.from_user.id
    await ensure_users_table_and_columns()

    # Перевірка кількості ігор
    try:
        user_data = await get_user_data(user_id)
        games_played = user_data.get("games_played", 0) if user_data else 0
    except:
        games_played = 0

    if games_played < REQUIRED_GAMES:
        await cb.answer()
        await cb.message.answer(
            f"⚠️ Зберіть {REQUIRED_GAMES} PROMO 🎟️ щоб відкрити доступ\n"
            f"🎮 У вас зараз: {games_played} PROMO\n\n"
            f"🔓 Оновлюється щопонеділка 🔓",
            parse_mode="HTML",
        )
        return

    # Перевірка дати
    last_date = await get_last_bonus_date(user_id)
    today = datetime.date.today().isoformat()

    if last_date == today:
        await cb.answer()
        await cb.message.answer(
            "⚠️ Ви вже отримали свій бонус сьогодні!\n"
            "🎁 Поверніться завтра після <b>03:00</b>.",
            parse_mode="HTML",
        )
        return

    if user_id in _spinning_users:
        await cb.answer("Зачекай, бонус крутиться...", show_alert=False)
        return

    _spinning_users.add(user_id)

    try:
        await cb.answer()
        await _animate(cb)

        prize = _choose_bonus()
        await update_last_bonus_date(user_id)

        result = f"<b>🎉 Вітаємо!</b>\nТвій сьогоднішній бонус: <b>{prize['title']}</b>"
        await cb.message.edit_text(result, parse_mode="HTML")

        await _notify_admin(cb.from_user, prize["title"], cb.message.bot)

    finally:
        _spinning_users.discard(user_id)


# ===============================
# РОБОТА З БД
# ===============================
async def get_last_bonus_date(user_id: int) -> str | None:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT last_daily_bonus_date FROM users WHERE user_id = ?",
            (user_id,),
        )
        row = await cursor.fetchone()
        return row[0] if row else None


async def update_last_bonus_date(user_id: int):
    today_str = datetime.date.today().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO users (user_id, last_daily_bonus_date)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET last_daily_bonus_date = excluded.last_daily_bonus_date
            """,
            (user_id, today_str),
        )
        await db.commit()