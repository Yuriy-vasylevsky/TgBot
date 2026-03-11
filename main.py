import socket
import sys
import logging
import asyncio
import random
import string
import os
import time
from datetime import datetime, timedelta

import monobank
from aiohttp import web

from aiogram import Bot, Dispatcher, F, types
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties
from aiogram.types import (
    BotCommand,
    BotCommandScopeAllPrivateChats,
    BotCommandScopeAllGroupChats,
    BotCommandScopeAllChatAdministrators,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

import handlers.config as config
from db import (
    init_db,
    add_promocode,
    has_claimed_gift,
    reset_all_gifts,
    set_gift_claimed,
    mark_tx_used,
    is_tx_used,
    get_pending_payments,
    add_to_balance,
    remove_pending_payment,
    get_balance,
    DB_PATH,
)

from middlewares.middleware import BanMiddleware, SaveUserMiddleware

# ==================== РОУТЕРИ ====================
from group_games.group_safe import router as safe_router
from handlers.admin_group import router as admin_group_router
from group_games.group_bowling import router as bowling_router
from group_games.group_basketball import router as basketball_router
from group_games.football_router import router as football_router
from group_games.group_antispam import router as antispam_router
from group_games.group_night_mode import router as night_mode_router
from group_games.group_numbers import router as numbers_router
from group_games.group_jackpot import router as jackpot_router
from handlers.wallet import router as wallet_router
from group_games.group_wordle import router as wordle_router
from group_games.group_skarb import router as skarb_router
from group_games.group_vote_prize import router as vote_router
from group_games.group_minefield import router as minefield_router



from handlers.stats import router as stats_router
from handlers.general import router as general_router
from handlers.admin.router import router as admin_router
from handlers.profile import router as profile_router

from games import (
    slot_router,
    one_of_three_router,
    rewards_router,
    blackjack_router,
    fortune_router,
)

from handlers.menu import main_menu

# ===============================
# ЗАХИСТ ВІД ПОДВІЙНОГО ЗАПУСКУ
# ===============================
LOCK_PORT = 9999
_lock_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    _lock_socket.bind(("127.0.0.1", LOCK_PORT))
except OSError:
    print("❌ Бот уже запущений! Другий екземпляр заблоковано.")
    sys.exit(0)

# ==========================
# НАЛАШТУВАННЯ ЛОГІВ ТА БАЗИ
# ==========================
logging.basicConfig(level=logging.INFO)
print(f"📁 DB_PATH = {DB_PATH}")

# ==========================
# ІНІЦІАЛІЗАЦІЯ БОТА
# ==========================
bot = Bot(
    token=config.TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

# Підключаємо роутери (тільки один раз!)
dp.include_router(minefield_router)
dp.include_router(vote_router)
dp.include_router(skarb_router)
dp.include_router(jackpot_router)
dp.include_router(wordle_router)
dp.include_router(numbers_router)
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
dp.include_router(profile_router)
dp.include_router(fortune_router)
dp.include_router(slot_router)
dp.include_router(one_of_three_router)
dp.include_router(rewards_router)
dp.include_router(blackjack_router)
dp.include_router(wallet_router)

# Мідлвари (застосовуємо один раз)
dp.message.middleware(BanMiddleware())
dp.callback_query.middleware(BanMiddleware())
dp.message.middleware(SaveUserMiddleware())

ADMIN_ID = config.ADMIN_ID

# ==========================
# API ДЛЯ ВЕБ-АПУ СЕЙФА (порт 3000)
# ==========================
async def safe_api(request):
    from group_games.group_safe import load_state   # ← тут твій оновлений load_state
    
    state = await load_state()

    response = web.json_response({
        "opened": state.get("opened", []),
        "total": 250,
        "win_cell": state.get("win_cell", 198),      # ← додано (корисно)
        "users": state.get("users", {})              # ← САМЕ ГОЛОВНЕ для лідерборду!
    })

    # CORS (залишаємо як було)
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
    logging.info(f"🌐 Safe API запущено на порту {port}")


    
# ==========================
# ФОНОВА ПЕРЕВІРКА ПЛАТЕЖІВ MONOBANK
# ==========================
# async def background_payment_checker():
#     """Фонова перевірка платежів Monobank кожні 90 секунд"""
#     while True:
#         await asyncio.sleep(90)

#         try:
#             pendings = await get_pending_payments()
#             if not pendings:
#                 continue

#             logging.info(f"🔄 Фонова перевірка: знайдено {len(pendings)} платежів")

#             client = monobank.Client(token=config.MONO_TOKEN)
#             from_date = datetime.now() - timedelta(days=7)
#             to_date = datetime.now()

#             statements = client.get_statements(config.MONO_ACCOUNT, from_date, to_date)
#             logging.info(f"📥 Отримано {len(statements)} транзакцій")

#             for p in pendings:
#                 target_amount = p["amount_kop"]
#                 user_id = p["user_id"]
#                 payment_id = p["comment"]

#                 try:
#                     payment_timestamp = int(payment_id.split(":")[1])
#                 except Exception:
#                     payment_timestamp = int(time.time())

#                 time_window = 600
#                 best_match = None
#                 best_match_diff = float("inf")
#                 best_match_tx_id = None

#                 for tx in statements:
#                     tx_amount = tx.get("amount", 0)
#                     tx_time = tx.get("time", 0)
#                     tx_id = tx.get("id", "")
#                     time_diff = abs(tx_time - payment_timestamp)

#                     if await is_tx_used(tx_id):
#                         logging.debug(f"  ⏭️ TX вже використана: {tx_id}")
#                         continue

#                     if (tx_amount == target_amount and
#                         time_diff <= time_window and
#                         tx_amount > 0):

#                         if time_diff < best_match_diff:
#                             best_match = tx
#                             best_match_diff = time_diff
#                             best_match_tx_id = tx_id

#                 if best_match:
#                     await mark_tx_used(best_match_tx_id, user_id, target_amount, payment_id)

#                     amount_grn = target_amount // 100
#                     await add_to_balance(user_id, amount_grn)
#                     await remove_pending_payment(user_id)

#                     status = " (холд)" if best_match.get("hold", False) else ""
#                     try:
#                         await bot.send_message(
#                             user_id,
#                             f"✅ Автоматично зараховано {amount_grn} грн{status}!\n"
#                             f"Новий баланс: {await get_balance(user_id)} грн"
#                         )
#                     except Exception as send_err:
#                         logging.warning(f"Не вдалося надіслати повідомлення {user_id}: {send_err}")

#                     logging.info(
#                         f"✅ ЗАРАХУВАННЯ: user_id={user_id}, {amount_grn} грн, "
#                         f"tx_id='{best_match_tx_id}'"
#                     )
#                 else:
#                     logging.debug(f"⏳ Платіж очікується: user_id={user_id}, {target_amount//100} грн")

#         except Exception as e:
#             logging.error(f"❌ Background checker error: {e}", exc_info=True)
#             await asyncio.sleep(30)


# ==========================
# ГЕНЕРАЦІЯ ПРОМОКОДУ
# ==========================
def generate_promocode(length: int = 8) -> str:
    chars = string.ascii_uppercase + string.digits
    return "".join(random.choices(chars, k=length))


# ==========================
# КОМАНДИ
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
    if await has_claimed_gift(user_id):
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
# СКИДАННЯ ПОДАРУНКІВ (АДМІН)
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
    await message.answer("⚠️ Скинути ВСІ подарунки?", reply_markup=keyboard)


@dp.callback_query(F.data == "confirm_reset_gifts")
async def reset_gifts_confirmed(callback: types.CallbackQuery):
    await callback.message.edit_text("🔄 Скидаємо...")
    await reset_all_gifts()
    await callback.message.edit_text("✅ Усі подарунки скинуто.")


@dp.callback_query(F.data == "cancel_reset_gifts")
async def cancel_reset_gifts(callback: types.CallbackQuery):
    await callback.message.edit_text("❌ Скасовано.")


# ==========================
# КОМАНДИ ТА МЕНЮ
# ==========================
async def set_commands():
    await bot.set_my_commands(
        [BotCommand(command="start", description="🔄 Рестарт")],
        scope=BotCommandScopeAllPrivateChats()
    )
    await bot.delete_my_commands(scope=BotCommandScopeAllGroupChats())

    admin_commands = [
        BotCommand(command="safe", description="🔒 Показати Сейф"),
        BotCommand(command="open", description="🔓 Відкрити клітинку"),
        BotCommand(command="bowling", description="🎳 Боулінг"),
        BotCommand(command="basketball", description="🏀 Баскетбол"),
        BotCommand(command="football", description="⚽ Футбол"),
        BotCommand(command="wordle", description="🎭 Вгадай слово"),
        BotCommand(command="numbers", description="🕵️‍♂️ Вгадай код"),
        BotCommand(command="jackpot2", description="💵💵 Jackpot"),
        BotCommand(command="jackpot", description="💵💵💵 Jackpot"),
        BotCommand(command="jackpot5", description="💵💵💵💵💵 Jackpot"),
        BotCommand(command="skarb", description="💎 Найди скарб"),
        BotCommand(command="/vote_prize", description="Голосування"),
        BotCommand(command="/minefield", description="Промо борьба"),
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
    await set_commands()

    # asyncio.create_task(background_payment_checker())
    asyncio.create_task(run_api())

    logging.info("🚀 Бот успішно запущений!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())