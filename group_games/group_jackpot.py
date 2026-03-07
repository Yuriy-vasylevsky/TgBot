from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
import asyncio
import logging
import random
import time

from handlers.config import ADMIN_ID

router = Router(name="group_jackpot")
router.message.filter(F.chat.type.in_({"group", "supergroup"}))

# ==========================
# НАЛАШТУВАННЯ ГРИ
# ==========================
REQUIRED_PRESSES = 3      # для звичайного /jackpot
MIN_MAX_AMOUNT = 100
MAX_MAX_AMOUNT = 100
COOLDOWN_HOURS = 12
# ==========================

active_jackpots = {}
winners_cooldown = {}


def is_on_cooldown(user_id: int) -> tuple[bool, int]:
    if user_id in winners_cooldown:
        remaining = winners_cooldown[user_id] - time.time()
        if remaining > 0:
            return True, int(remaining)
        del winners_cooldown[user_id]
    return False, 0


def format_cooldown(remaining_seconds: int) -> str:
    hours = remaining_seconds // 3600
    minutes = (remaining_seconds % 3600) // 60
    if hours > 0:
        return f"{hours}г {minutes}хв"
    return f"{minutes}хв"


def get_display_name(user) -> str:
    return f"@{user.username}" if user.username else user.full_name


def get_starters_text(starters: list) -> str:
    if not starters:
        return "👥 Учасники:"
    lines = ["👥 Учасники:"]
    for name in starters:
        lines.append(f"• {name}")
    return "\n".join(lines)


# ==========================
# УНІВЕРСАЛЬНА ФУНКЦІЯ ЗАПУСКУ
# ==========================
async def create_jackpot(message: Message, required_presses: int, max_amount: int, title: str = "JACKPOT"):
    chat_id = message.chat.id
    if chat_id in active_jackpots:
        await message.answer("❌ В цьому чаті вже запущена гра Jackpot!")
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🚀 ПУСК (0/{required_presses})", callback_data="jackpot_press")]
    ])

    msg = await message.answer(
        f"<b>💸💸💸 Лови {title} 💸💸💸</b>\n\n"
        f"💰 Максимальний можливий виграш: до <b>{max_amount} грн 🤑</b>\n\n"
        f"Участь беруть <b>{required_presses} перших гравців</b>, що натиснуть ПУСК!\n"
        f"💸 Приз росте кожну секунду",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

    active_jackpots[chat_id] = {
        "message": msg,
        "max_amount": max_amount,
        "starters": [],
        "starter_ids": set(),
        "amount": 1,
        "task": None,
        "active": False,
        "required_presses": required_presses   # зберігаємо для цієї гри
    }


# ==========================
# КОМАНДИ ЗАПУСКУ
# ==========================
@router.message(Command("jackpot"))
async def start_jackpot(message: Message):
    if message.from_user.id != ADMIN_ID:
        try: await message.delete()
        except: pass
        return
    await create_jackpot(message, REQUIRED_PRESSES, random.randint(MIN_MAX_AMOUNT, MAX_MAX_AMOUNT))


@router.message(Command("jackpot2"))
async def start_jackpot2(message: Message):
    if message.from_user.id != ADMIN_ID:
        try: await message.delete()
        except: pass
        return
    await create_jackpot(message, 2, 60, title="JACKPOT 2")

@router.message(Command("jackpot5"))
async def start_jackpot2(message: Message):
    if message.from_user.id != ADMIN_ID:
        try: await message.delete()
        except: pass
        return
    await create_jackpot(message, 5, 300, title="JACKPOT 5")

# ==========================
# НАТИСКАННЯ ПУСК
# ==========================
@router.callback_query(F.data == "jackpot_press")
async def jackpot_press(callback: CallbackQuery):
    chat_id = callback.message.chat.id
    user = callback.from_user
    user_id = user.id

    on_cooldown, remaining = is_on_cooldown(user_id)
    if on_cooldown:
        await callback.answer(
            f"⏳ Ти вже вигравав!\nМожеш натиснути ПУСК знову через {format_cooldown(remaining)}",
            show_alert=True
        )
        return

    if chat_id not in active_jackpots or active_jackpots[chat_id]["active"]:
        await callback.answer("Гра вже запущена!", show_alert=True)
        return

    game = active_jackpots[chat_id]

    if user_id in game["starter_ids"]:
        await callback.answer("Ти вже натиснув ПУСК!", show_alert=True)
        return

    display_name = get_display_name(user)
    game["starters"].append(display_name)
    game["starter_ids"].add(user_id)

    pressed = len(game["starters"])
    required = game["required_presses"]

    if pressed < required:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"🚀 ПУСК ({pressed}/{required})", callback_data="jackpot_press")]
        ])

        await callback.message.edit_text(
            f"🎰 <b>Лови JACKPOT!</b>\n\n"
            f"Максимальний можливий виграш: до <b>{game['max_amount']} грн</b>\n\n"
            f"{get_starters_text(game['starters'])}\n\n"
            f"<b>{pressed}/{required}</b>",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        return

    # === ЗАПУСК ГРИ ===
    game["active"] = True

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 ЗАБРАТИ 1 ГРН", callback_data="jackpot_take")]
    ])

    await callback.message.edit_text(
        f"🎰 <b>Лови JACKPOT!</b>\n\n"
        f"Максимальний можливий виграш: до <b>{game['max_amount']} грн</b>\n\n"
        f"{get_starters_text(game['starters'])}\n\n"
        f"🔥 <b>ЛІЧИЛЬНИК ПРАЦЮЄ!</b>\n"
        f"Натискай кнопку, щоб забрати поточний виграш!",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

    game["task"] = asyncio.create_task(jackpot_counter(chat_id))


# ==========================
# ЛІЧИЛЬНИК (без змін)
# ==========================
async def jackpot_counter(chat_id: int):
    if chat_id not in active_jackpots:
        return

    game = active_jackpots[chat_id]
    msg = game["message"]
    max_amount = game["max_amount"]

    try:
        amount = 5
        game["amount"] = amount

        while amount <= max_amount:
            if chat_id not in active_jackpots or not game.get("active"):
                return

            delay = 1 if amount <= 15 else 3
            await asyncio.sleep(delay)

            amount += 5
            if amount > max_amount:
                break

            game["amount"] = amount

            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=f"💰 ЗАБРАТИ {amount} ГРН", callback_data="jackpot_take")]
            ])

            try:
                await msg.edit_reply_markup(reply_markup=keyboard)
            except Exception as e:
                if "not modified" not in str(e).lower():
                    logging.warning(f"Jackpot edit warning: {e}")

        if chat_id in active_jackpots and game.get("active"):
            await msg.edit_text(
                "⏰ Час вийшов!\n\n"
                f"Максимум {max_amount} грн ніхто не забрав 😔",
                reply_markup=None
            )
            del active_jackpots[chat_id]

    except asyncio.CancelledError:
        logging.info(f"✅ Jackpot лічильник скасовано в чаті {chat_id}")
        raise
    except Exception as e:
        logging.error(f"❌ Помилка в jackpot_counter {chat_id}: {e}")
        active_jackpots.pop(chat_id, None)


# ==========================
# ЗАБРАТИ ВИГРАШ (без змін)
# ==========================
@router.callback_query(F.data == "jackpot_take")
async def jackpot_take(callback: CallbackQuery):
    chat_id = callback.message.chat.id
    user = callback.from_user
    user_id = user.id

    if chat_id not in active_jackpots:
        await callback.answer("Гра вже закінчена!", show_alert=True)
        return

    game = active_jackpots[chat_id]

    if user_id not in game.get("starter_ids", set()):
        await callback.answer(
            "❌ Ти не натискав ПУСК на початку гри!\n"
            "Тільки учасники запуску можуть забирати приз.",
            show_alert=True
        )
        return

    amount = game.get("amount", 1)

    if game.get("task"):
        task = game["task"]
        if not task.done():
            task.cancel()
            try: await task
            except asyncio.CancelledError: pass

    game["active"] = False
    winners_cooldown[user_id] = time.time() + COOLDOWN_HOURS * 3600

    await callback.message.edit_text(
        f"🎉 <b>ПЕРЕМОЖЕЦЬ!</b> 🏆\n\n"
        f"{user.mention_html()} забрав <b>{amount} грн</b>!\n\n"
        f"🔒 Наступний ПУСК для тебе буде доступний через {COOLDOWN_HOURS} годин.",
        parse_mode="HTML",
        reply_markup=None
    )

    logging.info(f"💰 JACKPOT {amount} грн забрав {user.id} в чаті {chat_id}")
    active_jackpots.pop(chat_id, None)