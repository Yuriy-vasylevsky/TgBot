import socket
import sys

# ===============================
# Захист від подвійного запуску
# ===============================
LOCK_PORT = 9999  # будь-який вільний порт
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
import sys
from aiogram import Bot, Dispatcher, F, types, BaseMiddleware
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties
import config
from db import (
    init_db,
    save_user,
    add_promocode,
    has_claimed_gift,
    reset_all_gifts,
    has_claimed_gift,
    set_gift_claimed,
    reset_all_gifts,
    get_all_users,
    add_user_column_last_actions,
)

from stats import router as stats_router
from handlers.general import router as general_router
from handlers.admin import router as admin_router
from menu import main_menu
from aiogram import F
from random import choices
import string, asyncio
from aiogram.types import (
    BotCommand,
    BotCommandScopeDefault,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from aiogram import types, F
from aiogram import Bot, Dispatcher
from middlewares.ban_middleware import BanMiddleware
from games import (
    slot_router,
    one_of_three_router,
    rewards_router,
    blackjack_router,
    fortune_router,
)
from handlers.profile import router as profile_router

# ==========================
# Ініціалізація
# ==========================

sys.path.append(str(Path(__file__).parent))
logging.basicConfig(level=logging.INFO)

bot = Bot(token=config.TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

dp.include_router(stats_router)
dp.include_router(general_router)
dp.include_router(admin_router)
# dp.include_router(games_router)
dp.include_router(profile_router)
dp.include_router(fortune_router)

dp.include_router(slot_router)
dp.include_router(one_of_three_router)
dp.include_router(rewards_router)
dp.include_router(blackjack_router)
# dp.include_router(menu_update_router)
dp.message.middleware(BanMiddleware())
dp.callback_query.middleware(BanMiddleware())
ADMIN_ID = config.ADMIN_ID


# ==========================
# Middleware — автозбереження користувача
# ==========================

from aiogram import types
from aiogram.dispatcher.middlewares.base import BaseMiddleware
import logging
from datetime import datetime, timezone, timedelta
from db import save_user


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
# Допоміжні функції
# ==========================
def generate_promocode(length: int = 8) -> str:
    characters = string.ascii_uppercase + string.digits
    return "".join(random.choices(characters, k=length))


from aiogram import types
from aiogram.filters import Command
from aiogram.types import FSInputFile


@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    is_admin = user_id == ADMIN_ID
    gift_claimed = await has_claimed_gift(user_id)

    keyboard = main_menu(is_admin=is_admin, user_has_gift=gift_claimed)

    # 📸 Шлях до картинки (збережи її поруч із main.py або в папці images)
    photo = FSInputFile("images/4444.jpg")  # або .png, .jpeg

    # Надсилаємо фото з підписом і меню
    await message.answer_photo(
        photo=photo,
        caption=f"👋 Привіт, {message.from_user.full_name}!\n\nЛаскаво просимо до гри 🎮",
        reply_markup=keyboard,
    )


def generate_promocode(length: int = 8) -> str:
    characters = string.ascii_uppercase + string.digits
    return "".join(choices(characters, k=length))


@dp.message(F.text == "🎁 Подарунок")
async def gift_command(message: types.Message):
    user_id = message.from_user.id

    claimed = await has_claimed_gift(user_id)
    if claimed:
        await message.answer("🎁 Ви вже отримали свій подарунок!")
        return

    # Видаємо промокоди
    promo1 = generate_promocode()
    promo2 = generate_promocode()
    await add_promocode(promo1)
    await add_promocode(promo2)

    # Позначаємо, що користувач отримав подарунок
    await set_gift_claimed(user_id, True)  # <-- тут заміна

    await message.answer(
        f"🎉 Ваші подарункові промокоди:\n\n💎 `{promo1}`\n💎 `{promo2}`\n\nВикористайте їх у боті!",
        parse_mode="Markdown",
    )

    # Оновлюємо меню без кнопки подарунка
    keyboard = main_menu(is_admin=(user_id == ADMIN_ID), user_has_gift=True)
    await message.answer("Меню оновлено ⬇️", reply_markup=keyboard)


# ==========================
# Кнопка "Скинути подарунки" з підтвердженням
# ==========================
@dp.message(F.text == "🎁 Скинути подарунки")
async def confirm_reset_gifts(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ Ця команда лише для адміністратора.")
        return

    # Створюємо клавіатуру підтвердження
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Так, скинути", callback_data="confirm_reset_gifts"
                ),
                InlineKeyboardButton(
                    text="❌ Ні, скасувати", callback_data="cancel_reset_gifts"
                ),
            ]
        ]
    )

    await message.answer(
        "⚠️ Ви впевнені, що хочете скинути *всі подарунки* для користувачів?",
        reply_markup=keyboard,
        parse_mode="Markdown",
    )


# ==========================
# Обробка підтвердження
# ==========================

@dp.callback_query(F.data == "confirm_reset_gifts")
async def reset_gifts_confirmed(callback: types.CallbackQuery):
    await callback.message.edit_text("🔄 Скидаємо подарунки...")
    await reset_all_gifts()

    user_ids = await get_all_users()
    sent = 0

    for uid in user_ids:
        try:
            kb = main_menu(is_admin=(uid == ADMIN_ID), user_has_gift=False)
            await bot.send_message(
                chat_id=uid,
                text=(
                    "🎁 <b>Подарунки оновлено!</b>\n\n"
                    "Ділитись промокодами заборонено ⚠️\n"
                    "Гравцям, які ще не грали або грали давно, "
                    "бонус буде нараховано на депозит 💰\n\n"
                    "Бажаю всім удачі у грі! 🍀"
                ),
                reply_markup=kb,
                parse_mode="HTML",
            )
            sent += 1
            await asyncio.sleep(0.05)
        except Exception:
            continue

    await callback.message.edit_text(
        f"✅ Усі подарунки скинуто.\n📨 Повідомлення відправлено {sent} користувачам."
    )


# ==========================
# Обробка відміни
# ==========================
@dp.callback_query(F.data == "cancel_reset_gifts")
async def cancel_reset_gifts(callback: types.CallbackQuery):
    await callback.message.edit_text("❌ Скасовано. Подарунки залишились без змін.")


# ==========================
# Встановлення команд
# ==========================
async def set_commands():
    await bot.set_my_commands(
        [BotCommand(command="start", description="🔄 Рестарт бота")],
        scope=BotCommandScopeDefault(),
    )


# ==========================
# Запуск бота
# ==========================
async def main():
    await add_user_column_last_actions()
    await init_db(),
    await set_commands()
    # await register_game_handlers(dp, bot, main_menu, ADMIN_ID)
    logging.info("🚀 Бот запущений!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
