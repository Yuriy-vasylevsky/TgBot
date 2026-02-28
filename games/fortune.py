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

import aiosqlite
from pathlib import Path

# Імпорт з db
from db import (
    ensure_users_table_and_columns,
    get_user_data,
    add_money_win,
    save_notification,
)

DB_PATH = Path(__file__).resolve().parent.parent / "users.db"
router = Router(name="fortune")

FORTUNE_BTN = "🎡 Колесо фортуни"
REQUIRED_PROMO = 1

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
    if prize_titles != set(WEIGHTS.keys()) or prize_titles != set(DISPLAY_CHANCES.keys()):
        raise ValueError("❌ Неузгодженість PRIZES / WEIGHTS / DISPLAY_CHANCES!")
    print("✅ Fortune config validated successfully")

_validate_config()

_spinning_users: set[int] = set()
_spin_lock = asyncio.Lock()

# ===============================
# ДОПОМІЖНІ ФУНКЦІЇ
# ===============================
def _kb_main(promo_count: int) -> InlineKeyboardMarkup:
    status = f" {promo_count}/1" if promo_count >= 1 else " 0/1"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"Крутити колесо 🎯{status}", callback_data="fortune:spin")],
            [InlineKeyboardButton(text="📜 Список призів і шансів", callback_data="fortune:prizes")],
        ]
    )


def _format_prize_table() -> str:
    lines = ["<b>🎡 Колесо фортуни — призи та шанси</b>\n"]
    for i, prize in enumerate(PRIZES, 1):
        lines.append(f"{i:>2}. {prize['title']} — <code>{DISPLAY_CHANCES[prize['title']]}</code>")
    lines.append("\nНатисни кнопку вище, щоб спробувати удачу!")
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
    try:
        from config import ADMIN_ID
        if not ADMIN_ID:
            return
        text = f"🎡 <b>Колесо фортуни</b>\n👤 {('@' + user.username) if user.username else user.full_name}\n🎁 {html.escape(prize_title)}"
        await bot.send_message(ADMIN_ID, text, parse_mode="HTML")
        await save_notification(user.id, user.username or "-", user.full_name or "-", "fortune", f"🎡 Колесо фортуни — {prize_title}")
    except Exception as e:
        print(f"notify_admin error: {e}")


# ===============================
# СПИСАННЯ ПРОМО
# ===============================
async def spend_one_promo(user_id: int) -> bool:
    """Списує 1 промо (games_played)"""
    print(f"🔄 spend_one_promo: забезпечуємо таблицю для {user_id}")
    await ensure_users_table_and_columns()

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT games_played FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if not row or row[0] < 1:
                print(f"❌ У користувача {user_id} немає промо")
                return False

        await db.execute("UPDATE users SET games_played = games_played - 1 WHERE user_id = ?", (user_id,))
        await db.commit()
        print(f"✅ Списано 1 промо для {user_id}")
        return True


async def perform_spin(cb: CallbackQuery, is_first_spin: bool = True):
    user_id = cb.from_user.id
    user = cb.from_user

    async with _spin_lock:
        if user_id in _spinning_users:
            await cb.answer("Колесо вже крутиться…", show_alert=True)
            return
        _spinning_users.add(user_id)

    try:
        if is_first_spin:
            await cb.answer()

        await _animate_spin(cb.message)

        prize = _choose_prize()
        prize_title = prize["title"]

        await cb.message.edit_text(f"<b>🎉 Результат:</b>\nТобі випало: <b>{html.escape(prize_title)}</b>", parse_mode="HTML")

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
    await ensure_users_table_and_columns()
    user_data = await get_user_data(message.from_user.id)
    promo = user_data.get("games_played", 0) if user_data else 0

    text = (
        "<b>🎡 Колесо фортуни</b>\n\n"
        "Кожен спін коштує <b>1 промокод</b>.\n"
        f"У тебе зараз: <b>{promo} промокодів</b>"
    )
    await message.answer(text, reply_markup=_kb_main(promo), parse_mode="HTML")


@router.callback_query(F.data == "fortune:prizes")
async def show_prizes(cb: CallbackQuery):
    await cb.answer()
    await cb.message.edit_text(_format_prize_table(), reply_markup=_kb_main(0), parse_mode="HTML")


@router.callback_query(F.data == "fortune:spin")
async def spin(cb: CallbackQuery):
    user_id = cb.from_user.id
    await ensure_users_table_and_columns()

    user_data = await get_user_data(user_id)
    promo = user_data.get("games_played", 0) if user_data else 0

    if promo < REQUIRED_PROMO:
        await cb.answer("❌ У тебе немає промокодів!", show_alert=True)
        return

    success = await spend_one_promo(user_id)
    if not success:
        await cb.answer("❌ Не вдалося списати промокод", show_alert=True)
        return

    await perform_spin(cb, is_first_spin=True)


# ADMIN_ID
try:
    from config import ADMIN_ID
except Exception:
    ADMIN_ID = None