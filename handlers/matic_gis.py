import uuid
import logging

import aiohttp
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from db import get_balance
from handlers.gis_webhook import (
    GIS_PARTNER_ID,
    create_gis_session,
    get_active_session_for_user,
    mark_session_closed,
)

router = Router(name="matic_gis")
log = logging.getLogger(__name__)

# =============================================
# УВАГА! Ці URL — різні!
# =============================================

# 1. URL твого webhook (той, що ти вказував в особистому кабінеті GIS)
GIS_WEBHOOK_BASE = "http://77.42.71.244:3000"

# 2. URL GIS-платформи (той, з якого приходять вебхуки + init.session)
#    ←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←
GIS_PLATFORM_URL = "https://billing.superplat.pw"  # ←←← СЮДИ РЕАЛЬНИЙ!

GIS_API_URL = f"{GIS_PLATFORM_URL}/api/gisv2/"
GIS_INIT_SESSION_URL = GIS_API_URL + "init.session"
GIS_CLOSE_SESSION_URL = GIS_API_URL + "close.session"

GIS_GAME_ID = 0                     # ← Зміни на реальний ID гри Matic
GIS_DEFAULT_CURRENCY = "UAH"


@router.message(F.text == "🎰 Matic")
async def matic_menu(message: Message):
    user_id = message.from_user.id
    balance = await get_balance(user_id)

    if balance <= 0:
        await message.answer("❌ Недостатньо коштів на балансі для запуску гри.")
        return

    session_id = uuid.uuid4().hex

    payload = {
        "currency": GIS_DEFAULT_CURRENCY,
        "game.id": GIS_GAME_ID,
        "partner.alias": GIS_PARTNER_ID,
        "partner.session": session_id,
    }

    try:
        async with aiohttp.ClientSession() as http:
            async with http.post(
                GIS_INIT_SESSION_URL,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    log.error("GIS init.session HTTP %d: %s", resp.status, text)
                    await message.answer("❌ Помилка сервера GIS (HTTP %d)", resp.status)
                    return
                data = await resp.json()
    except aiohttp.ClientConnectorError:
        log.error("Cannot connect to GIS platform")
        await message.answer("❌ Не вдалося підключитися до GIS платформи.")
        return
    except Exception as e:
        log.exception("GIS init.session failed")
        await message.answer("❌ Технічна помилка при запуску гри.")
        return

    response = data.get("response") or {}
    client_dist = response.get("clientDist")
    token = response.get("token")

    if not client_dist or not token:
        log.error("GIS init.session: неправильна відповідь: %s", data)
        await message.answer("❌ Платформа не повернула посилання на гру.")
        return

    game_url = f"{client_dist}?t={token}"

    await create_gis_session(session_id=session_id, user_id=user_id, currency=GIS_DEFAULT_CURRENCY)

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎰 Грати в Matic", url=game_url)],
            [InlineKeyboardButton(text="🔒 Закрити сесію", callback_data=f"matic_close_{session_id}")]
        ]
    )

    await message.answer(
        f"🎰 <b>Matic готовий!</b>\n\n"
        f"💳 Баланс: {balance} грн\n\n"
        f"Ставки і виграші обробляються автоматично.",
        parse_mode="HTML",
        reply_markup=kb
    )


# === Закриття сесії ===
async def close_matic_session(target_message: Message, user_id: int, session_id: str):
    payload = {
        "partner.alias": GIS_PARTNER_ID,
        "partner.session": session_id,
    }

    try:
        async with aiohttp.ClientSession() as http:
            async with http.post(
                GIS_CLOSE_SESSION_URL,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=8),
            ) as resp:
                data = await resp.json()
    except Exception:
        log.exception("GIS close.session failed")
        await target_message.answer("❌ Не вдалося закрити сесію.")
        return

    if data.get("status") != 200:
        log.error("GIS close.session error: %s", data)
        await target_message.answer("❌ Помилка платформи при закритті сесії.")
        return

    await mark_session_closed(session_id)
    await target_message.answer(
        f"✅ Сесію Matic закрито.\n💳 Баланс: {await get_balance(user_id)} грн"
    )


@router.callback_query(F.data.startswith("matic_close_"))
async def matic_close_callback(callback: CallbackQuery):
    session_id = callback.data.removeprefix("matic_close_")
    user_id = callback.from_user.id
    await callback.answer("🔄 Закриваємо сесію...")
    await callback.message.edit_reply_markup(reply_markup=None)
    await close_matic_session(callback.message, user_id, session_id)


@router.message(F.text == "🔒 Закрити Matic")
async def matic_close_by_button(message: Message):
    user_id = message.from_user.id
    session = await get_active_session_for_user(user_id)
    if not session:
        await message.answer("❌ Активної сесії Matic немає.")
        return
    await close_matic_session(message, user_id, session["session_id"])