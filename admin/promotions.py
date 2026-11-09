import asyncio
import logging

import aiosqlite
from aiogram import F, Router, types
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest, TelegramRetryAfter

from db.core import DB_PATH
from handlers.config import ADMIN_ID
from handlers.menu import main_menu
from services.promotions import promotions_enabled, set_promotions, piggy_bank_enabled, set_piggy_bank

router = Router(name="admin_promotions")
_update_task = None
_toggle_lock = asyncio.Lock()
logger = logging.getLogger(__name__)


def promotions_keyboard():
    enabled = promotions_enabled()
    return types.InlineKeyboardMarkup(inline_keyboard=[[
        types.InlineKeyboardButton(
            text=f"🎟 Промокоди та колесо: {'✅ Увімкнено' if enabled else '⛔ Вимкнено'}",
            callback_data=f"promotions:set:{int(not enabled)}",
        )
    ], [
        types.InlineKeyboardButton(
            text=f"🐷 Скарбничка: {'✅ Увімкнено' if piggy_bank_enabled() else '⛔ Вимкнено'}",
            callback_data=f"promotions:piggy:{int(not piggy_bank_enabled())}",
        )
    ]])


@router.message(F.text == "📣 Керування акціями")
async def open_promotions(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer("📣 Керування акціями", reply_markup=promotions_keyboard())


async def refresh_menus(bot, feature="Промокоди та колесо фортуни", enabled=None):
    success = failed = 0
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT user_id FROM users") as cur:
                users = await cur.fetchall()
        text = f"🔄 Меню оновлено. {feature}: " + (
            "увімкнено." if (promotions_enabled() if enabled is None else enabled) else "вимкнено."
        )
        for (user_id,) in users:
            while True:
                try:
                    await bot.send_message(user_id, text, reply_markup=main_menu(is_admin=user_id == ADMIN_ID))
                    success += 1
                    break
                except TelegramRetryAfter as exc:
                    await asyncio.sleep(exc.retry_after)
                except (TelegramForbiddenError, TelegramBadRequest):
                    failed += 1
                    break
                except Exception:
                    logger.exception("Menu refresh failed for %s", user_id)
                    failed += 1
                    break
            await asyncio.sleep(0.05)
        await bot.send_message(ADMIN_ID, f"✅ Оновлення меню завершено: {success}. Не доставлено: {failed}.")
    except Exception:
        logger.exception("Automatic menu refresh failed")


@router.callback_query(F.data.in_({
    "promotions:set:0", "promotions:set:1", "promotions:piggy:0", "promotions:piggy:1",
}))
async def toggle_promotions(callback: types.CallbackQuery):
    global _update_task
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Тільки адміністратор.", show_alert=True)
        return
    async with _toggle_lock:
        if _update_task and not _update_task.done():
            await callback.answer("⏳ Триває оновлення меню. Зачекайте завершення.", show_alert=True)
            return
        enabled = callback.data.endswith(":1")
        is_piggy = callback.data.startswith("promotions:piggy:")
        if enabled == (piggy_bank_enabled() if is_piggy else promotions_enabled()):
            await callback.answer("Цей стан уже встановлено. Відкрийте меню керування ще раз.")
            return
        await (set_piggy_bank(enabled) if is_piggy else set_promotions(enabled))
        await callback.answer("Стан збережено. Оновлюю меню користувачів.")
        feature = "Скарбничка" if is_piggy else "Промокоди та колесо фортуни"
        _update_task = asyncio.create_task(refresh_menus(callback.bot, feature, enabled))
        await callback.message.edit_reply_markup(reply_markup=promotions_keyboard())
