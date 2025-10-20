# import asyncio
# import logging
# import random
# from aiogram import F, types
# from aiogram.fsm.context import FSMContext
# from aiogram.fsm.state import State, StatesGroup
# from aiogram.types import KeyboardButton, ReplyKeyboardMarkup
# from db import (
#     add_game_result,
#     add_slot_session,
#     get_user_access,
#     get_winrate,
#     set_winrate,
#     has_claimed_gift,
#     get_free_code,
#     create_pending_reward,
#     get_pending_by_id,
#     set_pending_status,
#     mark_code_used_by_id,
#     mark_code_unused,
# )
# from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
# from aiogram import Router, F, Bot
# from config import ADMIN_ID
# from menu import main_menu

# router = Router()


# class CouponGameFSM(StatesGroup):
#     playing = State()


# class SlotGameFSM(StatesGroup):
#     playing = State()


# def games_menu():
#     keyboard = [["🎰 Слоти"], ["🎯Один з трьох"]]
#     return ReplyKeyboardMarkup(
#         keyboard=[[KeyboardButton(text=b) for b in row] for row in keyboard],
#         resize_keyboard=True,
#     )


# # ___________________________________________________________________________________________________________________________________________
# #                                             =====================  🎯🎯🎯 =====================
# # ___________________________________________________________________________________________________________________________________________


# async def register_game_handlers(dp, bot, main_menu, ADMIN_ID):

#     @dp.message(F.text == "🎯Один з трьох")
#     async def start_coupon_game(message: types.Message, state: FSMContext):
#         buttons = [
#             [types.KeyboardButton(text="🎁 Варіант 1")],
#             [types.KeyboardButton(text="🎁 Варіант 2")],
#             [types.KeyboardButton(text="🎁 Варіант 3")],
#             [types.KeyboardButton(text="🔙 Повернутись до ігор")],
#         ]
#         keyboard = types.ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
#         await message.answer(
#             "🎯 <b>Один з трьох!</b>\n\n"
#             "Правила прості:\n"
#             "👉 Є три варіанти, лише один виграшний.\n"
#             "👉 Якщо пощастить — виграєш купон 💸\n\n"
#             "🔹 Обери свій варіант:",
#             reply_markup=keyboard,
#         )
#         await state.set_state(CouponGameFSM.playing)

#     # --- Обробка вибору ---
#     @dp.message(CouponGameFSM.playing)
#     async def coupon_game_choice(message: types.Message, state: FSMContext):
#         if message.text == "🔙 Повернутись до ігор":
#             await message.answer(
#                 "🔹 Повертаємось у меню ігор.", reply_markup=games_menu()
#             )
#             await state.clear()
#             return

#         video_msg = await message.answer_video(
#             types.FSInputFile("videos/loading.mp4"), caption="💫 Перевіряю..."
#         )
#         await asyncio.sleep(2)
#         try:
#             await bot.delete_message(
#                 chat_id=message.chat.id, message_id=video_msg.message_id
#             )
#         except Exception as e:
#             print("⚠️ Не вдалося видалити відео:", e)

#         # --- Отримуємо актуальний winrate ---
#         try:
#             winrate = await get_winrate()  # повинно повертати float від 0 до 1
#             if winrate > 1:  # якщо зберігаєш як 0–100
#                 winrate = winrate / 100
#         except Exception as e:
#             print("❌ Помилка get_winrate:", e)
#             winrate = 0.33  # запасне значення

#         # Ймовірність виграшу
#         is_win = random.random() < winrate

#         options = ["🎁 Варіант 1", "🎁 Варіант 2", "🎁 Варіант 3"]
#         user_choice = message.text.strip()

#         #    +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#         if is_win:
#             winning_button = user_choice
#             result_text = "🎉 Вітаю! Ви виграли 30 грн! 💸\nОберіть, який тип коду бажаєте отримати:"
#             outcome = "ВИГРАВ ✅"

#             # Кнопки для отримання виграшу
#             kb = InlineKeyboardMarkup(
#                 inline_keyboard=[
#                     [
#                         InlineKeyboardButton(
#                             text="🏆 Champion",
#                             callback_data=f"choose_reward:champion:{message.from_user.id}",
#                         ),
#                         InlineKeyboardButton(
#                             text="🎰 Superomatic",
#                             callback_data=f"choose_reward:superomatic:{message.from_user.id}",
#                         ),
#                     ]
#                 ]
#             )
#             await message.answer(result_text, reply_markup=kb)

#         else:
#             possible = [o for o in options if o != user_choice]
#             winning_button = random.choice(possible)
#             result_text = (
#                 f"❌ На жаль, ви програли.\nВиграш був у кнопці: {winning_button}"
#             )
#             outcome = "ПРОГРАВ ❌"
#             await message.answer(result_text)

#         # --- Повідомлення адміну ---
#         await bot.send_message(
#             ADMIN_ID,
#             f"🎯 <b>Гравець зіграв у 'Один із трьох'</b>\n\n"
#             f"👤 Ім'я: {message.from_user.full_name}\n"
#             f"💬 Username: @{message.from_user.username or 'Немає'}\n"
#             f"📊 Winrate: {winrate * 100:.1f}%\n"
#             f"🏁 Результат: {outcome}",
#         )

#         # --- Збереження результату ---
#         try:
#             await add_game_result("Один з трьох", is_win)
#         except Exception as e:
#             print("❌ Error saving game result:", e)

#         # --- Перевірка подарунка та формування головного меню ---
#         gift_claimed = await has_claimed_gift(message.from_user.id)
#         keyboard = main_menu(
#             is_admin=(message.from_user.id == ADMIN_ID), user_has_gift=gift_claimed
#         )

#         # --- Відповідь користувачу ---
#         if not is_win:
#             # Якщо програв — просто показуємо результат і головне меню
#             await message.answer(
#                 result_text + "\n\n🔙 Повертаємось у головне меню.",
#                 reply_markup=keyboard,
#             )
#         await state.clear()

#     # ------------------------------------------
#     # 🎰 СЛОТИ
#     # ------------------------------------------

#     @dp.message(F.text == "🎰 Слоти")
#     async def start_slots(message: types.Message, state: FSMContext):
#         # Доступ лише для користувачів з дозволом або адміна
#         if message.from_user.id != ADMIN_ID and not await get_user_access(
#             message.from_user.id
#         ):
#             await message.answer("⛔ У вас немає доступу. Активуйте промокод!")
#             return

#         await state.set_state(SlotGameFSM.playing)
#         await state.update_data(coupons=10, first_bet=False)
#         await message.answer(
#             "🎰 <b>Ласкаво просимо у слот-машину!</b>\n\n"
#             "💎 Твоя ціль — набити <b>30 купонів</b>! (1 🎟 = 1 грн)\n\n"
#             "🎟 Початковий баланс: <b>10 купонів</b>.\n\n"
#             "🎯 Обери ставку та крути барабани — удачі! 🍀",
#             reply_markup=ReplyKeyboardMarkup(
#                 keyboard=[
#                     [KeyboardButton(text="▶️ Почати гру")],
#                     [KeyboardButton(text="ℹ️ Правила та комбінації")],
#                     [KeyboardButton(text="🔙 Повернутись до ігор")],
#                 ],
#                 resize_keyboard=True,
#             ),
#         )

#     # ------------------------------------------
#     # ℹ️ Правила
#     # ------------------------------------------
#     @dp.message(F.text == "ℹ️ Правила та комбінації")
#     async def show_slot_rules(message: types.Message):
#         rules_text = (
#             "🎰 <b>Правила гри у слоти:</b>\n\n"
#             "• На початку ти маєш <b>10 купонів</b>.\n"
#             "• Обери ставку (1, 2 або 3 купони) і крути барабани.\n"
#             "• Виграші:\n\n"
#             "💥 3 однакових символи — ×12\n"
#             "💎 3 сімки (7️⃣) — ×15\n"
#             "🍀 2 сімки — ×7\n"
#             "🔥 2 однакові символи — ×3\n"
#             "✨ 1 сімка — ×1 (повертає ставку)\n\n"
#             "❌ Якщо немає збігів — ставка згорає.\n\n"
#             "🎯 Гра закінчується, коли:\n"
#             "• Баланс = 0 — програв 💀\n"
#             "• Баланс ≥ 30 — виграш 🏆\n\n"
#             "🔹 Повернись до гри кнопкою нижче:"
#         )
#         await message.answer(
#             rules_text,
#             reply_markup=ReplyKeyboardMarkup(
#                 keyboard=[
#                     [KeyboardButton(text="▶️ Почати гру")],
#                     [KeyboardButton(text="🔙 Повернутись до ігор")],
#                 ],
#                 resize_keyboard=True,
#             ),
#         )

#     # ------------------------------------------
#     # ▶️ Почати гру
#     # ------------------------------------------

#     @dp.message(F.text == "▶️ Почати гру")
#     async def enter_slot_game(message: types.Message, state: FSMContext):
#         await show_slot_menu(message, state)

#     # Меню вибору ставки

#     async def show_slot_menu(message: types.Message, state: FSMContext):
#         data = await state.get_data()
#         coupons = data.get("coupons", 10)
#         first_bet = data.get("first_bet", False)

#         keyboard = [
#             [KeyboardButton(text="1 купон"), KeyboardButton(text="2 купони")],
#             [KeyboardButton(text="3 купони")],
#         ]
#         if not first_bet:
#             keyboard.append([KeyboardButton(text="🔙 Повернутись до ігор")])

#         await message.answer(
#             f"💰 Баланс: <b>{coupons}</b> 🎟\n" f"Обери суму ставки:",
#             reply_markup=ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True),
#         )

#     # ------------------------------------------
#     # 🎰 Обертання слотів
#     # ------------------------------------------
#     @dp.message(SlotGameFSM.playing)
#     async def slot_spin(message: types.Message, state: FSMContext):
#         data = await state.get_data()
#         coupons = data.get("coupons", 10)
#         first_bet = data.get("first_bet", False)
#         text = message.text.strip()

#         if not first_bet and text == "🔙 Повернутись до ігор":
#             await message.answer(
#                 "🔹 Повертаємось у меню ігор.", reply_markup=games_menu()
#             )
#             await state.clear()
#             return

#         try:
#             bet = int(text.split()[0])
#         except Exception:
#             await message.answer("⚠️ Виберіть ставку з кнопок.")
#             return

#         if bet > coupons:
#             await message.answer("⚠️ Недостатньо купонів для цієї ставки.")
#             return

#         if not first_bet:
#             await state.update_data(first_bet=True)

#         # ---------------------- WINRATE ----------------------
#         try:
#             winrate = await get_winrate()  # 0.0–1.0
#             if winrate > 1:
#                 winrate = winrate / 100
#         except Exception as e:
#             logging.error(f"Помилка get_winrate: {e}")
#             winrate = 0.33

#         # ---------------------------------------------------------
#         # 🎯 Визначаємо, чи буде виграш за winrate
#         # ---------------------------------------------------------
#         try:
#             winrate = await get_winrate()  # 0.0–1.0
#             if winrate > 1:
#                 winrate = winrate / 100
#         except Exception as e:
#             logging.error(f"Помилка get_winrate: {e}")
#             winrate = 0.33

#         # ---------------------------------------------------------
#         # 🎯 Визначаємо, чи буде виграш за winrate
#         # ---------------------------------------------------------
#         is_win = random.random() < winrate

#         symbols = ["🍒", "🍋", "🍊", "🍇", "🍉", "🍓", "🍍", "🥭", "7️⃣"]

#         if is_win:
#             # 🎰 Тип виграшу за внутрішньою ймовірністю
#             roll = random.random()

#             if roll < 0.03:
#                 # 3% — три однакових символи (будь-які)
#                 sym = random.choice(symbols)
#                 reels = [sym, sym, sym]
#                 multiplier = 20
#                 outcome = f"🎉 ТРИ {sym} — x20! Джекпот!"
#             elif roll < 0.07:
#                 # 7% — дві сімки
#                 other = random.choice([s for s in symbols if s != "7️⃣"])
#                 reels = ["7️⃣", "7️⃣", other]
#                 random.shuffle(reels)
#                 multiplier = 7
#                 outcome = "💎 Подвійна удача! 2 сімки — x7!"
#             else:
#                 # 90% — пара фруктів (×3)
#                 fruit = random.choice([s for s in symbols if s != "7️⃣"])
#                 other = random.choice([s for s in symbols if s != fruit])
#                 reels = [fruit, fruit, other]
#                 random.shuffle(reels)
#                 multiplier = 3
#                 outcome = f"✨ Пара {fruit} — x3!"
#         else:
#             # ❌ Програш — без збігів
#             reels = random.sample(symbols[:-1], 3)
#             multiplier = 0
#             outcome = "❌ Програш!"

#         # ---------------------------------------------------------
#         # 💰 Підрахунок виграшу
#         # ---------------------------------------------------------
#         win_amount = int(bet * multiplier)
#         coupons = coupons - bet + win_amount
#         await state.update_data(coupons=coupons)

#         # ---------------------------------------------------------
#         # 📲 Відображення результату
#         # ---------------------------------------------------------
#         await message.answer(
#             f"| {reels[0]} | {reels[1]} | {reels[2]} |\n\n"
#             f"{outcome}\n"
#             f"Ставка: {bet}\n"
#             f"Виграш: {win_amount}\n"
#             f"Баланс: {coupons} 🎟"
#         )

#         try:
#             await add_game_result("Слоти", multiplier > 0)
#         except Exception as e:
#             logging.error(f"Error saving slots result: {e}")

#         # ---------------------- Перевірка завершення ----------------------
#         if coupons <= 0:
#             gift_claimed = await has_claimed_gift(message.from_user.id)
#             keyboard = main_menu(
#                 is_admin=(message.from_user.id == ADMIN_ID), user_has_gift=gift_claimed
#             )
#             await message.answer(
#                 "💀 Ви програли всі купони! Гра завершена.", reply_markup=keyboard
#             )
#             await bot.send_message(
#                 ADMIN_ID,
#                 f"💀 @{message.from_user.username or message.from_user.full_name} програв усі купони у слотах.",
#             )
#             await add_slot_session(message.from_user.id, "lose", 0)
#             await state.clear()
#             return

#         if coupons >= 30:
#             kb = InlineKeyboardMarkup(
#                 inline_keyboard=[
#                     [
#                         InlineKeyboardButton(
#                             text="🏆 Champion",
#                             callback_data=f"choose_reward:champion:{message.from_user.id}",
#                         ),
#                         InlineKeyboardButton(
#                             text="🎰 Superomatic",
#                             callback_data=f"choose_reward:superomatic:{message.from_user.id}",
#                         ),
#                     ]
#                 ]
#             )
#             await message.answer(
#                 "🎉 Вітаю! Ви виграли. Оберіть тип коду:", reply_markup=kb
#             )
#             await bot.send_message(
#                 ADMIN_ID,
#                 f"🏆 @{message.from_user.username or message.from_user.full_name} виграв {coupons} купонів у слотах!",
#             )
#             await add_slot_session(message.from_user.id, "win", coupons)
#             await state.clear()
#             return

#         await show_slot_menu(message, state)


# # ___________________________________________________________________________________________________________________________________________
# #                                                         ОТРИМАННЯ ВИГРАШУ


# # ___________________________________________________________________________________________________________________________________________
# @router.callback_query(F.data.startswith("choose_reward:"))
# async def on_choose_reward(cb: CallbackQuery, bot: Bot):
#     parts = cb.data.split(":")
#     if len(parts) < 3:
#         await cb.answer("Невірні дані.", show_alert=True)
#         return

#     _, casino_type, user_id_s = parts
#     try:
#         user_id = int(user_id_s)
#     except ValueError:
#         user_id = cb.from_user.id

#     # Дістаємо ім’я користувача
#     user_name = cb.from_user.full_name  # first_name + last_name
#     username = cb.from_user.username  # опціонально, якщо потрібен @username

#     # Прибираємо кнопки після натискання
#     try:
#         await cb.message.edit_text(
#             f"🎰 Ви обрали платформу <b>{casino_type.capitalize()}</b>!\nОчікуйте підтвердження адміністратора.",
#             parse_mode="HTML",
#         )
#     except Exception:
#         pass

#     # Беремо вільний код
#     free = await get_free_code(casino_type)
#     gift_claimed = await has_claimed_gift(user_id)
#     if not free:
#         await bot.send_message(
#             user_id,
#             "⚠️ Вибачте — кодів цього типу наразі немає.\nЗверніться до касира.",
#             reply_markup=main_menu(
#                 is_admin=(user_id == ADMIN_ID), user_has_gift=gift_claimed
#             ),  # повернення в головне меню # повернення в головне меню
#         )
#         await cb.answer("Немає вільних кодів цього типу.", show_alert=True)
#         return

#     code_id, code_text = free
#     # Створюємо pending без user_name — тільки з user_id, code_id, casino_type
#     pending_id = await create_pending_reward(user_id, code_id, casino_type)

#     # ==========================================
#     # 2️⃣ Відправка адміну для підтвердження
#     # ==========================================
#     kb_admin = InlineKeyboardMarkup(
#         inline_keyboard=[
#             [
#                 InlineKeyboardButton(
#                     text="✅ Підтвердити",
#                     callback_data=f"reward_confirm:{pending_id}:confirm",
#                 ),
#                 InlineKeyboardButton(
#                     text="❌ Відхилити",
#                     callback_data=f"reward_confirm:{pending_id}:reject",
#                 ),
#             ]
#         ]
#     )
#     await bot.send_message(
#         ADMIN_ID,
#         f"🔔 <b>Гравець просить код для {casino_type}</b>\n\n"
#         f"👤 Ім’я: <b>{user_name}</b>\n"
#         f"🆔 ID: <code>{user_id}</code>\n"
#         f"🔑 Код (зарезервовано): <code>{code_text}</code>",
#         parse_mode="HTML",
#         reply_markup=kb_admin,
#     )

#     gift_claimed = await has_claimed_gift(user_id)
#     await bot.send_message(
#         user_id,
#         "✅ Ваш виграш зафіксовано.\nЗачекайте підтвердження адміністратора.",
#         reply_markup=main_menu(
#             is_admin=(user_id == ADMIN_ID), user_has_gift=gift_claimed
#         ),
#     )
#     await cb.answer()


# # ==========================================
# # 3️⃣ Адмін підтверджує або відхиляє код
# # ==========================================
# @router.callback_query(F.data.startswith("reward_confirm:"))
# async def handle_reward_confirm(cb: CallbackQuery):
#     if cb.from_user.id != ADMIN_ID:
#         await cb.answer("⛔ Тільки адміністратор.", show_alert=True)
#         return

#     parts = cb.data.split(":")
#     if len(parts) != 3:
#         await cb.answer("Невірні дані.", show_alert=True)
#         return

#     _, pending_id_s, action = parts
#     try:
#         pending_id = int(pending_id_s)
#     except ValueError:
#         await cb.answer("Невірний ID.", show_alert=True)
#         return

#     pending = await get_pending_by_id(pending_id)
#     if not pending:
#         await cb.answer("Невідомий запит.", show_alert=True)
#         return

#     user_id = pending["user_id"]
#     code_text = (pending.get("code") or "").replace("-", "")
#     casino_type = pending.get("casino_type")

#     # --- Якщо адмін підтверджує ---
#     if action == "confirm":
#         if not code_text:
#             free_code = await get_free_code(casino_type)
#             if not free_code:
#                 await cb.answer(
#                     "❌ Немає вільних кодів для цього казино.", show_alert=True
#                 )
#                 return
#             code_text = free_code["code"].replace(
#                 "-", ""
#             )  # ✅ тут очищаємо від дефісів
#             await mark_code_used_by_id(free_code["id"], user_id)
#         else:
#             code_text = code_text.replace("-", "")  # ✅ якщо код уже був — теж чистимо

#         # позначаємо pending як підтверджений
#         await set_pending_status(pending_id, "confirmed")

#         # формуємо посилання
#         if casino_type == "champion":
#             url = f"https://spinplanet.net/?login_code={code_text}"
#         else:
#             url = f"https://code.greenhost.pw/?c={code_text}"

#         # повідомлення адміну
#         await cb.message.edit_text(
#             f"✅ Виграш підтверджено.\nКод: {casino_type} - {code_text}"
#         )

#         # повідомлення користувачу
#         try:
#             await cb.bot.send_message(
#                 user_id,
#                 f"🎉 Ваш виграш підтверджено!\n\n🎁 Бажаю удачі в грі\n\n 🔗 {url}",
#             )
#         except Exception as e:
#             logging.warning(f"Не вдалося надіслати код користувачу {user_id}: {e}")

#     # --- Якщо адмін відхиляє ---
#     else:
#         if pending.get("code_id"):
#             await mark_code_unused(pending["code_id"])

#         await set_pending_status(pending_id, "rejected")
#         await cb.message.edit_text(
#             "❌ Виграш відхилено. Код повернуто у пул (якщо був)."
#         )

#         try:
#             await cb.bot.send_message(
#                 user_id,
#                 "❌ Ваш запит на отримання коду відхилено. Адмін зв'яжеться з вами.",
#             )
#         except Exception:
#             pass

#     await cb.answer()
