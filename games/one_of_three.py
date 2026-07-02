import asyncio
import random
from aiogram import F, types, Router
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

from db import add_game_result, get_winrate, has_claimed_gift, add_game_win
from db.wallet import get_daily_net, get_yesterday_net, add_to_balance, add_daily_game_win
from db import can_receive_prize
from handlers.menu import main_menu
from handlers.config import ADMIN_ID

router = Router(name="one_of_three")

# Захист від абузу
_played_users: set[int] = set()


def choose_box_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="📦 1", callback_data="box:1"),
        InlineKeyboardButton(text="📦 2", callback_data="box:2"),
        InlineKeyboardButton(text="📦 3", callback_data="box:3"),
    ]])


@router.message(F.text == "🎯 Один з трьох")
async def start_one_of_three(message: types.Message):
    user_id = message.from_user.id
    _played_users.discard(user_id)

    await message.answer(
        "<b>🎯 Один із трьох!</b>\n\n"
        "Перед тобою три закриті коробки 📦📦📦\n"
        "Одна з них містить <b>приз 30 грн</b> 💸\n\n"

        "Обери коробку 👇",
        parse_mode="HTML",
        reply_markup=choose_box_kb(),
    )


@router.callback_query(F.data.startswith("box:"))
async def open_boxes(cb: CallbackQuery):
    user_id = cb.from_user.id

    if user_id in _played_users:
        await cb.answer("❌ Ти вже зіграв у цю гру в поточній сесії!", show_alert=True)
        return

    _played_users.add(user_id)

    await cb.answer()
    await cb.message.edit_reply_markup(reply_markup=None)

    user_choice = int(cb.data.split(":")[1]) - 1

    # Одразу повертаємо гравця в головне меню
    gift_claimed = await has_claimed_gift(user_id)
    await cb.message.answer(
        "🔙 Повертаємось у головне меню...",
        reply_markup=main_menu(is_admin=(user_id == ADMIN_ID), user_has_gift=gift_claimed),
    )

    # === Гра ===
    try:
        winrate = await get_winrate()
        if winrate > 1:
            winrate /= 100
    except Exception:
        winrate = 0.33

    is_win = random.random() < winrate
    winning_box = user_choice if is_win else random.choice([i for i in range(3) if i != user_choice])

    # Анімація
    header = "<b>🎯 Один із трьох</b>\n\n"
    emojis = ["📦", "📦", "📦"]

    result_msg = await cb.message.answer(
        header + "📦  📦  📦\n\n💫 Відкриваємо коробки...",
        parse_mode="HTML"
    )

    for i in range(3):
        await asyncio.sleep(1.0)
        emojis[i] = "💰" if i == winning_box else "❌"
        try:
            await result_msg.edit_text(
                header + "  ".join(emojis) + "\n\n💫 Відкриваємо коробки...",
                parse_mode="HTML"
            )
        except Exception:
            pass

    await asyncio.sleep(0.8)
    boxes_str = "  ".join(emojis)

    # === Результат + сповіщення адміну ===
    admin_status = ""

    if is_win:
        allowed, _ = await can_receive_prize(user_id, prize_amount=30)

        if allowed:
            await add_to_balance(user_id, 30)
            await add_game_win(user_id)
            await add_daily_game_win(user_id, 30)

            from db.winlog import log_win

            await log_win(
                user_id, cb.from_user.username, cb.from_user.full_name,
                "game", "Один з трьох", 30
            )

            await result_msg.edit_text(
                f"{header}{boxes_str}\n\n"
                f"<b>🎉 Вітаю!</b>\n"
                f"Твоя коробка <b>📦 {user_choice + 1}</b> — виграшна!\n\n"
                f"<b>+30 грн</b> нараховано на баланс 💸",
                parse_mode="HTML",
            )
            admin_status = " | +30 грн на баланс"
        else:
            await result_msg.edit_text(
                f"{header}{boxes_str}\n\n"
                f"<b>🎉 Технічно перемога!</b>\n"
                f"Твоя коробка <b>📦 {user_choice + 1}</b> — виграшна!\n\n"
                f"💸 Виграш <b>30 грн</b> буде зарахований до депозиту",
                parse_mode="HTML",
            )
            admin_status = " | +30 грн до депозиту"
    else:
        await result_msg.edit_text(
            f"{header}{boxes_str}\n\n"
            f"<b>❌ Не пощастило!</b>\n"
            f"Виграш був у коробці <b>📦 {winning_box + 1}</b>",
            parse_mode="HTML",
        )

    # === Сповіщення адміністратору ===
    try:
        await add_game_result("Один з трьох", is_win)
        username = f"@{cb.from_user.username}" if cb.from_user.username else f"<a href='tg://user?id={cb.from_user.id}'>{cb.from_user.full_name}</a>"

        admin_msg = (
            f"🎯 Гравець зіграв у 'Один із трьох'\n"
            f"👤 {cb.from_user.full_name} ({username})\n"
            f"Результат: {'ВИГРАВ' if is_win else 'ПРОГРАВ'}{admin_status}"
        )

        await cb.bot.send_message(ADMIN_ID, admin_msg, parse_mode="HTML")
    except Exception:
        pass