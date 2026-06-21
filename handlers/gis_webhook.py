"""
Серверна частина GIS-партнерського API.

Сюди стукається ігрова Платформа під час сесії гравця (вебхуки), а не навпаки.
Підключається до вже існуючого aiohttp-застосунку бота (того ж, де приймається
Telegram webhook) функцією setup_gis_routes(app).

URI, по якому Платформа має слати запити:
    {API.URI}/check.session
    {API.URI}/check.balance
    {API.URI}/withdraw.bet
    {API.URI}/deposit.win
    {API.URI}/trx.cancel
    {API.URI}/trx.complete

{API.URI} прописується в особистому кабінеті Партнера на стороні Платформи.

TODO перед продакшеном:
- звірити точні поля у "response" кожного методу з реальними CURL-прикладами
  з документації / особистого кабінету (тут вони відтворені за описом, а не
  за буквальним прикладом)
- підставити свій GIS_PARTNER_ID / GIS_SECRET_KEY (нижче — заглушки)
- переконатись, що конвертація копійки <-> грн відповідає твоїй денoмінації
"""

import hashlib
import logging
import time

import aiosqlite
from aiohttp import web

from db import get_balance, add_to_balance

log = logging.getLogger(__name__)

# === Дані партнера на GIS-платформі (видані в особистому кабінеті) ===
GIS_PARTNER_ID = "Subagent"      # TODO: підставити реальний Ідентифікатор Партнера
GIS_SECRET_KEY = "rbi9sshgtrhcnjlm970hgcep37ckrm97gthhtyju36nj1jfngt2g5f9"    # TODO: підставити реальний Секретний ключ

# Окрема sqlite-база для сесій GIS і вже оброблених транзакцій (ідемпотентність).
# За бажання можна перенести в основну БД бота — структура максимально проста.
GIS_DB_PATH = "gis.db"


# ==================== Ініціалізація сховища сесій/транзакцій ====================

async def init_gis_db():
    async with aiosqlite.connect(GIS_DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS gis_sessions (
                session_id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                currency TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                closed INTEGER NOT NULL DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS gis_transactions (
                trx_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                kind TEXT NOT NULL,           -- withdraw.bet / deposit.win
                amount_kopecks INTEGER NOT NULL,
                cancelled INTEGER NOT NULL DEFAULT 0,
                created_at INTEGER NOT NULL
            )
        """)
        await db.commit()


async def create_gis_session(session_id: str, user_id: int, currency: str):
    """Викликається з клієнтської частини (handlers/matic_gis.py) одразу після init.session."""
    async with aiosqlite.connect(GIS_DB_PATH) as db:
        await db.execute(
            "INSERT INTO gis_sessions (session_id, user_id, currency, created_at) VALUES (?, ?, ?, ?)",
            (session_id, user_id, currency, int(time.time())),
        )
        await db.commit()


async def get_gis_session(session_id: str):
    async with aiosqlite.connect(GIS_DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM gis_sessions WHERE session_id = ?", (session_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def get_processed_trx(trx_id: str):
    async with aiosqlite.connect(GIS_DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM gis_transactions WHERE trx_id = ?", (trx_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def save_trx(trx_id: str, session_id: str, kind: str, amount_kopecks: int):
    async with aiosqlite.connect(GIS_DB_PATH) as db:
        await db.execute(
            "INSERT INTO gis_transactions (trx_id, session_id, kind, amount_kopecks, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (trx_id, session_id, kind, amount_kopecks, int(time.time())),
        )
        await db.commit()


async def mark_trx_cancelled(trx_id: str):
    async with aiosqlite.connect(GIS_DB_PATH) as db:
        await db.execute(
            "UPDATE gis_transactions SET cancelled = 1 WHERE trx_id = ?", (trx_id,)
        )
        await db.commit()


async def mark_session_closed(session_id: str):
    async with aiosqlite.connect(GIS_DB_PATH) as db:
        await db.execute(
            "UPDATE gis_sessions SET closed = 1 WHERE session_id = ?", (session_id,)
        )
        await db.commit()


async def get_active_session_for_user(user_id: int):
    """Остання незакрита сесія користувача (на випадок, якщо повідомлення з кнопкою загубилось)."""
    async with aiosqlite.connect(GIS_DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM gis_sessions WHERE user_id = ? AND closed = 0 "
            "ORDER BY created_at DESC LIMIT 1",
            (user_id,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


# ==================== Конвертація копійки/центи <-> грн ====================
# Платформа оперує сумами в копійках/центах. Бот зберігає баланс у грн (int).
# Якщо у тебе інша деномінація — підправ тут.

def kopecks_to_uah(amount_kopecks: int) -> int:
    return int(amount_kopecks) // 100


def uah_to_kopecks(amount_uah) -> int:
    return int(round(float(amount_uah) * 100))


# ==================== Перевірка підпису ====================

def verify_signature(method_name: str, params: dict) -> bool:
    """
    method_name — рядок виду "check.session", "withdraw.bet" і т.п. (serviceName.methodName)
    params — усі параметри тіла POST-запиту (включно з sign)
    """
    received_sign = str(params.get("sign", ""))

    filtered = {
        k: v for k, v in params.items()
        if k != "sign" and k != "meta" and not str(k).startswith("partner.")
    }

    joined = "&".join(f"{k}={filtered[k]}" for k in sorted(filtered.keys()))
    raw = f"{joined}&{method_name}&{GIS_PARTNER_ID}&{GIS_SECRET_KEY}"
    expected = hashlib.md5(raw.encode("utf-8")).hexdigest()

    return expected == received_sign


def make_response(method: str, status: int, response: dict | None = None) -> dict:
    return {
        "method": method,
        "status": status,
        "response": response or {},
    }


# ==================== Обробники методів ====================

async def handle_check_session(request: web.Request):
    params = await request.json()
    method = "check.session"

    if not verify_signature(method, params):
        log.warning("GIS check.session: bad signature, params=%s", params)
        return web.json_response(make_response(method, 500), status=200)

    session = await get_gis_session(params.get("session", ""))
    if not session or session["closed"]:
        return web.json_response(make_response(method, 500), status=200)

    # TODO: звірити чи Платформа очікує тут якісь поля (наприклад id_player)
    return web.json_response(make_response(method, 200, {}), status=200)


async def handle_check_balance(request: web.Request):
    params = await request.json()
    method = "check.balance"

    if not verify_signature(method, params):
        log.warning("GIS check.balance: bad signature, params=%s", params)
        return web.json_response(make_response(method, 500), status=200)

    session = await get_gis_session(params.get("session", ""))
    if not session or session["closed"]:
        return web.json_response(make_response(method, 500), status=200)

    balance_uah = await get_balance(session["user_id"])
    return web.json_response(
        make_response(method, 200, {"balance": uah_to_kopecks(balance_uah)}),
        status=200,
    )


async def handle_withdraw_bet(request: web.Request):
    params = await request.json()
    method = "withdraw.bet"

    if not verify_signature(method, params):
        log.warning("GIS withdraw.bet: bad signature, params=%s", params)
        return web.json_response(make_response(method, 500), status=200)

    session_id = params.get("session", "")
    trx_id = str(params.get("trx_id", ""))
    amount_kopecks = int(params.get("amount", 0))

    session = await get_gis_session(session_id)
    if not session or session["closed"]:
        return web.json_response(make_response(method, 500), status=200)

    user_id = session["user_id"]

    # Ідемпотентність: якщо ця транзакція вже оброблена — повертаємо поточний
    # баланс без повторного списання.
    existing = await get_processed_trx(trx_id)
    if existing:
        balance_uah = await get_balance(user_id)
        return web.json_response(
            make_response(method, 200, {"balance": uah_to_kopecks(balance_uah)}),
            status=200,
        )

    amount_uah = kopecks_to_uah(amount_kopecks)
    balance_uah = await get_balance(user_id)

    if balance_uah < amount_uah:
        # Недостатньо коштів — Платформа за документацією трактує статус 500-599
        # як коректну відмову і сама скасує хід.
        return web.json_response(make_response(method, 500), status=200)

    await add_to_balance(user_id, -amount_uah)
    await save_trx(trx_id, session_id, "withdraw.bet", amount_kopecks)

    new_balance_uah = await get_balance(user_id)
    return web.json_response(
        make_response(method, 200, {"balance": uah_to_kopecks(new_balance_uah)}),
        status=200,
    )


async def handle_deposit_win(request: web.Request):
    params = await request.json()
    method = "deposit.win"

    if not verify_signature(method, params):
        log.warning("GIS deposit.win: bad signature, params=%s", params)
        return web.json_response(make_response(method, 500), status=200)

    session_id = params.get("session", "")
    trx_id = str(params.get("trx_id", ""))
    amount_kopecks = int(params.get("amount", 0))

    session = await get_gis_session(session_id)
    if not session:
        return web.json_response(make_response(method, 500), status=200)

    user_id = session["user_id"]

    existing = await get_processed_trx(trx_id)
    if existing:
        balance_uah = await get_balance(user_id)
        return web.json_response(
            make_response(method, 200, {"balance": uah_to_kopecks(balance_uah)}),
            status=200,
        )

    amount_uah = kopecks_to_uah(amount_kopecks)

    # deposit.win — за документацією "Proceed on fail": нарахування виграшу
    # не повинно блокуватись бізнес-логікою, лише підписом/сесією вище.
    await add_to_balance(user_id, amount_uah)
    await save_trx(trx_id, session_id, "deposit.win", amount_kopecks)

    new_balance_uah = await get_balance(user_id)
    return web.json_response(
        make_response(method, 200, {"balance": uah_to_kopecks(new_balance_uah)}),
        status=200,
    )


async def handle_trx_cancel(request: web.Request):
    """Платформа повідомляє про скасування раніше зробленої withdraw.bet — повертаємо кошти."""
    params = await request.json()
    method = "trx.cancel"

    if not verify_signature(method, params):
        log.warning("GIS trx.cancel: bad signature, params=%s", params)
        return web.json_response(make_response(method, 500), status=200)

    trx_id = str(params.get("trx_id", ""))
    session_id = params.get("session", "")

    session = await get_gis_session(session_id)
    if not session:
        return web.json_response(make_response(method, 500), status=200)

    trx = await get_processed_trx(trx_id)
    if trx and trx["kind"] == "withdraw.bet" and not trx["cancelled"]:
        amount_uah = kopecks_to_uah(trx["amount_kopecks"])
        await add_to_balance(session["user_id"], amount_uah)
        await mark_trx_cancelled(trx_id)

    return web.json_response(make_response(method, 200, {}), status=200)


async def handle_trx_complete(request: web.Request):
    """Платформа підтверджує, що транзакцію (зазвичай deposit.win) треба довиконати."""
    params = await request.json()
    method = "trx.complete"

    if not verify_signature(method, params):
        log.warning("GIS trx.complete: bad signature, params=%s", params)
        return web.json_response(make_response(method, 500), status=200)

    trx_id = str(params.get("trx_id", ""))
    session_id = params.get("session", "")
    amount_kopecks = int(params.get("amount", 0))

    session = await get_gis_session(session_id)
    if not session:
        return web.json_response(make_response(method, 500), status=200)

    existing = await get_processed_trx(trx_id)
    if not existing:
        # Якщо deposit.win раніше не дійшов — донараховуємо зараз.
        amount_uah = kopecks_to_uah(amount_kopecks)
        await add_to_balance(session["user_id"], amount_uah)
        await save_trx(trx_id, session_id, "deposit.win", amount_kopecks)

    return web.json_response(make_response(method, 200, {}), status=200)


# ==================== Реєстрація роутів ====================

def setup_gis_routes(app: web.Application):
    """Викликати один раз при старті, передавши вже існуючий aiohttp Application бота."""
    app.router.add_post("/check.session", handle_check_session)
    app.router.add_post("/check.balance", handle_check_balance)
    app.router.add_post("/withdraw.bet", handle_withdraw_bet)
    app.router.add_post("/deposit.win", handle_deposit_win)
    app.router.add_post("/trx.cancel", handle_trx_cancel)
    app.router.add_post("/trx.complete", handle_trx_complete)