
import socket
import sys

# ===============================
# Захист від подвійного запуску
# ===============================
LOCK_PORT = 9999
_lock_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    _lock_socket.bind(("127.0.0.1", LOCK_PORT))
except OSError:
    print("❌ Бот уже запущений! Другий екземпляр заблоковано.")
    sys.exit(0)

import logging
import asyncio
import random
import string
from datetime import datetime, timezone, timedelta
from pathlib import Path
import os

import logging
logging.basicConfig(level=logging.INFO)
from aiogram import Bot, Dispatcher, F, types, BaseMiddleware
from aiogram import Bot, Dispatcher, F, types
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties
from aiogram.types import (
    BotCommand, BotCommandScopeDefault, BotCommandScopeAllPrivateChats,
    BotCommandScopeAllGroupChats, BotCommandScopeAllChatAdministrators,
    InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
)

import config
from db import (
    init_db, save_user, add_promocode, has_claimed_gift,
    reset_all_gifts, set_gift_claimed, get_all_users, add_user_column_last_actions
)

from middlewares.ban_middleware import BanMiddleware
from handlers.group_safe import router as safe_router
from handlers.admin_group import router as admin_group_router
from handlers.group_bowling import router as bowling_router
from handlers.group_basketball import router as basketball_router
from handlers.football_router import router as football_router
from handlers.group_antispam import router as antispam_router
from handlers.group_night_mode import router as night_mode_router

from stats import router as stats_router
from handlers.general import router as general_router
from handlers.admin import router as admin_router
from handlers.profile import router as profile_router
from games import (
    slot_router, one_of_three_router, rewards_router,
    blackjack_router, fortune_router, daily_bonus_router
)
from menu import main_menu
from handlers.group_safe import router as safe_router
# ==========================
# Ініціалізація
# ==========================
bot = Bot(
    token=config.TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

# Підключаємо роутери
dp.include_router(safe_router)
dp.include_router(admin_group_router)
dp.include_router(bowling_router)
dp.include_router(basketball_router)
dp.include_router(football_router)
dp.include_router(antispam_router)
dp.include_router(night_mode_router)

dp.include_router(stats_router)
dp.include_router(general_router)
dp.include_router(admin_router)
dp.include_router(daily_bonus_router)
dp.include_router(profile_router)
dp.include_router(fortune_router)
dp.include_router(slot_router)
dp.include_router(one_of_three_router)
dp.include_router(rewards_router)
dp.include_router(blackjack_router)

dp.message.middleware(BanMiddleware())
dp.callback_query.middleware(BanMiddleware())

ADMIN_ID = config.ADMIN_ID

# ==========================
# API для веб-апу сейфа (порт 3000 — щоб не конфліктував)
# ==========================
from aiohttp import web

async def safe_api(request):
    from handlers.group_safe import load_state
    state = await load_state()

    response = web.json_response({
        "opened": state.get("opened", []),
        "total": 250,
    })

    # CORS — дозволяємо Railway сайту робити запити
    origin = request.headers.get("Origin", "*")
    response.headers["Access-Control-Allow-Origin"] = origin
    response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "*"
    response.headers["Access-Control-Max-Age"] = "3600"

    return response


async def run_api():
    app = web.Application()
    app.router.add_get("/api/safe", safe_api)
    app.router.add_options("/api/safe", safe_api)

    port = int(os.environ.get("PORT", 3000))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"🌐 Safe API запущено на порту {port}")


# ==========================
# Middleware — автозбереження користувача
# ==========================
class SaveUserMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        if isinstance(event, types.Message) and event.from_user:
            try:
                action = event.text or "Невідома дія"
                await save_user(
                    event.from_user.id,
                    event.from_user.username or "",
                    event.from_user.full_name or "",
                    action=action,
                )
            except Exception as e:
                logging.error(f"Save user error: {e}")
        return await handler(event, data)

dp.message.middleware(SaveUserMiddleware())

# ==========================
# Генерація промокоду (одна функція!)
# ==========================
def generate_promocode(length: int = 8) -> str:
    chars = string.ascii_uppercase + string.digits
    return "".join(random.choices(chars, k=length))

# ==========================
# Команди
# ==========================
@dp.message(Command("start"), F.chat.type == "private")
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    is_admin = user_id == ADMIN_ID
    gift_claimed = await has_claimed_gift(user_id)

    keyboard = main_menu(is_admin=is_admin, user_has_gift=gift_claimed)
    photo = types.FSInputFile("images/4444.jpg")

    await message.answer_photo(
        photo=photo,
        caption=f"👋 Привіт, {message.from_user.full_name}!\n\nЛаскаво просимо до гри 🎮",
        reply_markup=keyboard,
    )

@dp.message(F.text == "🎁 Подарунок")
async def gift_command(message: types.Message):
    user_id = message.from_user.id
    claimed = await has_claimed_gift(user_id)
    if claimed:
        await message.answer("🎁 Ви вже отримали свій подарунок!")
        return

    promo = generate_promocode()
    await add_promocode(promo)
    await set_gift_claimed(user_id, True)

    await message.answer(
        f"🎉 Ваш подарунковий промокод:\n\n💎 `{promo}`\n\nВикористайте його в боті!",
        parse_mode="Markdown"
    )

    keyboard = main_menu(is_admin=(user_id == ADMIN_ID), user_has_gift=True)
    await message.answer("Меню оновлено ⬇️", reply_markup=keyboard)

# ==========================
# Скинути подарунки (адмін)
# ==========================
@dp.message(F.text == "🎁 Скинути подарунки")
async def confirm_reset_gifts(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ Тільки для адміністратора.")
        return
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Так, скинути", callback_data="confirm_reset_gifts"),
        InlineKeyboardButton(text="❌ Ні", callback_data="cancel_reset_gifts")
    ]])
    await message.answer("⚠️ Скинути ВСІ подарунки?", reply_markup=keyboard, parse_mode="Markdown")

@dp.callback_query(F.data == "confirm_reset_gifts")
async def reset_gifts_confirmed(callback: types.CallbackQuery):
    await callback.message.edit_text("🔄 Скидаємо...")
    await reset_all_gifts()
    # ... (твій код розсилки лишається без змін)
    await callback.message.edit_text("✅ Усі подарунки скинуто.")

@dp.callback_query(F.data == "cancel_reset_gifts")
async def cancel_reset_gifts(callback: types.CallbackQuery):
    await callback.message.edit_text("❌ Скасовано.")

# ==========================
# Команди для адміна
# ==========================
async def set_commands():
    await bot.set_my_commands(
        [BotCommand(command="start", description="🔄 Рестарт")],
        scope=BotCommandScopeAllPrivateChats()
    )
    await bot.delete_my_commands(scope=BotCommandScopeAllGroupChats())
    await bot.set_my_commands(commands=[], scope=BotCommandScopeAllGroupChats())

    admin_commands = [
        BotCommand(command="safe", description="🔒 Показати Сейф"),
        BotCommand(command="open", description="🔓 Відкрити клітинку /open 123"),
        BotCommand(command="bowling", description="🎳 Боулінг"),
        BotCommand(command="basketball", description="🏀 Баскетбол"),
        BotCommand(command="football", description="⚽ Футбол"),
    ]
    await bot.set_my_commands(
        commands=admin_commands,
        scope=BotCommandScopeAllChatAdministrators()
    )

# ==========================
# ЗАПУСК
# ==========================
async def main():
    await init_db()
    await add_user_column_last_actions()
    await set_commands()

    logging.info("🚀 Бот запущений!")

    asyncio.create_task(run_api())      # ← API стартує тут
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())