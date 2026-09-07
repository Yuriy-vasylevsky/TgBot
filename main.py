import socket
import sys
import logging
import asyncio
import random
import string
import os
import time
from datetime import datetime, timedelta

from html import escape
from secrets import choice
from db.promo import claim_gift
from services.health import health
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
    is_referred,       
    add_referral, 
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
from group_games.bank import router as bank_router
from group_games.group_maize import router as maize_router


from handlers.stats import router as stats_router
from handlers.general import router as general_router
from admin.router import router as admin_router
from handlers.profile import router as profile_router
from handlers.referral import router as referral_router
from handlers.piggy_bank import router as piggy_bank_router
# from handlers.ma import router as matic_gis_router
from handlers.admin_winlog import router as winlog_router

from games import (
    slot_router,
    one_of_three_router,
    rewards_router,
    blackjack_router,
    fortune_router,
    simple_win_router
)

from handlers.menu import main_menu


logger = logging.getLogger(__name__)



# ===============================
# ЗАХИСТ ВІД ПОДВІЙНОГО ЗАПУСКУ
# ===============================
def acquire_instance_lock():
    lock_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        lock_socket.bind(("127.0.0.1", int(os.getenv("LOCK_PORT", "9999"))))
    except OSError:
        lock_socket.close()
        raise RuntimeError("Another bot instance is running or LOCK_PORT is unavailable")
    return lock_socket

# ==========================
# НАЛАШТУВАННЯ ЛОГІВ ТА БАЗИ
# ==========================
logging.basicConfig(level=logging.INFO)

# ==========================
# ІНІЦІАЛІЗАЦІЯ БОТА
# ==========================
bot = Bot(
    token=config.TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

# Підключаємо роутери (тільки один раз!)
dp.include_router(maize_router)
dp.include_router(bank_router)
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
dp.include_router(piggy_bank_router)
dp.include_router(profile_router)
dp.include_router(fortune_router)
dp.include_router(slot_router)
dp.include_router(one_of_three_router)
dp.include_router(rewards_router)
dp.include_router(blackjack_router)
dp.include_router(wallet_router)
dp.include_router(simple_win_router)
dp.include_router(referral_router)
# dp.include_router(matic_gis_router)
dp.include_router(winlog_router)


# Мідлвари (застосовуємо один раз)
dp.message.middleware(BanMiddleware())
dp.callback_query.middleware(BanMiddleware())
dp.message.middleware(SaveUserMiddleware())
dp.callback_query.middleware(SaveUserMiddleware())

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
        "users": state.get("users", {})              # ← САМЕ ГОЛОВНЕ для лідерборду!
    })

    # CORS (залишаємо як було)
    origin = request.headers.get("Origin")
    if origin in config.SAFE_API_ORIGINS:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Vary"] = "Origin"
    response.headers["Cache-Control"] = "no-store"
    response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "*"
    response.headers["Access-Control-Max-Age"] = "3600"

    return response


async def run_api():
    app = web.Application()
    app.router.add_get("/healthz", health)
    app.router.add_get("/api/safe", safe_api)
    app.router.add_options("/api/safe", safe_api)

    port = int(os.environ.get("PORT", 3000))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    try:
        await site.start()
    except BaseException:
        await runner.cleanup()
        raise
    logger.info(f"🌐 Safe API запущено на порту {port}")
    return runner


# ==========================
# ЗАПУСК
# ==========================



# ==========================
# ГЕНЕРАЦІЯ ПРОМОКОДУ
# ==========================
def generate_promocode(length: int = 8) -> str:
    chars = string.ascii_uppercase + string.digits
    return "".join((choice(chars) for _ in range(length)))


# ==========================
# КОМАНДИ
# ==========================

from db import is_referred, add_referral, user_exists

@dp.message(Command("start"), F.chat.type == "private")
async def cmd_start(message: types.Message, is_new_user: bool = True):
    user_id = message.from_user.id
    args = message.text.split()

    if len(args) > 1 and args[1].startswith("ref_"):
        try:
            referrer_id = int(args[1].replace("ref_", ""))

            if referrer_id != user_id and not await is_referred(user_id):
                was_existing = not is_new_user  # ← використовуємо з middleware

                await add_referral(referrer_id, user_id, was_existing_user=was_existing)

                if was_existing:
                    await message.answer(
                        "ℹ️ Ви вже зареєстровані в боті"
                    )
                else:
                    await message.answer(
                        "👋  "
                    )
        except ValueError:
            pass

    is_admin = user_id == ADMIN_ID
    gift_claimed = await has_claimed_gift(user_id)
    keyboard = main_menu(is_admin=is_admin, user_has_gift=gift_claimed)

    caption = (
        f"👋 Привіт, {escape(message.from_user.full_name)}!\n\n"
        "Ласкаво просимо до гри 🎮"
    )
    if is_new_user:
        caption += (
            "\n\n🎊 <b>ВІТАЛЬНИЙ БОНУС</b> 🎊\n"
            "Під час першого поповнення ти отримаєш\n"
            "💸 <b>+50 ГРН ДО ДЕПОЗИТУ</b> 💸\n\n"
            "Поповнюй баланс, обирай гру та випробовуй удачу! 🍀🔥"
        )

    photo = types.FSInputFile("images/4444.jpg")
    await message.answer_photo(
        photo=photo,
        caption=caption,
        reply_markup=keyboard,
    )
@dp.message(F.text == "🎁 Подарунок")
async def gift_command(message: types.Message):
    user_id = message.from_user.id
    if await has_claimed_gift(user_id):
        await message.answer("🎁 Ви вже отримали свій подарунок!")
        return

    promo = generate_promocode()
    if not await claim_gift(user_id, promo):
        await message.answer("?? ?? ??? ???????? ?????????.")
        return

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
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Тільки адміністратор.", show_alert=True)
        return
    await callback.answer()
    await callback.message.answer("🔄 Скидаємо...")
    await reset_all_gifts()
    await callback.message.answer("✅ Усі подарунки скинуто.")


@dp.callback_query(F.data == "cancel_reset_gifts")
async def cancel_reset_gifts(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Тільки адміністратор.", show_alert=True)
        return
    await callback.answer()
    await callback.message.answer("❌ Скасовано.")



async def set_commands():
    await bot.set_my_commands(
        [BotCommand(command="start", description="🔄 Рестарт")],
        scope=BotCommandScopeAllPrivateChats()
    )

    # Команди для ВСІХ учасників груп (не тільки адмінів)
    group_commands = [
        BotCommand(command="safe", description="🔒 Показати Сейф"),
    ]
    await bot.set_my_commands(
        commands=group_commands,
        scope=BotCommandScopeAllGroupChats()
    )

    admin_commands = [
        BotCommand(command="safe", description="🔒 Показати Сейф"),  # дублюємо, щоб адміни теж бачили
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
        BotCommand(command="maize", description="🌽 Maize"),
        BotCommand(command="vote_prize", description="Голосування"),
        BotCommand(command="minefield", description="Промо борьба"),
        BotCommand(command="bank", description="Банк "),
    ]
    await bot.set_my_commands(
        commands=admin_commands,
        scope=BotCommandScopeAllChatAdministrators()
    )

    
import asyncio
from db import (
    cleanup_old_payment_logs,
    cleanup_expired_freezes,
    expire_stale_manual_payments,
)
from handlers.casino_api import close_matic_api

MANUAL_PAYMENT_EXPIRY_HOURS = 24


async def _notify_expired_manual_payments(payments: list[dict]) -> None:
    for payment in payments:
        display_number = payment.get("daily_number") or payment["id"]
        try:
            await bot.send_message(
                payment["user_id"],
                f"⌛ <b>Заявку на поповнення №{display_number} автоматично "
                f"відхилено.</b>\n\n"
                f"💰 Сума: <b>{payment['amount']} грн</b>\n"
                f"Причина: адміністратор не підтвердив платіж протягом "
                f"{MANUAL_PAYMENT_EXPIRY_HOURS} годин.\n\n"
                "Тепер ви можете створити нову заявку на поповнення.",
                reply_markup=main_menu(),
            )
        except Exception:
            logger.exception(
                "Не вдалося повідомити користувача про прострочену заявку | "
                "payment_id=%s user_id=%s",
                payment["id"],
                payment["user_id"],
            )


async def run_cleanup_loop():
    while True:
        try:
            expired_payments = await expire_stale_manual_payments(
                MANUAL_PAYMENT_EXPIRY_HOURS
            )
            if expired_payments:
                logger.info(
                    "Автоматично відхилено прострочених ручних платежів: %s",
                    len(expired_payments),
                )
                await _notify_expired_manual_payments(expired_payments)
        except Exception:
            logger.exception("Помилка автоматичного відхилення старих платежів")
        try:
            await cleanup_old_payment_logs()
            await cleanup_expired_freezes()
        except Exception:
            logger.exception("Помилка фонового очищення інших даних")
        await asyncio.sleep(60 * 60)
# ==========================
# ЗАПУСК
# ==========================
async def main():
    config.validate_config()
    instance_lock = acquire_instance_lock()
    api_runner = None
    cleanup_task = None
    try:
        await init_db()
        await set_commands()
        api_runner = await run_api()
        cleanup_task = asyncio.create_task(run_cleanup_loop(), name="database-cleanup")
        logger.info("Bot started")
        await dp.start_polling(bot)
    finally:
        if cleanup_task:
            cleanup_task.cancel()
            await asyncio.gather(cleanup_task, return_exceptions=True)
        resources = [close_matic_api(), bot.session.close(), dp.storage.close()]
        if api_runner:
            resources.append(api_runner.cleanup())
        for result in await asyncio.gather(*resources, return_exceptions=True):
            if isinstance(result, BaseException):
                logger.error("Shutdown cleanup failed: %s", type(result).__name__)
        instance_lock.close()
        logger.info("Bot stopped")


if __name__ == "__main__":
    asyncio.run(main())
