# import aiosqlite
# import logging
# from aiogram.fsm.context import FSMContext
# from aiogram.utils.keyboard import InlineKeyboardBuilder
# from aiogram.types import ReplyKeyboardRemove
# from db import (
#     get_winrate,
#     set_winrate,
#     get_all_users_info,
#     add_promocode,
#     list_promocodes,
#     check_promocode,
#     set_user_access,
#     has_claimed_gift,
#     add_casino_code,
#     ensure_ban_table,
#     ban_user,
#     unban_user,
#     increment_games_played,
#     add_weekly_task,
#     get_notifications,
# )
# from handlers.menu import admin_menu, main_menu, admin_menu2
# from games import games_menu as imported_games_menu
# from handlers.states import WinrateFSM, Broadcast, PromoFSM, EnterPromoFSM, CodeLinkFSM
# import handlers.config as config
# from aiogram import Router, F, types
# from pathlib import Path
# from aiogram.types import Message, CallbackQuery
# from aiogram.fsm.context import FSMContext
# import re
# from aiogram.types import (
#     InlineKeyboardMarkup,
#     InlineKeyboardButton,
#     Message,
#     CallbackQuery,
# )
# from aiogram.fsm.state import StatesGroup, State
# from aiogram.filters.state import StateFilter
# from aiogram.fsm.context import FSMContext
# from aiogram.types import (
#     Message,
#     InlineKeyboardMarkup,
#     InlineKeyboardButton,
#     CallbackQuery,
# )
# from typing import Optional
# from db import DB_PATH
# import random
# import string
# from aiogram import Router, types, F
# from aiogram.fsm.context import FSMContext
# from aiogram.fsm.state import StatesGroup, State
# from aiogram.types import (
#     InlineKeyboardMarkup,
#     InlineKeyboardButton,
#     ReplyKeyboardMarkup,
#     KeyboardButton,
# )
# from handlers.config import ADMIN_ID

# import aiosqlite
# from handlers.menu import main_menu

# router = Router()


# ADMIN_ID = config.ADMIN_ID
# USERS_PER_PAGE = 12

# router = Router()


# # ==========================
# # ⚙️ Адмін панель
# # ==========================
# @router.message(F.text == "⚙️ Адмін панель")
# async def admin_panel(message: types.Message):
#     if message.from_user.id == ADMIN_ID:
#         await message.answer("🔐 Адмін панель", reply_markup=admin_menu())
#     else:
#         await message.answer("⛔ У вас немає доступу")


# # ==========================
# #             ⚙️⚙️⚙️
# # ==========================
# @router.message(F.text == "⚙️⚙️⚙️")
# async def admin_panel(message: types.Message):
#     if message.from_user.id == ADMIN_ID:
#         await message.answer("🔐 Адмін панель", reply_markup=admin_menu2())
#     else:
#         await message.answer("⛔ У вас немає доступу")


# # ==========================
# # 🎯 Winrate
# # ==========================
# @router.message(F.text == "🎯 Winrate")
# async def show_winrate(message: types.Message, state: FSMContext):
#     if message.from_user.id != ADMIN_ID:
#         return
#     current = await get_winrate()
#     user_id = message.from_user.id
#     # gift_claimed = await has_claimed_gift(user_id)
#     percent = round(current * 100)
#     await message.answer(
#         f"🎯 Поточний winrate: <b>{percent}%</b>\n\nВведіть новий відсоток виграшу (0–100):",
#         reply_markup=ReplyKeyboardRemove(),
#         keyboard=main_menu(is_admin=(user_id == ADMIN_ID)),
#     )
#     await state.set_state(WinrateFSM.waiting_for_value)


# @router.message(WinrateFSM.waiting_for_value)
# async def set_new_winrate(message: types.Message, state: FSMContext):
#     if message.from_user.id != ADMIN_ID:
#         return
#     user_id = message.from_user.id  # ← винести сюди
#     try:
#         val = int(message.text.strip())
#         if not (0 <= val <= 100):
#             raise ValueError
#         await set_winrate(val / 100)
#         await message.answer(
#             f"✅ Новий winrate збережено: {val}%",
#             reply_markup=main_menu(is_admin=True),
#         )
#     except ValueError:
#         await message.answer(
#             "❌ Введіть число від 0 до 100.",
#             reply_markup=main_menu(is_admin=True),
#         )
#     await state.clear()


# # ==============================================================================
# #                          Список користувачів
# # ==============================================================================

# from aiogram.utils.keyboard import InlineKeyboardBuilder
# from datetime import datetime, timezone, timedelta
# from aiogram import types, Router, F
# from db import get_all_users_info
# from handlers.config import ADMIN_ID

# USERS_PER_PAGE = 8
# MAX_ACTIONS_TO_SHOW = 20


# def parse_dt_safe(dt_str: str | None) -> datetime:
#     if not dt_str:
#         return datetime.min.replace(tzinfo=timezone.utc)
#     try:
#         dt = datetime.fromisoformat(dt_str)
#         if dt.tzinfo is None:
#             dt = dt.replace(tzinfo=timezone.utc)
#         return dt
#     except Exception:
#         return datetime.min.replace(tzinfo=timezone.utc)


# def format_time_kyiv(dt_str: str | None) -> str:
#     if not dt_str:
#         return "немає даних"
#     try:
#         dt = datetime.fromisoformat(dt_str)
#         if dt.tzinfo is None:
#             dt = dt.replace(tzinfo=timezone.utc)
#         local = dt.astimezone(timezone(timedelta(hours=2)))  # Київ UTC+2
#         now = datetime.now(timezone(timedelta(hours=2)))

#         if local.date() == now.date():
#             return f"сьогодні о {local:%H:%M}"
#         if local.date() == (now - timedelta(days=1)).date():
#             return f"вчора о {local:%H:%M}"
#         return local.strftime("%d.%m.%Y о %H:%M")
#     except Exception:
#         return "—"


# # ────────────────────────────────────────────────
# #          Оновлена функція побудови клавіатури списку
# # ────────────────────────────────────────────────


# async def build_users_keyboard(users: list[dict], page: int) -> InlineKeyboardBuilder:
#     # Сортуємо за останньою активністю (найновіші зверху)
#     users_sorted = sorted(
#         users, key=lambda x: parse_dt_safe(x.get("last_active")), reverse=True
#     )

#     total_pages = (len(users_sorted) + USERS_PER_PAGE - 1) // USERS_PER_PAGE
#     start = (page - 1) * USERS_PER_PAGE
#     end = start + USERS_PER_PAGE
#     page_users = users_sorted[start:end]

#     kb = InlineKeyboardBuilder()

#     for idx, user in enumerate(page_users, start=1):  # 1, 2, 3... на сторінці
#         user_id = user["user_id"]
#         full_name = user.get("full_name") or "Без імені"

#         # Беремо тільки ім'я, обрізаємо якщо дуже довге
#         name_short = full_name.strip()[:30]
#         if not name_short:
#             name_short = "Без імені"

#         btn_text = f"{idx}. {name_short}"

#         kb.row(
#             types.InlineKeyboardButton(
#                 text=btn_text, callback_data=f"user_detail:{user_id}:{page}"
#             )
#         )

#     # Навігація сторінками
#     nav_row = []
#     if page > 1:
#         nav_row.append(
#             types.InlineKeyboardButton(
#                 text="⬅️ Назад", callback_data=f"users_list:{page-1}"
#             )
#         )
#     if end < len(users_sorted):
#         nav_row.append(
#             types.InlineKeyboardButton(
#                 text="Далі ➡️", callback_data=f"users_list:{page+1}"
#             )
#         )

#     if nav_row:
#         kb.row(*nav_row)

#     kb.row(
#         types.InlineKeyboardButton(
#             text="⟲ Оновити список", callback_data=f"users_list:{page}"
#         )
#     )

#     return kb


# async def show_users_list(message_or_query, page: int = 1):
#     users = await get_all_users_info()
#     if not users:
#         text = "🫥 Користувачів ще немає"
#         kb = None
#     else:
#         kb_builder = await build_users_keyboard(users, page)
#         text = f"👥 Користувачі (стор. {page})\n\n"
#         kb = kb_builder.as_markup()

#     if isinstance(message_or_query, types.CallbackQuery):
#         try:
#             await message_or_query.message.edit_text(
#                 text, reply_markup=kb, parse_mode="HTML", disable_web_page_preview=True
#             )
#         except Exception:
#             await message_or_query.message.answer(
#                 text, reply_markup=kb, parse_mode="HTML"
#             )
#         await message_or_query.answer()
#     else:
#         await message_or_query.answer(
#             text, reply_markup=kb, parse_mode="HTML", disable_web_page_preview=True
#         )


# @router.message(F.text == "👥 Список користувачів")
# async def cmd_list_users(message: types.Message):
#     if message.from_user.id != ADMIN_ID:
#         return
#     await show_users_list(message, page=1)


# @router.callback_query(F.data.startswith("users_list:"))
# async def paginate_users_list(callback: types.CallbackQuery):
#     if callback.from_user.id != ADMIN_ID:
#         await callback.answer("Доступно лише адміністратору", show_alert=True)
#         return

#     try:
#         page = int(callback.data.split(":", 1)[1])
#     except:
#         page = 1

#     await show_users_list(callback, page=page)


# # ────────────────────────────────────────────────
# #               Детальна інформація про користувача
# # ────────────────────────────────────────────────


# @router.callback_query(F.data.startswith("user_detail:"))
# async def show_user_detail(callback: types.CallbackQuery):
#     if callback.from_user.id != ADMIN_ID:
#         await callback.answer("Тільки для адміна", show_alert=True)
#         return

#     try:
#         _, user_id_str, from_page_str = callback.data.split(":")
#         user_id = int(user_id_str)
#         from_page = int(from_page_str)
#     except:
#         await callback.answer("Помилка обробки", show_alert=True)
#         return

#     users = await get_all_users_info()
#     user = next((u for u in users if u["user_id"] == user_id), None)

#     if not user:
#         await callback.message.answer("Користувача вже немає в базі.")
#         return

#     # ─── Формуємо текст профілю ────────────────────────────────
#     full_name = user.get("full_name") or "—"
#     username = user.get("username") or "—"
#     reg_date = format_time_kyiv(user.get("registered_at"))
#     last_active = format_time_kyiv(user.get("last_active"))

#     games_played = user.get("games_played", 0)
#     games_won = user.get("games_won", 0)
#     winrate = round(games_won / games_played * 100) if games_played > 0 else 0

#     actions = user.get("last_actions", "")
#     actions_list = [a.strip() for a in actions.split("|") if a.strip()]
#     actions_show = actions_list[-MAX_ACTIONS_TO_SHOW:]  # останні 20
#     actions_text = "\n".join([f"• {act}" for act in actions_show]) or "немає записів"

#     text = (
#         f"👤 <b>{full_name}</b>\n"
#         f"{'@' if username != '—' else ''}{username}\n\n"
#         f"🆔 <code>{user_id}</code>\n"
#         f"📅 Реєстрація: {reg_date}\n"
#         f"🕒 Остання активність: {last_active}\n\n"
#         f"🎮 Зіграно: <b>{games_played}</b>\n"
#         f"🏆 Виграно: <b>{games_won}</b>  ({winrate}%)\n\n"
#         f"<b>Останні дії (до {MAX_ACTIONS_TO_SHOW}):</b>\n"
#         f"{actions_text}\n"
#     )

#     kb = InlineKeyboardBuilder()
#     kb.button(text="← Назад до списку", callback_data=f"users_list:{from_page}")
#     # можна додати ще кнопки: бан, видати бонуси, переглянути платежі тощо

#     try:
#         await callback.message.answer(
#             text,
#             parse_mode="HTML",
#             reply_markup=kb.as_markup(),
#             disable_web_page_preview=True,
#         )
#     except Exception as e:
#         await callback.message.answer(
#             "Не вдалося оновити повідомлення.\n\n" + text, parse_mode="HTML"
#         )

#     await callback.answer()


# # ========================================================================================================
# #                                            📢 Розсилка
# # ========================================================================================================

# from db import DB_PATH, ensure_users_table_and_columns  # ← ДОДАЛИ ЦЕ


# @router.message(F.text == "📢 Розсилка")
# async def start_broadcast(message: types.Message, state: FSMContext):
#     if message.from_user.id != ADMIN_ID:
#         return

#     kb = InlineKeyboardBuilder()
#     kb.button(text="📄 Створити шаблон", callback_data="create_template")
#     kb.button(text="📂 Шаблони", callback_data="show_templates")
#     kb.button(text="❌ Скасувати", callback_data="cancel_broadcast")
#     kb.adjust(2, 1)

#     await state.set_state(Broadcast.waiting_for_text)
#     await message.answer(
#         "✍️ Введіть текст розсилки або використайте шаблон:",
#         reply_markup=kb.as_markup(),
#     )


# @router.message(Broadcast.waiting_for_text)
# async def process_broadcast_text(message: types.Message, state: FSMContext):
#     text = message.text
#     confirm_kb = InlineKeyboardBuilder()
#     confirm_kb.button(text="✅ Надіслати", callback_data="confirm_broadcast")
#     confirm_kb.button(text="❌ Скасувати", callback_data="cancel_broadcast")
#     await state.update_data(broadcast_text=text)
#     await message.answer(
#         f"📨 Текст розсилки:\n\n{text}\n\nНадіслати розсилку?",
#         reply_markup=confirm_kb.as_markup(),
#     )


# @router.callback_query(F.data == "confirm_broadcast")
# async def confirm_broadcast(callback: types.CallbackQuery, state: FSMContext):
#     data = await state.get_data()
#     text = data.get("broadcast_text")
#     if not text:
#         await callback.answer("❌ Текст розсилки порожній!", show_alert=True)
#         return

#     # ←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←
#     await ensure_users_table_and_columns()  # ← ОБОВ'ЯЗКОВО!
#     # ←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←

#     async with aiosqlite.connect(DB_PATH) as conn:  # ← використовуємо DB_PATH
#         async with conn.execute("SELECT user_id FROM users") as cur:
#             rows = await cur.fetchall()

#     count = 0
#     failed = 0
#     for (user_id,) in rows:
#         try:
#             await callback.bot.send_message(user_id, text, parse_mode="HTML")
#             count += 1
#         except Exception:
#             failed += 1
#             continue

#     await callback.message.answer(
#         f"✅ Розсилку завершено!\n\n"
#         f"✅ Успішно: <b>{count}</b>\n"
#         f"❌ Не вдалося: <b>{failed}</b>",
#         parse_mode="HTML",
#     )
#     await state.clear()
#     await callback.answer("Розсилка завершена ✅")


# @router.callback_query(F.data == "cancel_broadcast")
# async def cancel_broadcast(callback: types.CallbackQuery, state: FSMContext):
#     await state.clear()
#     await callback.message.answer("❌ Розсилку скасовано.")
#     await callback.answer()


# # ======================= шаблони++++++++++++++++++++++++++++


# @router.callback_query(F.data == "show_templates")
# async def show_templates(cb: types.CallbackQuery, state: FSMContext):
#     async with aiosqlite.connect(DB_PATH) as db:
#         cur = await db.execute(
#             "SELECT id,title FROM broadcast_templates ORDER BY id DESC"
#         )
#         rows = await cur.fetchall()

#     kb = InlineKeyboardBuilder()

#     if not rows:
#         kb.button(text="🔙 Назад", callback_data="back_to_broadcast")
#         await cb.message.edit_text("📂 Немає шаблонів.", reply_markup=kb.as_markup())
#         await cb.answer()
#         return

#     for tid, title in rows:
#         kb.button(text=title, callback_data=f"use_template:{tid}")
#         kb.button(text="🗑", callback_data=f"delete_template:{tid}")

#     kb.button(text="🔙 Назад", callback_data="back_to_broadcast")
#     kb.adjust(2, 1)

#     await cb.message.edit_text("📂 Шаблони:", reply_markup=kb.as_markup())
#     await cb.answer()


# @router.callback_query(F.data.startswith("use_template:"))
# async def use_template(cb: types.CallbackQuery, state: FSMContext):
#     tid = cb.data.split(":")[1]
#     async with aiosqlite.connect(DB_PATH) as db:
#         cur = await db.execute(
#             "SELECT text FROM broadcast_templates WHERE id=?", (tid,)
#         )
#         row = await cur.fetchone()

#     if not row:
#         return await cb.answer("Помилка шаблону", show_alert=True)

#     text = row[0]
#     await state.update_data(broadcast_text=text)

#     kb = InlineKeyboardBuilder()
#     kb.button(text="✅ Надіслати", callback_data="confirm_broadcast")
#     kb.button(text="❌ Скасувати", callback_data="cancel_broadcast")

#     await cb.message.edit_text(
#         f"📨 Текст розсилки:\n\n{text}\n\nНадіслати?", reply_markup=kb.as_markup()
#     )
#     await cb.answer()


# class TemplateFSM(StatesGroup):
#     waiting_title = State()
#     waiting_body = State()


# @router.callback_query(F.data == "create_template")
# async def create_template(cb: types.CallbackQuery, state: FSMContext):
#     await state.set_state(TemplateFSM.waiting_title)
#     await cb.message.edit_text("📄 Введіть назву шаблону:")
#     await cb.answer()


# @router.message(TemplateFSM.waiting_title)
# async def template_title(message: types.Message, state: FSMContext):
#     await state.update_data(template_title=message.text)
#     await state.set_state(TemplateFSM.waiting_body)
#     await message.answer("✍️ Текст шаблону:")


# @router.message(TemplateFSM.waiting_body)
# async def template_body(message: types.Message, state: FSMContext):
#     data = await state.get_data()
#     title = data["template_title"]
#     text = message.text

#     async with aiosqlite.connect(DB_PATH) as db:
#         await db.execute(
#             "INSERT INTO broadcast_templates (title,text) VALUES (?,?)", (title, text)
#         )
#         await db.commit()

#     await state.clear()
#     await message.answer(f"✅ Шаблон <b>{title}</b> збережено.", parse_mode="HTML")


# @router.callback_query(F.data.startswith("delete_template:"))
# async def ask_delete_template(cb: types.CallbackQuery):
#     tid = cb.data.split(":")[1]

#     kb = InlineKeyboardBuilder()
#     kb.button(text="✅ Так", callback_data=f"confirm_delete_template:{tid}")
#     kb.button(text="❌ Ні", callback_data="show_templates")
#     kb.adjust(2)

#     await cb.message.edit_text("Видалити шаблон?", reply_markup=kb.as_markup())
#     await cb.answer()


# @router.callback_query(F.data.startswith("confirm_delete_template:"))
# async def confirm_delete_template(cb: types.CallbackQuery):
#     tid = cb.data.split(":")[1]

#     async with aiosqlite.connect(DB_PATH) as db:
#         await db.execute("DELETE FROM broadcast_templates WHERE id=?", (tid,))
#         await db.commit()

#     await cb.answer("✅ Видалено.")
#     await show_templates(cb, None)


# @router.callback_query(F.data == "back_to_broadcast")
# async def back_to_broadcast(cb: types.CallbackQuery, state: FSMContext):
#     await start_broadcast(cb.message, state)
#     await cb.answer()


# # ______________________________________________________________________________________________________
# import asyncio
# import aiosqlite
# from aiogram import Router, F, types
# from aiogram.fsm.context import FSMContext
# from aiogram.fsm.state import State, StatesGroup
# from aiogram.utils.keyboard import InlineKeyboardBuilder
# from handlers.config import ADMIN_ID
# from handlers.menu import main_menu


# # ---------------- FSM ----------------
# class MenuUpdate(StatesGroup):
#     waiting_for_text = State()


# # ---------------- Команда для адміна ----------------
# @router.message(F.text == "🛠 Оновити меню")
# async def start_menu_update(message: types.Message, state: FSMContext):
#     if message.from_user.id != ADMIN_ID:
#         return
#     await state.set_state(MenuUpdate.waiting_for_text)

#     cancel_kb = InlineKeyboardBuilder()
#     cancel_kb.button(text="❌ Скасувати", callback_data="cancel_menu_update")

#     await message.answer(
#         "✍️ Введіть текст, який буде надіслано всім користувачам разом з новим меню.\n\n"
#         "Натисніть «❌ Скасувати», щоб вийти.",
#         reply_markup=cancel_kb.as_markup(),
#     )


# # ---------------- Отримання тексту ----------------
# @router.message(MenuUpdate.waiting_for_text)
# async def process_menu_update_text(message: types.Message, state: FSMContext):
#     text = message.text

#     confirm_kb = InlineKeyboardBuilder()
#     confirm_kb.button(text="✅ Надіслати", callback_data="confirm_menu_update")
#     confirm_kb.button(text="❌ Скасувати", callback_data="cancel_menu_update")

#     await state.update_data(update_text=text)
#     await message.answer(
#         f"📨 <b>Підтвердіть оновлення меню</b>\n\n" f"Текст повідомлення:\n\n{text}",
#         parse_mode="HTML",
#         reply_markup=confirm_kb.as_markup(),
#     )


# # ---------------- Підтвердження ----------------
# @router.callback_query(F.data == "confirm_menu_update")
# async def confirm_menu_update(callback: types.CallbackQuery, state: FSMContext):
#     data = await state.get_data()
#     text = data.get("update_text", "")

#     await callback.message.answer("📤 Починаю оновлення меню...")

#     async with aiosqlite.connect("users.db") as conn:
#         async with conn.execute("SELECT user_id FROM users") as cur:
#             rows = await cur.fetchall()

#     total = len(rows)
#     success = 0
#     failed = 0

#     for (user_id,) in rows:
#         gift_claimed = await has_claimed_gift(user_id)
#         try:
#             await callback.bot.send_message(
#                 user_id,
#                 text,
#                 reply_markup=main_menu(
#                     is_admin=(user_id == ADMIN_ID), user_has_gift=gift_claimed
#                 ),
#                 parse_mode="HTML",
#             )
#             success += 1
#             await asyncio.sleep(0.05)
#         except Exception:
#             failed += 1
#             continue

#     await callback.message.answer(
#         f"✅ Оновлення меню завершено!\n\n"
#         f"📬 Успішно: <b>{success}</b>\n"
#         f"⚠️ Помилок: <b>{failed}</b>\n"
#         f"👥 Всього користувачів: <b>{total}</b>",
#         parse_mode="HTML",
#     )

#     await state.clear()
#     await callback.answer()


# # ---------------- Скасування ----------------
# @router.callback_query(F.data == "cancel_menu_update")
# async def cancel_menu_update(callback: types.CallbackQuery, state: FSMContext):
#     await state.clear()
#     await callback.message.answer("❌ Оновлення меню скасовано.")
#     await callback.answer()


# # ___________________________________________________________________________________________________________________


# # ==========================
# # 🎟 Промокоди
# # ==========================


# class PromoFSM(StatesGroup):
#     waiting_for_code = State()  # для ручного вводу промокоду
#     waiting_for_count = State()


# @router.message(F.text == "➕ Створити промокод")
# async def create_promocode(message: types.Message, state: FSMContext):

#     if message.from_user.id != ADMIN_ID:
#         return
#     await state.set_state(PromoFSM.waiting_for_code)
#     await message.answer(
#         "🆕 Введіть новий промокод:", reply_markup=ReplyKeyboardRemove()
#     )


# @router.message(PromoFSM.waiting_for_code)
# async def save_promocode_handler(message: types.Message, state: FSMContext):

#     if message.from_user.id != ADMIN_ID:
#         return
#     code = message.text.strip()
#     # user_id = message.from_user.id
#     await add_promocode(code)
#     await message.answer(
#         f"✅ Промокод <b>{code}</b> збережено",
#         reply_markup=admin_menu(),
#     )
#     await state.clear()


# # __________________________________________________________________________________________________________


# # ---------------- Автоматична генерація ----------------
# @router.message(F.text == "🤞 Згенерувати промо")
# async def ask_promo_count(message: types.Message, state: FSMContext):
#     """Запитує кількість промокодів"""
#     if message.from_user.id != ADMIN_ID:
#         return

#     await state.set_state(PromoFSM.waiting_for_count)

#     # Клавіатура з вибором кількості
#     num_kb = ReplyKeyboardMarkup(
#         keyboard=[
#             [KeyboardButton(text=str(i)) for i in range(1, 6)],
#             [
#                 KeyboardButton(text="10"),
#                 # KeyboardButton(text="20"),
#                 # KeyboardButton(text="50"),
#             ],
#             # [KeyboardButton(text="100")],
#         ],
#         resize_keyboard=True,
#     )

#     # Inline кнопка відміни
#     cancel_kb = InlineKeyboardMarkup(
#         inline_keyboard=[
#             [
#                 InlineKeyboardButton(
#                     text="❌ Відмінити", callback_data="cancel_promo_gen"
#                 )
#             ]
#         ]
#     )

#     await message.answer(
#         "🔢 Введіть або виберіть кількість промокодів для генерації:",
#         reply_markup=num_kb,
#     )
#     await message.answer(
#         "👇 Якщо передумали, натисніть нижче:",
#         reply_markup=cancel_kb,
#     )


# # ---------------- Обробка введеної кількості ----------------
# @router.message(PromoFSM.waiting_for_count)
# async def generate_promocodes(message: types.Message, state: FSMContext):
#     user_id = message.from_user.id
#     try:
#         count = int(message.text)
#         if count <= 0 or count > 100:
#             raise ValueError
#     except ValueError:
#         await message.answer("⚠️ Введіть число від 1 до 100 або натисніть кнопку.")
#         return

#     generated = []
#     for _ in range(count):
#         code = "PROMO-" + "".join(
#             random.choices(string.ascii_uppercase + string.digits, k=6)
#         )
#         await add_promocode(code)
#         generated.append(code)

#     text = "\n".join(generated)
#     await message.answer(
#         f"✅ Згенеровано {count} промокодів:\n\n<code>{text}</code>",
#         parse_mode="HTML",
#         reply_markup=main_menu(is_admin=user_id == ADMIN_ID),
#     )
#     await state.clear()


# # ---------------- Відміна через inline кнопку ----------------
# @router.callback_query(F.data == "cancel_promo_gen")
# async def cancel_promo_gen(callback: types.CallbackQuery, state: FSMContext):
#     """Обробка натискання кнопки 'Відмінити'"""
#     await state.clear()
#     await callback.message.answer(
#         "❌ Створення промокодів скасовано.",
#     )
#     await callback.message.answer(
#         "🔙 Повертаємось у головне меню.",
#         reply_markup=main_menu(is_admin=callback.from_user.id == ADMIN_ID),
#     )
#     await callback.answer()  # закриває “годинник” Telegram


# # ---------------- Допоміжна функція ----------------
# async def add_promocode(code: str):
#     """Додає промокод у базу."""
#     async with aiosqlite.connect(DB_PATH) as db:
#         await db.execute(
#             "INSERT OR IGNORE INTO promocodes (code, active) VALUES (?, 1)", (code,)
#         )
#         await db.commit()


# # ___________________________________________________________________________________________________________


# @router.message(F.text == "🎟 Активні Promo")
# async def show_promocodes(message: types.Message):
#     if message.from_user.id != ADMIN_ID:
#         return
#     codes = await list_promocodes()
#     if not codes:
#         await message.answer("❌ Немає активних промокодів")
#         return

#     formatted_codes = "\n".join([f"🎟️ <code>{code}</code>" for code in codes])
#     builder = InlineKeyboardBuilder()
#     builder.button(text="📋 Скопіювати всі", callback_data="copy_codes")
#     builder.button(text="🗑 Очистити всі", callback_data="confirm_clear_codes")
#     builder.adjust(1)
#     await message.answer(
#         f"🎟 <b>Активні промокоди:</b>\n\n{formatted_codes}",
#         reply_markup=builder.as_markup(),
#     )


# @router.callback_query(F.data == "copy_codes")
# async def copy_codes_callback(callback: types.CallbackQuery):
#     codes = await list_promocodes()
#     if not codes:
#         await callback.message.answer("❌ Немає активних промокодів")
#         await callback.answer()
#         return
#     codes_text = "\n".join(codes)
#     await callback.message.answer(
#         f"📋 <b>Скопіюйте промокоди нижче:</b>\n\n<code>{codes_text}</code>"
#     )
#     await callback.answer("✅ Готово — коди можна скопіювати!")


# @router.callback_query(F.data == "confirm_clear_codes")
# async def confirm_clear_codes(callback: types.CallbackQuery):
#     builder = InlineKeyboardBuilder()
#     builder.button(text="✅ Так, видалити", callback_data="clear_codes")
#     builder.button(text="❌ Скасувати", callback_data="cancel_clear")
#     builder.adjust(2)
#     await callback.message.answer(
#         "⚠️ Ви впевнені, що хочете <b>видалити всі промокоди</b>?",
#         reply_markup=builder.as_markup(),
#     )
#     await callback.answer()


# @router.callback_query(F.data == "clear_codes")
# async def clear_codes(callback: types.CallbackQuery):
#     await clear_all_promocodes()
#     await callback.message.answer("✅ Усі промокоди успішно видалено.")
#     await callback.answer("Видалено ✅")


# @router.callback_query(F.data == "cancel_clear")
# async def cancel_clear(callback: types.CallbackQuery):
#     await callback.message.answer("Операцію скасовано.")
#     await callback.answer("❌ Скасовано")


# # ==========================
# # Очистка промокодів
# # ==========================
# async def clear_all_promocodes():
#     async with aiosqlite.connect("users.db") as db:
#         await db.execute("DELETE FROM promocodes")
#         await db.commit()


# # ==========================
# # Введення промокоду користувачем
# # ==========================
# @router.message(F.text == "🎟 Ввести промокод")
# async def enter_promocode(message: types.Message, state: FSMContext):
#     await state.set_state(EnterPromoFSM.waiting_for_code)
#     await message.answer("🔑 Введіть ваш промокод:", reply_markup=ReplyKeyboardRemove())
#     # await increment_games_played(message.from_user.id)


# @router.message(EnterPromoFSM.waiting_for_code)
# async def check_user_promo(message: types.Message, state: FSMContext):
#     code = message.text.strip()
#     user_id = message.from_user.id

#     # Перевіряємо, чи користувач вже отримав подарунок
#     gift_claimed = await has_claimed_gift(user_id)

#     if await check_promocode(code):
#         await set_user_access(user_id, True)
#         text = (
#             "✅ <b>Промокод активовано!</b>\n\n"
#             "🎮 Виберіть гру, щоб перевірити свою удачу!\n\n"
#             "🎁 Виграні купони можна поставити в казино 🎰"
#         )
#         await increment_games_played(message.from_user.id)
#         await message.answer(text, reply_markup=imported_games_menu())
#     else:
#         # Передаємо актуальний стан подарунка у меню
#         await message.answer(
#             "❌ Невірний або вже використаний промокод.",
#             reply_markup=main_menu(
#                 is_admin=(user_id == ADMIN_ID), user_has_gift=gift_claimed
#             ),
#         )

#     # Очищаємо стан FSM
#     await state.clear()


# # ======================
# # СТАНИ
# # ======================
# class AddCodeFSM(StatesGroup):
#     waiting_for_code = State()


# # class CodeLinkFSM(StatesGroup):
# #     waiting_for_code = State()


# # FSM для додавання коду
# class AddCodeFSM(StatesGroup):
#     waiting_for_type = State()
#     waiting_for_code = State()


# # ======================
# # ДОДАВАННЯ КОДУ (для адміна)
# # ======================
# @router.message(F.text == "➕ Додати код")
# async def ask_code_type(message: Message):
#     if message.from_user.id != ADMIN_ID:
#         await message.answer("⛔ Тільки адміністратор.")
#         return

#     kb = InlineKeyboardMarkup(
#         inline_keyboard=[
#             [
#                 InlineKeyboardButton(
#                     text="🏆 Champion", callback_data="add_code_type:champion"
#                 ),
#                 InlineKeyboardButton(
#                     text="🎰 Superomatic", callback_data="add_code_type:superomatic"
#                 ),
#             ]
#         ]
#     )
#     await message.answer("Виберіть тип коду для додавання:", reply_markup=kb)


# @router.callback_query(F.data.startswith("add_code_type:"))
# async def on_choose_add_type(cb: CallbackQuery, state: FSMContext):
#     _, code_type = cb.data.split(":")
#     await state.update_data(casino_type=code_type)
#     await state.set_state(AddCodeFSM.waiting_for_code)
#     await cb.message.answer(f"Введіть новий код для {code_type}:")
#     await cb.answer()


# @router.message(AddCodeFSM.waiting_for_code)
# async def add_code_receive(message: Message, state: FSMContext):
#     data = await state.get_data()
#     casino_type = data.get("casino_type")
#     code = message.text.strip()

#     if not re.fullmatch(r"(\d{2}-){6}\d{2}", code):
#         await message.answer("❌ Невірний формат! Приклад: 11-36-36-50-20-11-33")
#         return

#     await add_casino_code(code, casino_type)

#     await message.answer(
#         f"✅ Код <code>{code}</code> додано до {casino_type}.", parse_mode="HTML"
#     )
#     await state.clear()


# class AddCodeFSM(StatesGroup):
#     waiting_for_code = State()


# # ++++++++++++++++++             код в посилання            +++++++++++++++++++++++++++++++++


# @router.message(F.text.regexp(r"^\d{2}(?:-\d{2}){6}$"))
# async def auto_generate_links(message: Message, state: FSMContext):
#     current_state = await state.get_state()

#     # якщо бот зараз очікує код від адміна — пропускаємо
#     if current_state == AddCodeFSM.waiting_for_code.state:
#         return

#     code = message.text.strip().replace("-", "")
#     await message.answer(f"🏆 Champion:\nhttps://spinplanet.net/?login_code={code}")
#     # await message.answer(f"🎰 Superomatic:\nhttps://code.greenhost.pw/?c={code}")


# # ________________________________________________БАН________________________________________________________________


# async def is_banned(user_id: int) -> bool:
#     async with aiosqlite.connect(DB_PATH) as db:
#         async with db.execute(
#             "SELECT 1 FROM banned_users WHERE user_id=?", (user_id,)
#         ) as cur:
#             row = await cur.fetchone()
#             return bool(row)


# async def list_banned() -> list[tuple]:
#     async with aiosqlite.connect(DB_PATH) as db:
#         async with db.execute(
#             """
#             SELECT b.user_id, u.full_name, b.reason, b.banned_by, b.ts
#             FROM banned_users b
#             LEFT JOIN users u ON u.user_id = b.user_id
#             ORDER BY b.ts DESC
#             """
#         ) as cur:
#             return await cur.fetchall()


# # -----------------------
# # FSM
# # -----------------------
# class BanStates(StatesGroup):
#     waiting_for_ban_id = State()
#     waiting_for_unban_id = State()
#     waiting_for_ban_reason = State()


# # -----------------------
# # Адмінські хендлери (Router)
# # -----------------------


# # Кнопка: почати бан (адмін натискає)
# @router.message(F.text == "🚫 Забанити")
# async def cmd_start_ban(message: types.Message, state: FSMContext):
#     if message.from_user.id != ADMIN_ID:
#         await message.answer("⛔ Тільки адміністратор.")
#         return
#     await message.answer("Введи ID користувача для бану:")
#     await state.set_state(BanStates.waiting_for_ban_id)


# @router.message(BanStates.waiting_for_ban_id)
# async def handle_ban_id(message: types.Message, state: FSMContext):
#     if not message.text.isdigit():
#         await message.answer("Введи тільки числовий ID.")
#         return
#     uid = int(message.text)
#     if uid == ADMIN_ID:
#         await message.answer("⛔ Нельзя банити себе.")
#         await state.clear()
#         return
#     await state.update_data(ban_target=uid)
#     await message.answer("Введи причину бану (можеш залишити порожньою):")
#     await state.set_state(BanStates.waiting_for_ban_reason)


# @router.message(BanStates.waiting_for_ban_reason)
# async def handle_ban_reason(message: types.Message, state: FSMContext):
#     data = await state.get_data()
#     uid = data.get("ban_target")
#     reason = message.text.strip() or None
#     await ban_user(uid, banned_by=message.from_user.id, reason=reason)
#     await state.clear()
#     await message.answer(
#         f"✅ Користувач <code>{uid}</code> заблокований.\nПричина: {reason or '—'}",
#         parse_mode="HTML",
#     )


# @router.message(BanStates.waiting_for_ban_reason)
# async def handle_ban_reason(message: types.Message, state: FSMContext):
#     data = await state.get_data()
#     uid = data.get("ban_target")
#     reason = message.text.strip() or None
#     await ban_user(uid, banned_by=message.from_user.id, reason=reason)
#     await state.clear()
#     await message.answer(
#         f"✅ Користувач <code>{uid}</code> заблокований.\nПричина: {reason or '—'}",
#         parse_mode="HTML",
#         reply_markup=admin_menu(),
#     )


# # -----------------------
# # Розбан
# # -----------------------
# @router.message(F.text == "🔓 Розбанити")
# async def cmd_start_unban(message: types.Message, state: FSMContext):
#     if message.from_user.id != ADMIN_ID:
#         await message.answer("⛔ Тільки адміністратор.")
#         return
#     await message.answer("Введи ID користувача для розбану (тільки цифри):")
#     await state.set_state(BanStates.waiting_for_unban_id)


# @router.message(BanStates.waiting_for_unban_id)
# async def handle_unban_id(message: types.Message, state: FSMContext):
#     text = message.text.strip()
#     if not text.isdigit():
#         await message.answer("Невірний формат. Введи тільки числовий ID або /cancel.")
#         return
#     uid = int(text)
#     await unban_user(uid)
#     await state.clear()
#     await message.answer(
#         f"✅ Користувач <code>{uid}</code> розблокований.",
#         parse_mode="HTML",
#         reply_markup=admin_menu(),
#     )


# # -----------------------
# # Список банів
# # -----------------------


# @router.message(F.text == "📋 Список банів")
# async def view_banned_list(message: types.Message):
#     if message.from_user.id != ADMIN_ID:
#         await message.answer("⛔ Тільки адміністратор.")
#         return

#     rows = await list_banned()
#     if not rows:
#         await message.answer(
#             "📭 Список банів пустий.", reply_markup=main_menu(is_admin=True)
#         )
#         return

#     lines = []
#     for uid, full_name, reason, banned_by, ts in rows:
#         name = full_name or "—"
#         by = str(banned_by) if banned_by else "—"
#         r = reason if reason else "—"
#         lines.append(
#             f"👤 <b>{name}</b>\n 🔮ID: <code>{uid}</code>\n 📄Причина: {r}\n🕒 {ts}\n"
#         )

#     text = "📋 <b>Заблоковані користувачі:</b>\n\n" + "\n".join(lines)
#     await message.answer(text, parse_mode="HTML", reply_markup=admin_menu())


# # 🔒 by: {by}
# # -----------------------
# # Cancel / back
# # -----------------------
# @router.message(F.text.in_({"/cancel", "❌ Відмінити", "скасувати"}))
# async def cancel_state(message: types.Message, state: FSMContext):
#     await state.clear()
#     await message.answer(
#         "❌ Дія скасована.",
#         reply_markup=main_menu(is_admin=(message.from_user.id == ADMIN_ID)),
#     )


# # _______________________________ Оновлення карт ______________________________

# from aiogram.fsm.state import StatesGroup, State
# from aiogram.fsm.context import FSMContext
# from db import get_cards, update_card
# from aiogram import Router, types, F
# from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove

# # router = Router()


# class CardFSM(StatesGroup):
#     waiting_for_bank = State()
#     waiting_for_number = State()


# @router.message(F.text == "💳 Керування картами")
# async def manage_cards(message: types.Message, state: FSMContext):
#     if message.from_user.id != ADMIN_ID:
#         return

#     cards = await get_cards()
#     text = "🏦 Поточні картки:\n\n" + "\n".join(
#         [f"{bank}: <code>{num}</code>" for bank, num in cards]
#     )

#     kb = ReplyKeyboardMarkup(
#         keyboard=[
#             [KeyboardButton(text="Приват"), KeyboardButton(text="Ощад")],
#             [KeyboardButton(text="❌ Відмінити")],
#         ],
#         resize_keyboard=True,
#     )

#     await message.answer(
#         f"{text}\n\n🔧 Виберіть банк для редагування:", reply_markup=kb
#     )
#     await state.set_state(CardFSM.waiting_for_bank)


# @router.message(CardFSM.waiting_for_bank)
# async def ask_new_card(message: types.Message, state: FSMContext):
#     bank = message.text
#     if bank == "❌ Відмінити":
#         await state.clear()
#         await message.answer("❌ Скасовано.", reply_markup=admin_menu())
#         return

#     await state.update_data(bank_name=bank)
#     await message.answer(
#         f"💳 Введіть новий номер картки для {bank}:", reply_markup=ReplyKeyboardRemove()
#     )
#     await state.set_state(CardFSM.waiting_for_number)


# @router.message(CardFSM.waiting_for_number)
# async def save_new_card(message: types.Message, state: FSMContext):
#     data = await state.get_data()
#     bank_name = data.get("bank_name")
#     new_number = message.text.strip()

#     await update_card(bank_name, new_number)
#     await message.answer(
#         f"✅ Картку для {bank_name} оновлено на:\n<code>{new_number}</code>",
#         parse_mode="HTML",
#         reply_markup=admin_menu(),
#     )
#     await state.clear()


# from aiogram import Router, F, types
# from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
# from handlers.config import ADMIN_ID
# from db import reset_all_game_stats

# # router = Router()


# @router.message(F.text == "🧹 Очистити статистику ігор")
# async def confirm_clear_stats(message: types.Message):
#     if message.from_user.id != ADMIN_ID:
#         await message.answer("⛔ Ця команда доступна лише адміну.")
#         return

#     keyboard = InlineKeyboardMarkup(
#         inline_keyboard=[
#             [
#                 InlineKeyboardButton(
#                     text="✅ Так, очистити", callback_data="admin:confirm_clear_stats"
#                 ),
#                 InlineKeyboardButton(text="❌ Ні", callback_data="admin:cancel_clear"),
#             ]
#         ]
#     )
#     await message.answer(
#         "⚠️ Ви впевнені, що хочете обнулити статистику всіх користувачів?",
#         reply_markup=keyboard,
#     )


# @router.callback_query(F.data == "admin:confirm_clear_stats")
# async def clear_stats(cb: types.CallbackQuery):
#     if cb.from_user.id != ADMIN_ID:
#         await cb.answer("⛔ Тільки адміністратор може це зробити.")
#         return

#     await cb.answer()
#     await reset_all_game_stats()
#     await cb.message.edit_text("✅ Статистика всіх гравців успішно обнулена!")


# @router.callback_query(F.data == "admin:cancel_clear")
# async def cancel_clear(cb: types.CallbackQuery):
#     await cb.answer("❌ Скасовано.")
#     await cb.message.edit_text("Очищення статистики скасовано.")


# # _________________________ скачати бд ________________________________________________

# from aiogram import Router, F, types
# from aiogram.types import FSInputFile
# from handlers.config import ADMIN_ID
# from pathlib import Path


# @router.message(F.text == "📦 Скачати БД")
# async def download_db(message: types.Message):
#     """Відправляє адміну файл бази даних users.db"""
#     if message.from_user.id != ADMIN_ID:
#         await message.answer("⛔ Ця команда доступна лише адміну.")
#         return

#     db_path = Path(__file__).resolve().parent.parent / "users.db"

#     if not db_path.exists():
#         await message.answer("⚠️ Файл бази даних не знайдено.")
#         return

#     await message.answer("⏳ Готую базу даних до відправки...")
#     await message.answer_document(
#         FSInputFile(db_path), caption="📦 База даних користувачів"
#     )


# # ________________________________________ тижневі завдання ________________________________________________

# from aiogram import F, types
# from aiogram.fsm.state import State, StatesGroup
# from aiogram.fsm.context import FSMContext
# from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
# import aiosqlite
# from db import add_weekly_task, get_active_tasks
# from handlers.menu import main_menu


# # ===============================
# #   FSM для створення завдань
# # ===============================
# class TaskFSM(StatesGroup):
#     waiting_title = State()
#     waiting_description = State()
#     waiting_reward = State()
#     waiting_duration = State()


# @router.message(F.text == "🗓 Додати тижневе завдання")
# async def ask_task_title(message: types.Message, state: FSMContext):
#     await message.answer("📝 Введіть назву завдання:")
#     await state.set_state(TaskFSM.waiting_title)


# @router.message(TaskFSM.waiting_title)
# async def ask_task_description(message: types.Message, state: FSMContext):
#     await state.update_data(title=message.text)
#     await message.answer("📖 Введіть опис завдання:")
#     await state.set_state(TaskFSM.waiting_description)


# @router.message(TaskFSM.waiting_description)
# async def ask_task_reward(message: types.Message, state: FSMContext):
#     await state.update_data(description=message.text)
#     await message.answer("🎁 Введіть нагороду за виконання:")
#     await state.set_state(TaskFSM.waiting_reward)


# @router.message(TaskFSM.waiting_reward)
# async def ask_task_duration(message: types.Message, state: FSMContext):
#     await state.update_data(reward=message.text)
#     await message.answer(
#         "⏰ Вкажіть час на виконання (наприклад: 7 днів, до неділі, або дата):"
#     )
#     await state.set_state(TaskFSM.waiting_duration)


# @router.message(TaskFSM.waiting_duration)
# async def save_task(message: types.Message, state: FSMContext):
#     data = await state.get_data()
#     await add_weekly_task(
#         data["title"],
#         data["description"],
#         data["reward"],
#         message.text,
#     )
#     await state.clear()
#     await message.answer(
#         "✅ Завдання успішно додано!", reply_markup=main_menu(is_admin=True)
#     )


# # ===============================
# #   Перегляд / Видалення завдань
# # ===============================
# @router.message(F.text == "🗑 Видалити завдання")
# async def show_tasks_to_delete(message: types.Message):
#     tasks = await get_active_tasks()
#     if not tasks:
#         await message.answer("ℹ️ Немає активних тижневих завдань для видалення.")
#         return

#     keyboard = InlineKeyboardMarkup(
#         inline_keyboard=[
#             [
#                 InlineKeyboardButton(
#                     text=f"{t['title'][:40]} 🗑", callback_data=f"delete_task:{t['id']}"
#                 )
#             ]
#             for t in tasks
#         ]
#     )

#     await message.answer(
#         "🗓 <b>Активні тижневі завдання:</b>\nНатисніть на завдання, щоб видалити його.",
#         reply_markup=keyboard,
#         parse_mode="HTML",
#     )


# @router.callback_query(F.data.startswith("delete_task:"))
# async def delete_selected_task(callback: types.CallbackQuery):
#     task_id = int(callback.data.split(":")[1])
#     async with aiosqlite.connect(DB_PATH) as db:
#         await db.execute("DELETE FROM weekly_tasks WHERE id = ?", (task_id,))
#         await db.execute("DELETE FROM user_tasks WHERE task_id = ?", (task_id,))
#         await db.commit()

#     await callback.message.answer(
#         f"✅ Завдання <b>ID {task_id}</b> видалено.", parse_mode="HTML"
#     )
#     await callback.answer("Завдання видалено!")


# # =============================================================================================
# #                              📜 ІСТОРІЯ СПОВІЩЕНЬ (АДМІН)
# # =============================================================================================

# from aiogram import Router, F, types
# from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
# from db import get_notifications
# from handlers.config import ADMIN_ID


# @router.message(F.text == "📜 Історія сповіщень")
# async def show_notifications(message: types.Message):
#     if message.from_user.id != ADMIN_ID:
#         return await message.answer("⛔ Доступ лише для адміністратора.")

#     page = 1
#     filter_type = None
#     records, total_pages = await get_notifications(page=page, filter_type=filter_type)

#     text = "<b>📜 Історія сповіщень</b>\n\n"
#     if records:
#         text += "\n\n".join(records)
#     else:
#         text += "🔹 Поки немає нових сповіщень."

#     kb = build_notifications_kb(page, total_pages, filter_type)
#     await message.answer(text, parse_mode="HTML", reply_markup=kb)


# # ===============================  ⚙️ ПАГІНАЦІЯ ТА ФІЛЬТРИ   ===============================


# @router.callback_query(F.data.startswith("notif_page:"))
# async def paginate_notifications(cb: CallbackQuery):
#     if cb.from_user.id != ADMIN_ID:
#         return await cb.answer("⛔ Доступ лише для адміністратора.", show_alert=True)

#     data = cb.data.split(":")
#     page = int(data[1])
#     filter_type = data[2] if len(data) > 2 and data[2] != "none" else None

#     if page < 1:
#         await cb.answer("🚫 Це перша сторінка.")
#         return

#     records, total_pages = await get_notifications(page=page, filter_type=filter_type)
#     if not records and page > total_pages:
#         await cb.answer("🚫 Це остання сторінка.")
#         return

#     text = "<b>📜 Історія сповіщень</b>\n\n"
#     text += "\n\n".join(records) if records else "🔹 Більше немає записів."

#     kb = build_notifications_kb(page, total_pages, filter_type)
#     await cb.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
#     await cb.answer()


# @router.callback_query(F.data.startswith("notif_filter:"))
# async def filter_notifications(cb: CallbackQuery):
#     if cb.from_user.id != ADMIN_ID:
#         return await cb.answer("⛔ Доступ лише для адміністратора.", show_alert=True)

#     filter_type = cb.data.split(":")[1]
#     page = 1
#     records, total_pages = await get_notifications(page=page, filter_type=filter_type)

#     text = f"<b>📜 Історія сповіщень</b>\n🔍 Фільтр: <code>{filter_type}</code>\n\n"
#     text += "\n\n".join(records) if records else "🔹 Немає записів для цього типу."

#     kb = build_notifications_kb(page, total_pages, filter_type)
#     await cb.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
#     await cb.answer()


# # ===============================   🧩 ДОПОМІЖНА ФУНКЦІЯ КЛАВІАТУРИ   ===============================


# def build_notifications_kb(page: int, total_pages: int, filter_type: str | None):
#     ftype = filter_type or "none"

#     return InlineKeyboardMarkup(
#         inline_keyboard=[
#             [
#                 InlineKeyboardButton(
#                     text="⬅️", callback_data=f"notif_page:{page-1}:{ftype}"
#                 ),
#                 InlineKeyboardButton(
#                     text=f"{page}/{total_pages}", callback_data="noop"
#                 ),
#                 InlineKeyboardButton(
#                     text="➡️", callback_data=f"notif_page:{page+1}:{ftype}"
#                 ),
#             ],
#             [
#                 InlineKeyboardButton(
#                     text="🎰 Слоти", callback_data="notif_filter:slots"
#                 ),
#                 InlineKeyboardButton(
#                     text="🎯 1 із 3", callback_data="notif_filter:one_of_three"
#                 ),
#                 InlineKeyboardButton(
#                     text="🃏 Blackjack", callback_data="notif_filter:blackjack"
#                 ),
#             ],
#             [
#                 InlineKeyboardButton(
#                     text="🎡 Фортуна", callback_data="notif_filter:fortune"
#                 ),
#                 InlineKeyboardButton(
#                     text="🎁 Бонус", callback_data="notif_filter:bonus"
#                 ),
#                 # InlineKeyboardButton(text="🔑 Промокоди", callback_data="notif_filter:promocode"),
#             ],
#             # [
#             #     InlineKeyboardButton(text="🔄 Усі", callback_data="notif_filter:none")
#             # ]
#         ]
#     )


# # =============================================================================================
# #                              🔒 КЕРУВАННЯ СЕЙФОМ (АДМІН)
# # =============================================================================================
# from group_games.group_safe import load_state, save_state, get_win_cell, TOTAL_CELLS


# class SafeFSM(StatesGroup):
#     waiting_for_win_cell = State()


# def safe_admin_keyboard():
#     return InlineKeyboardMarkup(
#         inline_keyboard=[
#             [InlineKeyboardButton(text="🗑 Очистити сейф", callback_data="safe:clear")],
#             [
#                 InlineKeyboardButton(
#                     text="🔢 Встановити виграшне число", callback_data="safe:set_win"
#                 )
#             ],
#             [
#                 InlineKeyboardButton(
#                     text="👁 Поточне виграшне число", callback_data="safe:view_win"
#                 )
#             ],
#             [InlineKeyboardButton(text="📊 Стан сейфа", callback_data="safe:status")],
#         ]
#     )


# @router.message(F.text == "🔒 Сейф")
# async def safe_admin_panel(message: types.Message):
#     if message.from_user.id != ADMIN_ID:
#         return
#     await message.answer(
#         "🔒 <b>Керування сейфом</b>",
#         parse_mode="HTML",
#         reply_markup=safe_admin_keyboard(),
#     )


# # --- Очистити сейф ---
# @router.callback_query(F.data == "safe:clear")
# async def safe_clear_confirm(cb: types.CallbackQuery):
#     if cb.from_user.id != ADMIN_ID:
#         return
#     kb = InlineKeyboardMarkup(
#         inline_keyboard=[
#             [
#                 InlineKeyboardButton(
#                     text="✅ Так, очистити", callback_data="safe:clear_confirm"
#                 ),
#                 InlineKeyboardButton(text="❌ Скасувати", callback_data="safe:back"),
#             ]
#         ]
#     )
#     await cb.message.edit_text(
#         "⚠️ Очистити всі відкриті клітинки та почати новий раунд?", reply_markup=kb
#     )
#     await cb.answer()


# @router.callback_query(F.data == "safe:clear_confirm")
# async def safe_clear_do(cb: types.CallbackQuery):
#     if cb.from_user.id != ADMIN_ID:
#         return
#     win_cell = await get_win_cell()  # ← await
#     await save_state([], win_cell=win_cell)  # ← await
#     await cb.message.edit_text(
#         f"✅ <b>Сейф очищено!</b>\nНовий раунд розпочато.\nВиграшна клітинка залишається: <b>{win_cell}</b>",
#         parse_mode="HTML",
#         reply_markup=safe_admin_keyboard(),
#     )
#     await cb.answer("✅ Сейф очищено!")


# # --- Встановити виграшне число ---
# @router.callback_query(F.data == "safe:set_win")
# async def safe_set_win_ask(cb: types.CallbackQuery, state: FSMContext):
#     if cb.from_user.id != ADMIN_ID:
#         return
#     await state.set_state(SafeFSM.waiting_for_win_cell)
#     kb = InlineKeyboardMarkup(
#         inline_keyboard=[
#             [InlineKeyboardButton(text="❌ Скасувати", callback_data="safe:cancel_fsm")]
#         ]
#     )
#     await cb.message.edit_text(
#         f"🔢 Введіть нове виграшне число (від 1 до {TOTAL_CELLS}):", reply_markup=kb
#     )
#     await cb.answer()


# @router.message(SafeFSM.waiting_for_win_cell)
# async def safe_set_win_save(message: types.Message, state: FSMContext):
#     if message.from_user.id != ADMIN_ID:
#         return
#     try:
#         cell = int(message.text.strip())
#         if cell < 1 or cell > TOTAL_CELLS:
#             raise ValueError
#     except ValueError:
#         await message.answer(f"❌ Введіть число від 1 до {TOTAL_CELLS}")
#         return

#     state_data = await load_state()  # ← await
#     await save_state(state_data.get("opened", []), win_cell=cell)  # ← await
#     await state.clear()
#     await message.answer(
#         f"✅ <b>Виграшну клітинку встановлено: {cell}</b>",
#         parse_mode="HTML",
#         reply_markup=safe_admin_keyboard(),
#     )


# @router.callback_query(F.data == "safe:cancel_fsm")
# async def safe_cancel_fsm(cb: types.CallbackQuery, state: FSMContext):
#     await state.clear()
#     await cb.message.edit_text(
#         "🔒 <b>Керування сейфом</b>",
#         parse_mode="HTML",
#         reply_markup=safe_admin_keyboard(),
#     )
#     await cb.answer("❌ Скасовано")


# # --- Переглянути виграшне число ---
# @router.callback_query(F.data == "safe:view_win")
# async def safe_view_win(cb: types.CallbackQuery):
#     if cb.from_user.id != ADMIN_ID:
#         return
#     win_cell = await get_win_cell()  # ← await
#     await cb.answer(f"🏆 Виграшна клітинка: {win_cell}", show_alert=True)


# # --- Стан сейфа ---
# @router.callback_query(F.data == "safe:status")
# async def safe_status(cb: types.CallbackQuery):
#     if cb.from_user.id != ADMIN_ID:
#         return
#     state = await load_state()  # ← await
#     opened = state.get("opened", [])
#     win_cell = state.get("win_cell", "?")
#     text = (
#         f"📊 <b>Стан сейфа</b>\n\n"
#         f"Відкрито: <b>{len(opened)}</b> / {TOTAL_CELLS}\n"
#         f"Виграшна клітинка: <b>{win_cell}</b>\n"
#         f"Залишилось: <b>{TOTAL_CELLS - len(opened)}</b>"
#     )
#     await cb.message.edit_text(
#         text, parse_mode="HTML", reply_markup=safe_admin_keyboard()
#     )
#     await cb.answer()


# # --- Назад ---
# @router.callback_query(F.data == "safe:back")
# async def safe_back(cb: types.CallbackQuery):
#     await cb.message.edit_text(
#         "🔒 <b>Керування сейфом</b>",
#         parse_mode="HTML",
#         reply_markup=safe_admin_keyboard(),
#     )
#     await cb.answer()
