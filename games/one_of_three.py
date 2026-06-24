
import asyncio
import random
from aiogram import F, types, Router
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from db import add_game_result, get_winrate, has_claimed_gift, save_notification, add_game_win
from handlers.menu import main_menu
from handlers.config import ADMIN_ID

router = Router(name="one_of_three")

_played_users: set[int] = set()


def choose_box_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="📦 1", callback_data="box:1"),
        InlineKeyboardButton(text="📦 2", callback_data="box:2"),
        InlineKeyboardButton(text="📦 3", callback_data="box:3"),
    ]])


def reward_kb(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🏆 Champion",   callback_data=f"choose_reward:champion:{user_id}"),
        InlineKeyboardButton(text="🎰 Superomatic", callback_data=f"choose_reward:superomatic:{user_id}"),
    ]])


@router.message(F.text == "🎯 Один з трьох")
async def start_one_of_three(message: types.Message):
    user_id = message.from_user.id
    if user_id in _played_users:
        await message.answer("❌ Ти вже зіграв у цю гру в цій сесії.")
        return
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
        await cb.answer("Ти вже зіграв!", show_alert=True)
        return
    _played_users.add(user_id)

    await cb.answer()
    # Прибираємо клавіатуру одразу
    await cb.message.edit_reply_markup(reply_markup=None)

    # Одразу відправляємо головне меню — гравець більше не може натискати кнопки ігор
    gift_claimed = await has_claimed_gift(user_id)
    await cb.message.answer(
        "🔙 Повертаємось у головне меню.",
        reply_markup=main_menu(is_admin=(user_id == ADMIN_ID), user_has_gift=gift_claimed),
    )

    # Далі — анімація і результат у тому самому повідомленні з коробками
    user_choice = int(cb.data.split(":")[1]) - 1

    try:
        winrate = await get_winrate()
        if winrate > 1:
            winrate /= 100
    except Exception:
        winrate = 0.33

    is_win = random.random() < winrate
    winning_box = user_choice if is_win else random.choice([i for i in range(3) if i != user_choice])

    emojis = ["📦", "📦", "📦"]
    header = "<b>🎯 Один із трьох</b>\n\n"

    msg = await cb.message.edit_text(
        header + "📦  📦  📦\n\n💫 Відкриваємо коробки...",
        parse_mode="HTML",
    )

    for i in range(3):
        await asyncio.sleep(1.0)
        emojis[i] = "💰" if i == winning_box else "❌"
        mood = random.choice(["😮", "🤔", "😯", "😬", "🫢"])
        try:
            await msg.edit_text(
                header + "  ".join(emojis) + f"\n\n{mood} Відкриваємо коробки...",
                parse_mode="HTML",
            )
        except Exception:
            pass

    await asyncio.sleep(0.8)
    boxes_str = "  ".join(emojis)

    if is_win:
        await msg.edit_text(
            f"{header}{boxes_str}\n\n"
            f"<b>🎉 Вітаю!</b>\n"
            f"Твоя коробка <b>📦 {user_choice + 1}</b> — виграшна 💰\n\n"
            f"Отримуєш <b>30 грн!</b> 💸\n\n"
            "Оберіть тип коду:",
            parse_mode="HTML",
            reply_markup=reward_kb(user_id),
        )
        await add_game_win(user_id)
        outcome = "✅ ВИГРАВ"
    else:
        await msg.edit_text(
            f"{header}{boxes_str}\n\n"
            f"<b>❌ Не пощастило!</b>\n"
            f"Твоя коробка <b>📦 {user_choice + 1}</b> була порожня 😢\n"
            f"Виграш був у <b>📦 {winning_box + 1}</b> 💰\n\n"
            "🔁 Спробуй ще раз пізніше!",
            parse_mode="HTML",
        )
        outcome = "❌ ПРОГРАВ"

    try:
        await add_game_result("Один з трьох", is_win)
    except Exception as e:
        print(f"❌ DB Error: {e}")

    try:
        username = f"@{cb.from_user.username}" if cb.from_user.username else f"<a href='tg://user?id={user_id}'>Профіль</a>"
        await cb.bot.send_message(
            ADMIN_ID,
            f"🎯 <b>Гравець зіграв у 'Один із трьох'</b>\n"
            f"👤 {cb.from_user.full_name} ({username})\n"
            f"🏁 Результат: {outcome}\n"
            f"📊 Winrate: {winrate * 100:.1f}%",
            parse_mode="HTML",
        )
        await save_notification(
            user_id, cb.from_user.username or "-", cb.from_user.full_name or "-",
            "one_of_three", f"🎯 Один із трьох — {outcome}",
        )
    except Exception:
        pass


