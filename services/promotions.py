"""Persistent promotion switch shared by handlers and synchronous keyboards."""
import aiosqlite
from db.core import DB_PATH

_enabled = True
_piggy_enabled = True
_daily_fortune_enabled = True
_superomatic_enabled = False


def superomatic_enabled():
    return _superomatic_enabled


def superomatic_refund(balance, price, enabled):
    deduction = price * 0.25 if enabled and price >= 100 else 0
    return max(0, int(balance - deduction))


async def set_superomatic(enabled):
    global _superomatic_enabled
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO settings(key, value) VALUES ('superomatic_enabled', ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (int(enabled),)
        )
        await db.commit()
    _superomatic_enabled = enabled
PROMO_BUTTONS = {
    "🤞 Згенерувати промо", "🎟 Ввести промокод", "➕ Створити промокод",
    "🎟 Активні Promo", "🎡 Колесо фортуни", "🎟 Промокоди",
    "➕ Додати промокод", "🎁 Подарунок", "🎁 Скинути подарунки",
}
PROMO_CALLBACKS = {
    "profile:claim_promo", "profile:fortune", "promo_cash_details",
    "copy_codes", "confirm_clear_codes", "clear_codes", "cancel_clear",
    "cancel_promo_gen", "confirm_reset_gifts", "cancel_reset_gifts",
}


def promotions_enabled():
    return _enabled


def piggy_bank_enabled():
    return _piggy_enabled


def daily_fortune_enabled():
    return _daily_fortune_enabled


def daily_fortune_callback(value):
    return bool(value and value.startswith("daily_fortune:"))


def piggy_callback(value):
    return bool(value and value.startswith("piggy:"))


def disabled_callback(value):
    return ((not _enabled and promo_callback(value))
            or (not _piggy_enabled and piggy_callback(value))
            or (not _daily_fortune_enabled and daily_fortune_callback(value)))


def promo_callback(value):
    return bool(value and (value.startswith("fortune:") or value in PROMO_CALLBACKS))


def visible_rows(rows):
    hidden = set() if _enabled else set(PROMO_BUTTONS)
    if not _piggy_enabled:
        hidden.add("🐷 Скарбничка")
    if not _daily_fortune_enabled:
        hidden.add("🎲 Фортуна")
    return [filtered for row in rows if (filtered := [b for b in row if b not in hidden])]


async def load_promotions():
    global _enabled, _piggy_enabled, _daily_fortune_enabled, _superomatic_enabled
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT value FROM settings WHERE key='promotions_enabled'") as cur:
            row = await cur.fetchone()
        async with db.execute("SELECT value FROM settings WHERE key='piggy_bank_enabled'") as cur:
            piggy_row = await cur.fetchone()
        async with db.execute("SELECT value FROM settings WHERE key='daily_fortune_enabled'") as cur:
            fortune_row = await cur.fetchone()
        async with db.execute("SELECT value FROM settings WHERE key='superomatic_enabled'") as cur:
            superomatic_row = await cur.fetchone()
    _enabled = row is None or bool(row[0])
    _piggy_enabled = piggy_row is None or bool(piggy_row[0])
    _daily_fortune_enabled = fortune_row is None or bool(fortune_row[0])
    _superomatic_enabled = superomatic_row is not None and bool(superomatic_row[0])
    return _enabled


async def set_promotions(enabled):
    global _enabled
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO settings(key, value) VALUES ('promotions_enabled', ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (int(enabled),)
        )
        await db.commit()
    _enabled = enabled


async def set_piggy_bank(enabled):
    global _piggy_enabled
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO settings(key, value) VALUES ('piggy_bank_enabled', ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (int(enabled),)
        )
        await db.commit()
    _piggy_enabled = enabled


async def set_daily_fortune(enabled):
    global _daily_fortune_enabled
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO settings(key, value) VALUES ('daily_fortune_enabled', ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (int(enabled),)
        )
        await db.commit()
    _daily_fortune_enabled = enabled
