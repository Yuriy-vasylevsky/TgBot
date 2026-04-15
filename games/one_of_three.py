# import asyncio
# import random
# from aiogram import F, types, Router
# from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
# from db import (
#     add_game_result,
#     get_winrate,
#     has_claimed_gift,
#     save_notification,
#     add_game_win,
# )
# from handlers.menu import main_menu
# from handlers.config import ADMIN_ID

# router = Router(name="one_of_three")


# # ================== Кнопки вибору коробок ==================
# def choose_box_kb() -> InlineKeyboardMarkup:
#     return InlineKeyboardMarkup(
#         inline_keyboard=[
#             [
#                 InlineKeyboardButton(text="📦 1", callback_data="box:1"),
#                 InlineKeyboardButton(text="📦 2", callback_data="box:2"),
#                 InlineKeyboardButton(text="📦 3", callback_data="box:3"),
#             ]
#         ]
#     )


# # ================== Старт гри ==================
# @router.message(F.text == "🎯 Один з трьох")
# async def start_one_of_three(message: types.Message):
#     text = (
#         "<b>🎯 Один із трьох!</b>\n\n"
#         "Перед тобою три закриті коробки 📦📦📦\n"
#         "Одна з них містить <b>приз 30 грн</b> 💸\n\n"
#         "Обери коробку 👇"
#     )
#     await message.answer(text, parse_mode="HTML", reply_markup=choose_box_kb())


# # ================== Вибір коробки ==================
# @router.callback_query(F.data.startswith("box:"))
# async def open_boxes(cb: CallbackQuery):
#     user_choice = int(cb.data.split(":")[1]) - 1
#     user_id = cb.from_user.id

#     # === Отримуємо winrate ===
#     try:
#         winrate = await get_winrate()
#         if winrate > 1:
#             winrate /= 100
#     except Exception:
#         winrate = 0.33

#     is_win = random.random() < winrate
#     winning_box = (
#         user_choice
#         if is_win
#         else random.choice([i for i in range(3) if i != user_choice])
#     )

#     box_emojis = ["📦", "📦", "📦"]
#     base_text = "<b>🎯 Один із трьох</b>\n\n{}"

#     # === 1️⃣ Початкове повідомлення ===
#     msg = await cb.message.edit_text(
#         base_text.format("📦  📦  📦\n\n💫 Відкриваємо коробки..."),
#         parse_mode="HTML",
#     )
#     await cb.answer("Відкриваємо коробки...")

#     # === 2️⃣ Відкриття коробок з анімацією (1 секунда між) ===
#     for i in range(3):
#         await asyncio.sleep(1.0)
#         if i == winning_box:
#             box_emojis[i] = "💰"
#         else:
#             box_emojis[i] = "❌"

#         boxes_state = "  ".join(box_emojis)
#         thinking_emote = random.choice(["😮", "🤔", "😯", "😬", "🫢"])
#         try:
#             await msg.edit_text(
#                 base_text.format(
#                     f"{boxes_state}\n\n{thinking_emote} Відкриваємо коробки..."
#                 ),
#                 parse_mode="HTML",
#             )
#         except Exception:
#             pass

#     await asyncio.sleep(0.8)

#     # === 3️⃣ Результат ===
#     if is_win:
#         result_text = (
#             f"<b>🎉 Вітаю!</b>\n"
#             f"Твоя коробка <b>📦 {user_choice + 1}</b> — виграшна 💰\n\n"
#             f"Отримуєш <b>30 грн!</b> 💸\n\n"
#             "Оберіть, який тип коду бажаєте отримати:"
#         )
#         kb = InlineKeyboardMarkup(
#             inline_keyboard=[
#                 [
#                     InlineKeyboardButton(
#                         text="🏆 Champion",
#                         callback_data=f"choose_reward:champion:{user_id}",
#                     ),
#                     InlineKeyboardButton(
#                         text="🎰 Superomatic",
#                         callback_data=f"choose_reward:superomatic:{user_id}",
#                     ),
#                 ]
#             ]
#         )
#         await msg.edit_text(
#             f"<b>🎯 Один із трьох</b>\n\n{'  '.join(box_emojis)}\n\n{result_text}",
#             parse_mode="HTML",
#             reply_markup=kb,
#         )
#         await add_game_win(cb.from_user.id)
#         outcome = "✅ ВИГРАВ"
#     else:
#         result_text = (
#             f"<b>❌ Не пощастило!</b>\n"
#             f"Твоя коробка <b>📦 {user_choice + 1}</b> була порожня 😢\n"
#             f"Виграш був у <b>📦 {winning_box + 1}</b> 💰\n\n"
#             "🔁 Спробуй ще — удача поруч!"
#         )
#         await msg.edit_text(
#             f"<b>🎯 Один із трьох</b>\n\n{'  '.join(box_emojis)}\n\n{result_text}",
#             parse_mode="HTML",
#         )
#         outcome = "❌ ПРОГРАВ"

#     # === 4️⃣ Статистика ===
#     profile_link = f"<a href='tg://user?id={cb.from_user.id}'>Профіль</a>"
#     username_display = (
#         f"@{cb.from_user.username}" if cb.from_user.username else profile_link
#     )
#     try:
#         await add_game_result("Один з трьох", is_win)
#     except Exception as e:
#         print(f"❌ DB Error: {e}")

#     try:

#         await cb.message.bot.send_message(
#             ADMIN_ID,
#             f"🎯 <b>Гравець зіграв у 'Один із трьох'</b>\n"
#             f"👤 {cb.from_user.full_name} ({username_display})\n"
#             f"🏁 Результат: {outcome}\n"
#             f"📊 Winrate: {winrate * 100:.1f}%",
#             parse_mode="HTML",
#         )
#         await save_notification(
#             cb.from_user.id,
#             cb.from_user.username or "-",
#             cb.from_user.full_name or "-",
#             "one_of_three",
#             f"🎯 Один із трьох — {outcome}",
#         )

#     except Exception:
#         pass

#     # === 5️⃣ Якщо програв — повернення до меню через 2с ===
#     if not is_win:
#         await asyncio.sleep(0.2)
#         gift_claimed = await has_claimed_gift(user_id)
#         await cb.message.answer(
#             "🔙 Повертаємось у головне меню.",
#             reply_markup=main_menu(
#                 is_admin=(user_id == ADMIN_ID),
#                 user_has_gift=gift_claimed,
#             ),
#         )
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