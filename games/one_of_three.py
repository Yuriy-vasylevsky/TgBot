

# import asyncio
# import random
# from aiogram import F, types, Router
# from aiogram.fsm.context import FSMContext
# from aiogram.fsm.state import State, StatesGroup
# from aiogram.types import (
#     KeyboardButton,
#     ReplyKeyboardMarkup,
#     InlineKeyboardMarkup,
#     InlineKeyboardButton,
# )
# from db import add_game_result, get_winrate, has_claimed_gift
# from menu import main_menu
# from config import ADMIN_ID

# router = Router()


# # ================== FSM ==================
# class CouponGameFSM(StatesGroup):
#     playing = State()


# # ================== Меню ігор ==================
# def games_menu():
#     return ReplyKeyboardMarkup(
#         keyboard=[
#             [KeyboardButton(text="🎰 Слоти")],
#             [KeyboardButton(text="🎯 Один з трьох")],
#             [KeyboardButton(text="🃏 Blackjack")],
#         ],
#         resize_keyboard=True,
#     )


# # ================== Гра ==================
# @router.message(F.text == "🎯 Один з трьох")
# async def start_coupon_game(message: types.Message, state: FSMContext):
#     buttons = [
#         [KeyboardButton(text=f"🎁 Варіант {i}") for i in range(1, 4)],
#         [KeyboardButton(text="🔙 Повернутись до ігор")],
#     ]
#     keyboard = ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

#     await message.answer(
#         "🎯 <b>Один з трьох!</b>\n\n"
#         "Є три варіанти, лише один виграшний 💸\n"
#         "Вгадай, де приз 👇",
#         reply_markup=keyboard,
#         parse_mode="HTML",
#     )
#     await state.set_state(CouponGameFSM.playing)


# @router.message(CouponGameFSM.playing)
# async def coupon_game_choice(message: types.Message, state: FSMContext):
#     if message.text == "🔙 Повернутись до ігор":
#         await message.answer("🔙 Повертаємось у меню ігор.", reply_markup=games_menu())
#         await state.clear()
#         return

#     user_choice = message.text.strip()
#     options = ["🎁 Варіант 1", "🎁 Варіант 2", "🎁 Варіант 3"]

#     if user_choice not in options:
#         await message.answer("⚠️ Оберіть один із трьох варіантів 🎁.")
#         return

#     # === Отримуємо winrate ===
#     try:
#         winrate = await get_winrate()
#         if winrate > 1:
#             winrate /= 100
#     except Exception:
#         winrate = 0.33

#     is_win = random.random() < winrate
#     winning_button = (
#         user_choice
#         if is_win
#         else random.choice([o for o in options if o != user_choice])
#     )

#     # === 1️⃣ Початкове відображення коробок ===
#     box_emojis = ["📦", "📦", "📦"]
#     box_text = (
#         "<b>🎯 Один із трьох</b>\n\n"
#         "Три коробки перед тобою — одна з них містить виграш 💸\n\n"
#         f"{'  '.join(box_emojis)}\n\n"
#         f"Ти вибрав: <b>{user_choice}</b>\n\n"
#         "💫 Відкриваємо коробки..."
#     )
#     msg = await message.answer(box_text, parse_mode="HTML")

#     # === 2️⃣ Анімація відкриття ===
#     open_frames = ["🕐", "🕑", "🕒", "🕓", "🕔", "🕕"]
#     for frame in open_frames:
#         await asyncio.sleep(0.1)
#         try:
#             await msg.edit_text(box_text.replace("💫", f"{frame}"), parse_mode="HTML")
#         except Exception:
#             pass

#     await asyncio.sleep(0.4)

#     # === 3️⃣ Відкриття коробок ===
#     # перетворимо виграшну коробку на 💰, інші на ❌
#     win_index = int(winning_button[-1]) - 1  # 0, 1, або 2
#     for i in range(len(box_emojis)):
#         if i == win_index:
#             box_emojis[i] = "💰"
#         else:
#             box_emojis[i] = "❌"
#         await asyncio.sleep(0.5)
#         boxes_state = f"{'  '.join(box_emojis)}"
#         try:
#             await msg.edit_text(
#                 f"<b>🎯 Один із трьох</b>\n\n"
#                 f"{boxes_state}\n\n"
#                 f"Відкриваємо коробки... {['😮', '🤔', '😬', '😯', '🫢'][i % 5]}",
#                 parse_mode="HTML",
#             )
#         except Exception:
#             pass

#     await asyncio.sleep(0.7)

#     # === 4️⃣ Результат ===
#     if is_win:
#         result_text = (
#             "🎉 <b>Вітаю!</b>\n"
#             "Ти відкрив виграшну коробку і отримуєш <b>30 грн!</b> 💸\n\n"
#             "Оберіть, який тип коду бажаєте отримати:"
#         )
#         kb = InlineKeyboardMarkup(
#             inline_keyboard=[
#                 [
#                     InlineKeyboardButton(
#                         text="🏆 Champion",
#                         callback_data=f"choose_reward:champion:{message.from_user.id}",
#                     ),
#                     InlineKeyboardButton(
#                         text="🎰 Superomatic",
#                         callback_data=f"choose_reward:superomatic:{message.from_user.id}",
#                     ),
#                 ]
#             ]
#         )
#         await msg.edit_text(
#             f"<b>🎯 Один із трьох</b>\n\n{'  '.join(box_emojis)}\n\n{result_text}",
#             parse_mode="HTML",
#             reply_markup=kb,
#         )
#         outcome = "✅ ВИГРАВ"
#     else:
#         result_text = (
#             f"❌ <b>На жаль, не пощастило!</b>\n"
#             f"Виграш був у <b>{winning_button}</b> 💰\n\n"
#             "🔁 Спробуй ще — удача точно прийде!"
#         )
#         await msg.edit_text(
#             f"<b>🎯 Один із трьох</b>\n\n{'  '.join(box_emojis)}\n\n{result_text}",
#             parse_mode="HTML",
#         )
#         outcome = "❌ ПРОГРАВ"

#     # === 5️⃣ Статистика ===
#     try:
#         await add_game_result("Один з трьох", is_win)
#     except Exception as e:
#         print(f"❌ Error saving result: {e}")

#     try:
#         await message.bot.send_message(
#             ADMIN_ID,
#             f"🎯 <b>Гравець зіграв у 'Один із трьох'</b>\n"
#             f"👤 {message.from_user.full_name} (@{message.from_user.username or 'немає'})\n"
#             f"🏁 Результат: {outcome}\n"
#             f"📊 Winrate: {winrate * 100:.1f}%",
#             parse_mode="HTML",
#         )
#     except Exception:
#         pass

#     # === 6️⃣ Якщо програв — повертаємо в меню ===
#     if not is_win:
#         gift_claimed = await has_claimed_gift(message.from_user.id)
#         await asyncio.sleep(1.5)
#         await message.answer(
#             "🔙 Повертаємось у головне меню.",
#             reply_markup=main_menu(
#                 is_admin=(message.from_user.id == ADMIN_ID),
#                 user_has_gift=gift_claimed,
#             ),
#         )

#     await state.clear()

import asyncio
import random
from aiogram import F, types, Router
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from db import add_game_result, get_winrate, has_claimed_gift
from menu import main_menu
from config import ADMIN_ID

router = Router(name="one_of_three")


# ================== Кнопки вибору коробок ==================
def choose_box_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📦 1", callback_data="box:1"),
                InlineKeyboardButton(text="📦 2", callback_data="box:2"),
                InlineKeyboardButton(text="📦 3", callback_data="box:3"),
            ]
        ]
    )


# ================== Старт гри ==================
@router.message(F.text == "🎯 Один з трьох")
async def start_one_of_three(message: types.Message):
    text = (
        "<b>🎯 Один із трьох!</b>\n\n"
        "Перед тобою три закриті коробки 📦📦📦\n"
        "Одна з них містить <b>приз 30 грн</b> 💸\n\n"
        "Обери коробку 👇"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=choose_box_kb())


# ================== Вибір коробки ==================
@router.callback_query(F.data.startswith("box:"))
async def open_boxes(cb: CallbackQuery):
    user_choice = int(cb.data.split(":")[1]) - 1
    user_id = cb.from_user.id

    # === Отримуємо winrate ===
    try:
        winrate = await get_winrate()
        if winrate > 1:
            winrate /= 100
    except Exception:
        winrate = 0.33

    is_win = random.random() < winrate
    winning_box = user_choice if is_win else random.choice([i for i in range(3) if i != user_choice])

    box_emojis = ["📦", "📦", "📦"]
    base_text = "<b>🎯 Один із трьох</b>\n\n{}"

    # === 1️⃣ Початкове повідомлення ===
    msg = await cb.message.edit_text(
        base_text.format("📦  📦  📦\n\n💫 Відкриваємо коробки..."),
        parse_mode="HTML",
    )
    await cb.answer("Відкриваємо коробки...")

    # === 2️⃣ Відкриття коробок з анімацією (1 секунда між) ===
    for i in range(3):
        await asyncio.sleep(1.0)
        if i == winning_box:
            box_emojis[i] = "💰"
        else:
            box_emojis[i] = "❌"

        boxes_state = "  ".join(box_emojis)
        thinking_emote = random.choice(["😮", "🤔", "😯", "😬", "🫢"])
        try:
            await msg.edit_text(
                base_text.format(f"{boxes_state}\n\n{thinking_emote} Відкриваємо коробки..."),
                parse_mode="HTML",
            )
        except Exception:
            pass

    await asyncio.sleep(0.8)

    # === 3️⃣ Результат ===
    if is_win:
        result_text = (
            f"<b>🎉 Вітаю!</b>\n"
            f"Твоя коробка <b>📦 {user_choice + 1}</b> — виграшна 💰\n\n"
            f"Отримуєш <b>30 грн!</b> 💸\n\n"
            "Оберіть, який тип коду бажаєте отримати:"
        )
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🏆 Champion",
                        callback_data=f"choose_reward:champion:{user_id}",
                    ),
                    InlineKeyboardButton(
                        text="🎰 Superomatic",
                        callback_data=f"choose_reward:superomatic:{user_id}",
                    ),
                ]
            ]
        )
        await msg.edit_text(
            f"<b>🎯 Один із трьох</b>\n\n{'  '.join(box_emojis)}\n\n{result_text}",
            parse_mode="HTML",
            reply_markup=kb,
        )
        outcome = "✅ ВИГРАВ"
    else:
        result_text = (
            f"<b>❌ Не пощастило!</b>\n"
            f"Твоя коробка <b>📦 {user_choice + 1}</b> була порожня 😢\n"
            f"Виграш був у <b>📦 {winning_box + 1}</b> 💰\n\n"
            "🔁 Спробуй ще — удача поруч!"
        )
        await msg.edit_text(
            f"<b>🎯 Один із трьох</b>\n\n{'  '.join(box_emojis)}\n\n{result_text}",
            parse_mode="HTML",
        )
        outcome = "❌ ПРОГРАВ"

    # === 4️⃣ Статистика ===
    try:
        await add_game_result("Один з трьох", is_win)
    except Exception as e:
        print(f"❌ DB Error: {e}")

    try:
        await cb.message.bot.send_message(
            ADMIN_ID,
            f"🎯 <b>Гравець зіграв у 'Один із трьох'</b>\n"
            f"👤 {cb.from_user.full_name} (@{cb.from_user.username or 'немає'})\n"
            f"🏁 Результат: {outcome}\n"
            f"📊 Winrate: {winrate * 100:.1f}%",
            parse_mode="HTML",
        )
    except Exception:
        pass

    # === 5️⃣ Якщо програв — повернення до меню через 2с ===
    if not is_win:
        await asyncio.sleep(2)
        gift_claimed = await has_claimed_gift(user_id)
        await cb.message.answer(
            "🔙 Повертаємось у головне меню.",
            reply_markup=main_menu(
                is_admin=(user_id == ADMIN_ID),
                user_has_gift=gift_claimed,
            ),
        )
