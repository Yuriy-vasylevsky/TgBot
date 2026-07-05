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


from handlers.stats import router as stats_router
from handlers.general import router as general_router
from admin.router import router as admin_router
from handlers.profile import router as profile_router
from handlers.referral import router as referral_router
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
    logger.info(f"🌐 Safe API запущено на порту {port}")
    return runner


# ==========================
# ЗАПУСК
# ==========================
async def main():
    await init_db()
    await set_commands()

    # Фонові завдання
    asyncio.create_task(run_cleanup_loop())
    
    # Запускаємо Web API
    api_runner = None
    try:
        api_runner = await run_api()
    except Exception as e:
        logger.error(f"Не вдалося запустити Safe API: {e}")

        logger.info("🚀 Бот успішно запущений!")

    try:
        await dp.start_polling(bot)
    except asyncio.CancelledError:
        pass
    except KeyboardInterrupt:
        pass
    finally:
        print("🛑 Завершуємо роботу бота...")
        
        # Закриваємо Matic API
        try:
            await matic_api.close()
        except:
            pass
        
        # Закриваємо бот
        try:
            await bot.session.close()
        except:
            pass
        
        # Закриваємо Web API
        if api_runner:
            try:
                await api_runner.cleanup()
            except:
                pass
        
        print("✅ Бот коректно завершено.")


# ==========================
# ГЕНЕРАЦІЯ ПРОМОКОДУ
# ==========================
def generate_promocode(length: int = 8) -> str:
    chars = string.ascii_uppercase + string.digits
    return "".join(random.choices(chars, k=length))


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
    await callback.message.answer("🔄 Скидаємо...")
    await reset_all_gifts()
    await callback.message.answer("✅ Усі подарунки скинуто.")


@dp.callback_query(F.data == "cancel_reset_gifts")
async def cancel_reset_gifts(callback: types.CallbackQuery):
    await callback.message.answer("❌ Скасовано.")


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
        BotCommand(command="/bank", description="Банк "),
    ]
    await bot.set_my_commands(
        commands=admin_commands,
        scope=BotCommandScopeAllChatAdministrators()
    )


import asyncio
from db import cleanup_old_payment_logs
from handlers.casino_api import _matic_api as matic_api

async def run_cleanup_loop():
    while True:
        await cleanup_old_payment_logs()
        await asyncio.sleep(60 * 60)
# ==========================
# ЗАПУСК
# ==========================
async def main():
    await init_db()
    await set_commands()

    asyncio.create_task(run_cleanup_loop())
    api_runner = await run_api()

    print("🚀 Бот успішно запущений!")

    try:
        await dp.start_polling(bot)
    except asyncio.CancelledError:
        pass
    except KeyboardInterrupt:
        pass
    finally:
        print("🛑 Завершуємо роботу бота...")
        try:
            await matic_api.close()
        except:
            pass
        await bot.session.close()
        if 'api_runner' in locals():
            await api_runner.cleanup()
        print("✅ Бот коректно завершено.")


if __name__ == "__main__":
    asyncio.run(main())



#                          ssh root@77.42.71.244  
#                           mPLmmcFnpcmK

#    Подивитись логи:     journalctl -u tgbot -f
#    Оновити код після змін у GitHub:    cd /root/tgbot/tgbot && git pull && systemctl restart tgbot


#              systemctl restart tgbot    
#              systemctl stop tgbot       
#              systemctl start tgbot      
#              systemctl status tgbot    

# 77.42.71.244	

# lTWMUl0FnG9yLS34bCLevmmK3W95ULmPupySbFDI28lWvb8S5GqJPIhWdX4hR2r7

# cd /root/safe-250-web

# systemctl start safe-250-web