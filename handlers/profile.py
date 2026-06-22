# # import logging
# # from datetime import datetime, timezone, timedelta

# # import aiosqlite
# # from aiogram import Router, F, types
# # from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# from db import (
#     get_user_data,
#     add_or_update_user,
#     has_claimed_gift,
#     get_issued_checks_for_user,
#     DB_PATH,
#     add_to_balance,
# )
# # from db.wallet import get_balance
# # from handlers.menu import main_menu
# # from handlers.config import ADMIN_ID

# # router = Router()
# # logging.basicConfig(level=logging.INFO)

# # KYIV = timezone(timedelta(hours=3))
# # PROMO_GOAL = 500
# # CASHBACK_GOAL = 1000
# # CASHBACK_PERCENT = 0.10


# # def _today_sum(all_checks: list[dict]) -> int:
# #     today = datetime.now(KYIV).date()
# #     total = 0
# #     for ch in all_checks:
# #         try:
# #             dt = datetime.fromisoformat(ch["issued_at"])
# #             if dt.tzinfo is None:
# #                 dt = dt.replace(tzinfo=timezone.utc)
# #             if dt.astimezone(KYIV).date() == today:
# #                 total += ch["price"]
# #         except Exception:
# #             pass
# #     return total


# # # ──────────────────────────────────────────────────────────────────────────
# # #  ПРОФІЛЬ КОРИСТУВАЧА
# # # ──────────────────────────────────────────────────────────────────────────

# # def build_balance_bar(balance: int) -> str:
# #     levels = [
# #         (5000, "👑"),
# #         (2000, "💎"),
# #         (1000, "🔥"),
# #         (500,  "⚡️"),
# #         (200,  "🌟"),
# #         (0,    "🌱"),
# #     ]
# #     for threshold, icon in levels:
# #         if balance >= threshold:
# #             tier_icon = icon
# #             break
# #     else:
# #         tier_icon = "🌱"

# #     filled = min(int(balance / 200), 10)
# #     bar = "█" * filled + "░" * (10 - filled)
# #     return f"{tier_icon} [{bar}]"


# # def build_profile_text(user_id, username, full_name, balance, weekly_coupons) -> str:
# #     username_line = f"@{username}" if username != "—" else "без username"
# #     balance_bar = build_balance_bar(balance)

# #     if weekly_coupons == 0:
# #         promo_icons = "😔"
# #     else:
# #         promo_icons = "🎟 " * min(weekly_coupons, 15)
# #         if weekly_coupons > 15:
# #             promo_icons += f"+{weekly_coupons - 15}"

# #     return (
# #         f"╔════════════╗\n"
# #         f"║ 👤 <b>МІЙ КАБІНЕТ</b> \n"
# #         f"╚════════════╝\n"
# #         f"<b>{full_name}</b>\n"
# #         f"🆔 <code>{user_id}</code>\n"
# #         f"━━━━━━━━━━━━\n"
# #         f"💰 <b>БАЛАНС</b> : {balance}\n"
# #         f"━━━━━━━━━━━━\n\n"
# #         f"<b>Зібрано PROMO :</b> <code>{weekly_coupons}</code>\n"
# #         f"{promo_icons}\n"
# #     )


# # def build_progress_bars(today_sum: int) -> str:
# #     """
# #     Прогрес-бари на сьогодні. Якщо рівень вже досягнуто (наприклад, перший
# #     промокод отримано), бар автоматично перемикається на прогрес до
# #     НАСТУПНОГО рівня замість того, щоб просто показувати "✅" назавжди.
# #     """

# #     # ── Промокод ──
# #     promo_tier = today_sum // PROMO_GOAL
# #     promo_progress = today_sum % PROMO_GOAL
# #     promo_blocks = int(promo_progress / PROMO_GOAL * 10)
# #     promo_bar = "█" * promo_blocks + "░" * (10 - promo_blocks)

# #     if promo_tier > 0:
# #         promo_line = (
# #             f"🎟 <b>Промокод</b> · отримано {promo_tier} шт ✅\n"
# #             f"  Прогрес до наступного: [{promo_bar}] {promo_progress}/{PROMO_GOAL} грн\n"
# #         )
# #     else:
# #         promo_line = (
# #             f"🎟 <b>Промокод</b> · {PROMO_GOAL} грн\n"
# #             f"  [{promo_bar}] {today_sum}/{PROMO_GOAL} грн\n"
# #         )

# #     # ── Відкат ──
# #     cashback_tier = today_sum // CASHBACK_GOAL
# #     cashback_progress = today_sum % CASHBACK_GOAL
# #     cashback_blocks = int(cashback_progress / CASHBACK_GOAL * 10)
# #     cashback_bar = "█" * cashback_blocks + "░" * (10 - cashback_blocks)

# #     if cashback_tier > 0:
# #         earned = int(cashback_tier * CASHBACK_GOAL * CASHBACK_PERCENT)
# #         cashback_line = (
# #             f"💸 <b>Відкат {int(CASHBACK_PERCENT * 100)}%</b> · нараховано {earned} грн ✅\n"
# #             f"  Прогрес до наступного: [{cashback_bar}] {cashback_progress}/{CASHBACK_GOAL} грн\n"
# #         )
# #     else:
# #         cashback_line = (
# #             f"💸 <b>Відкат {int(CASHBACK_PERCENT * 100)}%</b> · {CASHBACK_GOAL} грн\n"
# #             f"  [{cashback_bar}] {today_sum}/{CASHBACK_GOAL} грн\n"
# #         )

# #     return (
# #         f"\n━━━━━━━━━━━━\n"
# #         f"📊 <b>ПРОГРЕС СЬОГОДНІ</b>\n\n"
# #         f"{promo_line}\n"
# #         f"{cashback_line}"
# #     )


# # async def build_checks_list_text(user_id: int) -> str:
# #     """Список чеків за сьогодні і вчора (без прогрес-барів — вони вже на головному екрані кабінету)."""
# #     all_checks = await get_issued_checks_for_user(user_id)

# #     now = datetime.now(KYIV)
# #     today = now.date()
# #     yesterday = (now - timedelta(days=1)).date()

# #     buckets = {
# #         "сьогодні": [],
# #         "вчора": [],
# #     }

# #     for ch in all_checks:
# #         try:
# #             dt = datetime.fromisoformat(ch["issued_at"])
# #             if dt.tzinfo is None:
# #                 dt = dt.replace(tzinfo=timezone.utc)
# #             d = dt.astimezone(KYIV).date()
# #             if d == today:
# #                 buckets["сьогодні"].append((ch, dt))
# #             elif d == yesterday:
# #                 buckets["вчора"].append((ch, dt))
# #         except Exception:
# #             pass

# #     if not any(buckets.values()):
# #         return (
# #             f"🔑 <b>МОЇ ЧЕКИ</b>\n\n"
# #             f"😔 За останні 2 дні чеків немає"
# #         )

# #     result = "🔑 <b>МОЇ ЧЕКИ</b>\n"

# #     for label, items in buckets.items():
# #         if not items:
# #             result += f"\n📅 <b>{label.capitalize()}:</b> немає\n"
# #             continue

# #         total = sum(ch["price"] for ch, _ in items)
# #         result += f"\n📅 <b>{label.capitalize()}</b> ({len(items)} шт · {total} грн):\n\n"

# #         for ch, dt in items:
# #             time_str = dt.astimezone(KYIV).strftime("%H:%M")
# #             result += (
# #                 f"┌ {ch['check_type']}\n"
# #                 f"├ 🔑 <code>{ch['code']}</code>\n"
# #                 f"└ 💰 {ch['price']} грн · ⏰ {time_str}\n\n"
# #             )

# #     return result


# # # ──────────────────────────────────────────────────────────────────────────
# # #  ІНЛАЙН-КЛАВІАТУРИ
# # # ──────────────────────────────────────────────────────────────────────────

# # def profile_keyboard() -> InlineKeyboardMarkup:
# #     return InlineKeyboardMarkup(inline_keyboard=[
# #         [InlineKeyboardButton(text="🔑 Показати мої чеки", callback_data="profile:checks")],
# #         # [InlineKeyboardButton(text="🔙 Назад до головного меню", callback_data="profile:main_menu")],
# #     ])


# # def checks_keyboard() -> InlineKeyboardMarkup:
# #     return InlineKeyboardMarkup(inline_keyboard=[
# #         [InlineKeyboardButton(text="⬅️ Назад до кабінету", callback_data="profile:back")],
# #         # [InlineKeyboardButton(text="🔙 Назад до головного меню", callback_data="profile:main_menu")],
# #     ])


# # # ──────────────────────────────────────────────────────────────────────────
# # #  ХЕНДЛЕРИ
# # # ──────────────────────────────────────────────────────────────────────────

# # @router.message(F.text == "👤 Мій кабінет")
# # async def show_profile(message: types.Message):
# #     user_id = message.from_user.id
# #     username = message.from_user.username or "—"
# #     full_name = message.from_user.full_name or "—"

# #     await add_or_update_user(user_id, username, full_name)
# #     user_data = await get_user_data(user_id)
# #     if not user_data:
# #         await message.answer("⚠️ Ваш профіль ще не створений. Спробуйте пізніше.")
# #         return

# #     balance = await get_balance(user_id)
# #     weekly_coupons = user_data.get("games_played", 0)

# #     all_checks = await get_issued_checks_for_user(user_id)
# #     today_sum = _today_sum(all_checks)

# #     profile_text = build_profile_text(user_id, username, full_name, balance, weekly_coupons)
# #     progress_text = build_progress_bars(today_sum)

# #     await message.answer(
# #         profile_text + progress_text,
# #         parse_mode="HTML",
# #         reply_markup=profile_keyboard(),
# #     )


# # @router.callback_query(F.data == "profile:checks")
# # async def cb_show_checks(callback: types.CallbackQuery):
# #     user_id = callback.from_user.id
# #     checks_text = await build_checks_list_text(user_id)

# #     await callback.message.edit_text(
# #         checks_text,
# #         parse_mode="HTML",
# #         reply_markup=checks_keyboard(),
# #     )
# #     await callback.answer()


# # @router.callback_query(F.data == "profile:back")
# # async def cb_back_to_profile(callback: types.CallbackQuery):
# #     user_id = callback.from_user.id
# #     username = callback.from_user.username or "—"
# #     full_name = callback.from_user.full_name or "—"

# #     user_data = await get_user_data(user_id)
# #     balance = await get_balance(user_id)
# #     weekly_coupons = user_data.get("games_played", 0) if user_data else 0

# #     all_checks = await get_issued_checks_for_user(user_id)
# #     today_sum = _today_sum(all_checks)

# #     profile_text = build_profile_text(user_id, username, full_name, balance, weekly_coupons)
# #     progress_text = build_progress_bars(today_sum)

# #     await callback.message.edit_text(
# #         profile_text + progress_text,
# #         parse_mode="HTML",
# #         reply_markup=profile_keyboard(),
# #     )
# #     await callback.answer()


# # @router.callback_query(F.data == "profile:main_menu")
# # async def cb_back_to_main_menu(callback: types.CallbackQuery):
# #     # Інлайн-повідомлення кабінету видаляємо, бо подальша навігація — через
# #     # звичайне (reply) меню. Якщо main_menu() приймає інші аргументи —
# #     # підправте виклик нижче.
# #     await callback.message.delete()
# #     await callback.message.answer(
# #         "🏠 Головне меню",
# #         reply_markup=main_menu(),
# #     )
# #     await callback.answer()


# # # ──────────────────────────────────────────────────────────────────────────
# # #  СПОВІЩЕННЯ ПРО ПРОГРЕС НАГОРОД (промокод / відкат)
# # #
# # #  ⚠️ notify_reward_progress(bot, user_id, username, full_name) потрібно
# # #  викликати ОДРАЗУ ПІСЛЯ db.log_check_issued(...) — там, де у вас видається
# # #  чек/код гравцю.
# # # ──────────────────────────────────────────────────────────────────────────

# # async def _ensure_table(db):
# #     await db.execute("""
# #         CREATE TABLE IF NOT EXISTS reward_progress (
# #             user_id INTEGER NOT NULL,
# #             reward_date TEXT NOT NULL,
# #             promo_tier INTEGER NOT NULL DEFAULT 0,
# #             cashback_tier INTEGER NOT NULL DEFAULT 0,
# #             PRIMARY KEY (user_id, reward_date)
# #         )
# #     """)


# # async def get_reward_tiers(user_id: int, reward_date: str) -> tuple[int, int]:
# #     async with aiosqlite.connect(DB_PATH) as db:
# #         await _ensure_table(db)
# #         cur = await db.execute(
# #             "SELECT promo_tier, cashback_tier FROM reward_progress "
# #             "WHERE user_id = ? AND reward_date = ?",
# #             (user_id, reward_date),
# #         )
# #         row = await cur.fetchone()
# #         return (row[0], row[1]) if row else (0, 0)


# # async def set_reward_tiers(user_id: int, reward_date: str, promo_tier: int, cashback_tier: int):
# #     async with aiosqlite.connect(DB_PATH) as db:
# #         await _ensure_table(db)
# #         await db.execute("""
# #             INSERT INTO reward_progress (user_id, reward_date, promo_tier, cashback_tier)
# #             VALUES (?, ?, ?, ?)
# #             ON CONFLICT(user_id, reward_date) DO UPDATE SET
# #                 promo_tier = excluded.promo_tier,
# #                 cashback_tier = excluded.cashback_tier
# #         """, (user_id, reward_date, promo_tier, cashback_tier))
# #         await db.commit()


# # async def notify_reward_progress(bot, user_id: int, username: str | None, full_name: str):
# #     all_checks = await get_issued_checks_for_user(user_id)
# #     today_sum = _today_sum(all_checks)
# #     today_str = datetime.now(KYIV).strftime("%Y-%m-%d")

# #     old_promo_tier, old_cashback_tier = await get_reward_tiers(user_id, today_str)
# #     new_promo_tier = today_sum // PROMO_GOAL
# #     new_cashback_tier = today_sum // CASHBACK_GOAL

# #     display_name = f"@{username}" if username else full_name

# #     if new_promo_tier > old_promo_tier:
# #         # Скільки лишилось грн до ще одного промокоду (новий прогрес-бар
# #         # одразу після отримання першого/будь-якого промокоду).
# #         next_goal_progress = today_sum % PROMO_GOAL
# #         remaining = PROMO_GOAL - next_goal_progress

# #         await bot.send_message(
# #             user_id,
# #             f"🎉 Вітаємо! Ви можете отримати промокод!\n",
# #             # f"Всього сьогодні: {new_promo_tier} промокод(ів).\n"
# #             # f"До наступного промокоду залишилось {remaining} грн.",
# #             parse_mode="HTML",
# #         )
# #         if ADMIN_ID:
# #             await bot.send_message(
# #                 ADMIN_ID,
# #                 f"🎟 {display_name} (id <code>{user_id}</code>) отримав промокод "
# #                 f"(всього сьогодні: {new_promo_tier}).",
# #                 parse_mode="HTML",
# #             )

# #     if new_cashback_tier > old_cashback_tier:
# #         gained = int((new_cashback_tier - old_cashback_tier) * CASHBACK_GOAL * CASHBACK_PERCENT)
# #         await add_to_balance(user_id, gained)

# #         next_goal_progress = today_sum % CASHBACK_GOAL
# #         remaining = CASHBACK_GOAL - next_goal_progress

# #         await bot.send_message(
# #             user_id,
# #             f"💸 Вітаємо! Вам доступно відкат <b>{gained} грн</b> "
# #             f"({int(CASHBACK_PERCENT * 100)}% з {CASHBACK_GOAL} грн).\n",
# #             # f"До наступного відкату залишилось {remaining} грн.",
# #             parse_mode="HTML",
# #         )
# #         if ADMIN_ID:
# #             await bot.send_message(
# #                 ADMIN_ID,
# #                 f"💸 {display_name} (id <code>{user_id}</code>) отримав відкат {gained} грн.",
# #                 parse_mode="HTML",
# #             )

# #     if new_promo_tier > old_promo_tier or new_cashback_tier > old_cashback_tier:
# #         await set_reward_tiers(user_id, today_str, new_promo_tier, new_cashback_tier)


# import logging
# from datetime import datetime, timezone, timedelta

# import aiosqlite
# from aiogram import Router, F, types
# from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# from db import (
#     get_user_data,
#     add_or_update_user,
#     has_claimed_gift,
#     get_issued_checks_for_user,
#     DB_PATH,
#     add_to_balance,
# )
# from db.wallet import get_balance
# from handlers.menu import main_menu
# from handlers.config import ADMIN_ID

# router = Router()
# logging.basicConfig(level=logging.INFO)

# KYIV = timezone(timedelta(hours=3))
# PROMO_GOAL = 500
# CASHBACK_GOAL = 1000
# CASHBACK_PERCENT = 0.10


# def _today_sum(all_checks: list[dict]) -> int:
#     today = datetime.now(KYIV).date()
#     total = 0
#     for ch in all_checks:
#         try:
#             dt = datetime.fromisoformat(ch["issued_at"])
#             if dt.tzinfo is None:
#                 dt = dt.replace(tzinfo=timezone.utc)
#             if dt.astimezone(KYIV).date() == today:
#                 total += ch["price"]
#         except Exception:
#             pass
#     return total


# # ──────────────────────────────────────────────────────────────────────────
# #  ПРОФІЛЬ КОРИСТУВАЧА
# # ──────────────────────────────────────────────────────────────────────────

# def build_balance_bar(balance: int) -> str:
#     levels = [
#         (5000, "👑"),
#         (2000, "💎"),
#         (1000, "🔥"),
#         (500,  "⚡️"),
#         (200,  "🌟"),
#         (0,    "🌱"),
#     ]
#     for threshold, icon in levels:
#         if balance >= threshold:
#             tier_icon = icon
#             break
#     else:
#         tier_icon = "🌱"

#     filled = min(int(balance / 200), 10)
#     bar = "█" * filled + "░" * (10 - filled)
#     return f"{tier_icon} [{bar}]"


# def build_profile_text(user_id, username, full_name, balance, weekly_coupons) -> str:
#     username_line = f"@{username}" if username != "—" else "без username"
#     balance_bar = build_balance_bar(balance)

#     if weekly_coupons == 0:
#         promo_icons = "😔"
#     else:
#         promo_icons = "🎟 " * min(weekly_coupons, 15)
#         if weekly_coupons > 15:
#             promo_icons += f"+{weekly_coupons - 15}"

#     return (
#         f"╔════════════╗\n"
#         f"║ 👤 <b>МІЙ КАБІНЕТ</b> \n"
#         f"╚════════════╝\n"
#         f"<b>{full_name}</b>\n"
#         f"🆔 <code>{user_id}</code>\n"
#         f"━━━━━━━━━━━━\n"
#         f"💰 <b>БАЛАНС</b> : {balance}\n"
#         f"━━━━━━━━━━━━\n\n"
#         f"<b>Зібрано PROMO :</b> <code>{weekly_coupons}</code>\n"
#         f"{promo_icons}\n"
#     )


# def build_progress_bars(today_sum: int) -> str:
#     """
#     Прогрес-бари на сьогодні. Якщо рівень вже досягнуто (наприклад, перший
#     промокод отримано), бар автоматично перемикається на прогрес до
#     НАСТУПНОГО рівня замість того, щоб просто показувати "✅" назавжди.
#     """

#     # ── Промокод ──
#     promo_tier = today_sum // PROMO_GOAL
#     promo_progress = today_sum % PROMO_GOAL
#     promo_blocks = int(promo_progress / PROMO_GOAL * 10)
#     promo_bar = "█" * promo_blocks + "░" * (10 - promo_blocks)

#     if promo_tier > 0:
#         promo_line = (
#             f"🎟 <b>Промокод</b> · отримано {promo_tier} шт ✅\n"
#             f"  Прогрес до наступного: [{promo_bar}] {promo_progress}/{PROMO_GOAL} грн\n"
#         )
#     else:
#         promo_line = (
#             f"🎟 <b>Промокод</b> · {PROMO_GOAL} грн\n"
#             f"  [{promo_bar}] {today_sum}/{PROMO_GOAL} грн\n"
#         )

#     # ── Відкат ──
#     cashback_tier = today_sum // CASHBACK_GOAL
#     cashback_progress = today_sum % CASHBACK_GOAL
#     cashback_blocks = int(cashback_progress / CASHBACK_GOAL * 10)
#     cashback_bar = "█" * cashback_blocks + "░" * (10 - cashback_blocks)

#     if cashback_tier > 0:
#         earned = int(cashback_tier * CASHBACK_GOAL * CASHBACK_PERCENT)
#         cashback_line = (
#             f"💸 <b>Відкат {int(CASHBACK_PERCENT * 100)}%</b> · нараховано {earned} грн ✅\n"
#             f"  Прогрес до наступного: [{cashback_bar}] {cashback_progress}/{CASHBACK_GOAL} грн\n"
#         )
#     else:
#         cashback_line = (
#             f"💸 <b>Відкат {int(CASHBACK_PERCENT * 100)}%</b> · {CASHBACK_GOAL} грн\n"
#             f"  [{cashback_bar}] {today_sum}/{CASHBACK_GOAL} грн\n"
#         )

#     return (
#         f"\n━━━━━━━━━━━━\n"
#         f"📊 <b>ПРОГРЕС СЬОГОДНІ</b>\n\n"
#         f"{promo_line}\n"
#         f"{cashback_line}"
#     )


# async def build_checks_list_text(user_id: int) -> str:
#     """Список чеків за сьогодні і вчора (без прогрес-барів — вони вже на головному екрані кабінету)."""
#     all_checks = await get_issued_checks_for_user(user_id)

#     now = datetime.now(KYIV)
#     today = now.date()
#     yesterday = (now - timedelta(days=1)).date()

#     buckets = {
#         "сьогодні": [],
#         "вчора": [],
#     }

#     for ch in all_checks:
#         try:
#             dt = datetime.fromisoformat(ch["issued_at"])
#             if dt.tzinfo is None:
#                 dt = dt.replace(tzinfo=timezone.utc)
#             d = dt.astimezone(KYIV).date()
#             if d == today:
#                 buckets["сьогодні"].append((ch, dt))
#             elif d == yesterday:
#                 buckets["вчора"].append((ch, dt))
#         except Exception:
#             pass

#     if not any(buckets.values()):
#         return (
#             f"🔑 <b>МОЇ ЧЕКИ</b>\n\n"
#             f"😔 За останні 2 дні чеків немає"
#         )

#     result = "🔑 <b>МОЇ ЧЕКИ</b>\n"

#     for label, items in buckets.items():
#         if not items:
#             result += f"\n📅 <b>{label.capitalize()}:</b> немає\n"
#             continue

#         total = sum(ch["price"] for ch, _ in items)
#         result += f"\n📅 <b>{label.capitalize()}</b> ({len(items)} шт · {total} грн):\n\n"

#         for ch, dt in items:
#             time_str = dt.astimezone(KYIV).strftime("%H:%M")
#             result += (
#                 f"┌ {ch['check_type']}\n"
#                 f"├ 🔑 <code>{ch['code']}</code>\n"
#                 f"└ 💰 {ch['price']} грн · ⏰ {time_str}\n\n"
#             )

#     return result


# # ──────────────────────────────────────────────────────────────────────────
# #  ІНЛАЙН-КЛАВІАТУРИ
# # ──────────────────────────────────────────────────────────────────────────

# def profile_keyboard() -> InlineKeyboardMarkup:
#     return InlineKeyboardMarkup(inline_keyboard=[
#         [InlineKeyboardButton(text="🔑 Показати мої чеки", callback_data="profile:checks")],
#         # [InlineKeyboardButton(text="🔙 Назад до головного меню", callback_data="profile:main_menu")],
#     ])


# def checks_keyboard() -> InlineKeyboardMarkup:
#     return InlineKeyboardMarkup(inline_keyboard=[
#         [InlineKeyboardButton(text="⬅️ Назад до кабінету", callback_data="profile:back")],
#         # [InlineKeyboardButton(text="🔙 Назад до головного меню", callback_data="profile:main_menu")],
#     ])


# # ──────────────────────────────────────────────────────────────────────────
# #  ХЕНДЛЕРИ
# # ──────────────────────────────────────────────────────────────────────────

# @router.message(F.text == "👤 Мій кабінет")
# async def show_profile(message: types.Message):
#     user_id = message.from_user.id
#     username = message.from_user.username or "—"
#     full_name = message.from_user.full_name or "—"

#     await add_or_update_user(user_id, username, full_name)
#     user_data = await get_user_data(user_id)
#     if not user_data:
#         await message.answer("⚠️ Ваш профіль ще не створений. Спробуйте пізніше.")
#         return

#     balance = await get_balance(user_id)
#     weekly_coupons = user_data.get("games_played", 0)

#     all_checks = await get_issued_checks_for_user(user_id)
#     today_sum = _today_sum(all_checks)

#     profile_text = build_profile_text(user_id, username, full_name, balance, weekly_coupons)
#     progress_text = build_progress_bars(today_sum)

#     await message.answer(
#         profile_text + progress_text,
#         parse_mode="HTML",
#         reply_markup=profile_keyboard(),
#     )


# @router.callback_query(F.data == "profile:checks")
# async def cb_show_checks(callback: types.CallbackQuery):
#     user_id = callback.from_user.id
#     checks_text = await build_checks_list_text(user_id)

#     await callback.message.edit_text(
#         checks_text,
#         parse_mode="HTML",
#         reply_markup=checks_keyboard(),
#     )
#     await callback.answer()


# @router.callback_query(F.data == "profile:back")
# async def cb_back_to_profile(callback: types.CallbackQuery):
#     user_id = callback.from_user.id
#     username = callback.from_user.username or "—"
#     full_name = callback.from_user.full_name or "—"

#     user_data = await get_user_data(user_id)
#     balance = await get_balance(user_id)
#     weekly_coupons = user_data.get("games_played", 0) if user_data else 0

#     all_checks = await get_issued_checks_for_user(user_id)
#     today_sum = _today_sum(all_checks)

#     profile_text = build_profile_text(user_id, username, full_name, balance, weekly_coupons)
#     progress_text = build_progress_bars(today_sum)

#     await callback.message.edit_text(
#         profile_text + progress_text,
#         parse_mode="HTML",
#         reply_markup=profile_keyboard(),
#     )
#     await callback.answer()


# @router.callback_query(F.data == "profile:main_menu")
# async def cb_back_to_main_menu(callback: types.CallbackQuery):
#     # Інлайн-повідомлення кабінету видаляємо, бо подальша навігація — через
#     # звичайне (reply) меню. Якщо main_menu() приймає інші аргументи —
#     # підправте виклик нижче.
#     await callback.message.delete()
#     await callback.message.answer(
#         "🏠 Головне меню",
#         reply_markup=main_menu(),
#     )
#     await callback.answer()


# # ──────────────────────────────────────────────────────────────────────────
# #  СПОВІЩЕННЯ ПРО ПРОГРЕС НАГОРОД (промокод / відкат)
# #
# #  ⚠️ notify_reward_progress(bot, user_id, username, full_name) потрібно
# #  викликати ОДРАЗУ ПІСЛЯ db.log_check_issued(...) — там, де у вас видається
# #  чек/код гравцю.
# # ──────────────────────────────────────────────────────────────────────────

# async def _ensure_table(db):
#     await db.execute("""
#         CREATE TABLE IF NOT EXISTS reward_progress (
#             user_id INTEGER NOT NULL,
#             reward_date TEXT NOT NULL,
#             promo_tier INTEGER NOT NULL DEFAULT 0,
#             cashback_tier INTEGER NOT NULL DEFAULT 0,
#             PRIMARY KEY (user_id, reward_date)
#         )
#     """)


# async def get_reward_tiers(user_id: int, reward_date: str) -> tuple[int, int]:
#     async with aiosqlite.connect(DB_PATH) as db:
#         await _ensure_table(db)
#         cur = await db.execute(
#             "SELECT promo_tier, cashback_tier FROM reward_progress "
#             "WHERE user_id = ? AND reward_date = ?",
#             (user_id, reward_date),
#         )
#         row = await cur.fetchone()
#         return (row[0], row[1]) if row else (0, 0)


# async def set_reward_tiers(user_id: int, reward_date: str, promo_tier: int, cashback_tier: int):
#     async with aiosqlite.connect(DB_PATH) as db:
#         await _ensure_table(db)
#         await db.execute("""
#             INSERT INTO reward_progress (user_id, reward_date, promo_tier, cashback_tier)
#             VALUES (?, ?, ?, ?)
#             ON CONFLICT(user_id, reward_date) DO UPDATE SET
#                 promo_tier = excluded.promo_tier,
#                 cashback_tier = excluded.cashback_tier
#         """, (user_id, reward_date, promo_tier, cashback_tier))
#         await db.commit()


# async def notify_reward_progress(bot, user_id: int, username: str | None, full_name: str):
#     all_checks = await get_issued_checks_for_user(user_id)
#     today_sum = _today_sum(all_checks)
#     today_str = datetime.now(KYIV).strftime("%Y-%m-%d")

#     old_promo_tier, old_cashback_tier = await get_reward_tiers(user_id, today_str)
#     new_promo_tier = today_sum // PROMO_GOAL
#     new_cashback_tier = today_sum // CASHBACK_GOAL

#     display_name = f"@{username}" if username else full_name

#     if new_promo_tier > old_promo_tier:
#         # Скільки лишилось грн до ще одного промокоду (новий прогрес-бар
#         # одразу після отримання першого/будь-якого промокоду).
#         next_goal_progress = today_sum % PROMO_GOAL
#         remaining = PROMO_GOAL - next_goal_progress

#         await bot.send_message(
#             user_id,
#             f"🎉 Вітаємо! Ви можете отримати промокод!\n",
#             # f"Всього сьогодні: {new_promo_tier} промокод(ів).\n"
#             # f"До наступного промокоду залишилось {remaining} грн.",
#             parse_mode="HTML",
#         )
#         if ADMIN_ID:
#             await bot.send_message(
#                 ADMIN_ID,
#                 f"🎟 {display_name} (id <code>{user_id}</code>) отримав промокод "
#                 f"(всього сьогодні: {new_promo_tier}).",
#                 parse_mode="HTML",
#             )

#     if new_cashback_tier > old_cashback_tier:
#         gained = int((new_cashback_tier - old_cashback_tier) * CASHBACK_GOAL * CASHBACK_PERCENT)
#         await add_to_balance(user_id, gained)

#         next_goal_progress = today_sum % CASHBACK_GOAL
#         remaining = CASHBACK_GOAL - next_goal_progress

#         await bot.send_message(
#             user_id,
#             f"💸 Вітаємо! Вам доступно відкат <b>{gained} грн</b> "
#             f"({int(CASHBACK_PERCENT * 100)}% з {CASHBACK_GOAL} грн).\n",
#             # f"До наступного відкату залишилось {remaining} грн.",
#             parse_mode="HTML",
#         )
#         if ADMIN_ID:
#             await bot.send_message(
#                 ADMIN_ID,
#                 f"💸 {display_name} (id <code>{user_id}</code>) отримав відкат {gained} грн.",
#                 parse_mode="HTML",
#             )

#     if new_promo_tier > old_promo_tier or new_cashback_tier > old_cashback_tier:
#         await set_reward_tiers(user_id, today_str, new_promo_tier, new_cashback_tier)


import logging
from datetime import datetime, timezone, timedelta

import aiosqlite
from aiogram import Router, F, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from db import (
    get_user_data,
    add_or_update_user,
    DB_PATH,
    add_to_balance,
    get_issued_checks_for_user,
    
)
from db.wallet import get_balance
from handlers.menu import main_menu
from handlers.config import ADMIN_ID

router = Router()
logging.basicConfig(level=logging.INFO)

KYIV = timezone(timedelta(hours=3))
PROMO_GOAL = 500
CASHBACK_GOAL = 1000
CASHBACK_PERCENT = 0.10


def _today_sum(all_checks: list[dict]) -> int:
    today = datetime.now(KYIV).date()
    total = 0
    for ch in all_checks:
        try:
            dt = datetime.fromisoformat(ch["issued_at"])
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            if dt.astimezone(KYIV).date() == today:
                total += ch["price"]
        except Exception:
            pass
    return total


# ──────────────────────────────────────────────────────────────────────────
#  ПРОФІЛЬ КОРИСТУВАЧА
# ──────────────────────────────────────────────────────────────────────────

def build_balance_bar(balance: int) -> str:
    levels = [
        (5000, "👑"),
        (2000, "💎"),
        (1000, "🔥"),
        (500,  "⚡️"),
        (200,  "🌟"),
        (0,    "🌱"),
    ]
    for threshold, icon in levels:
        if balance >= threshold:
            tier_icon = icon
            break
    else:
        tier_icon = "🌱"

    filled = min(int(balance / 200), 10)
    bar = "█" * filled + "░" * (10 - filled)
    return f"{tier_icon} [{bar}"


def build_profile_text(user_id, username, full_name, balance, weekly_coupons) -> str:
    username_line = f"@{username}" if username != "—" else "без username"
    balance_bar = build_balance_bar(balance)

    if weekly_coupons == 0:
        promo_icons = "😔"
    else:
        promo_icons = "🎟 " * min(weekly_coupons, 15)
        if weekly_coupons > 15:
            promo_icons += f"+{weekly_coupons - 15}"

    return (
        f"╔════════════╗\n"
        f"║ 👤 <b>МІЙ КАБІНЕТ</b> \n"
        f"╚════════════╝\n"
        f"<b>{full_name}</b>\n"
        f"🆔 <code>{user_id}</code>\n"
        f"━━━━━━━━━━━━\n"
        f"💰 <b>БАЛАНС</b> : {balance}\n"
        f"━━━━━━━━━━━━\n\n"
        f"<b>Зібрано PROMO :</b> <code>{weekly_coupons}</code>\n"
        f"{promo_icons}\n"
    )


# ──────────────────────────────────────────────────────────────────────────
#  ПРОГРЕС СЬОГОДНІ (закоментовано)
# ──────────────────────────────────────────────────────────────────────────

# def build_progress_bars(today_sum: int) -> str:
#     """
#     Прогрес-бари на сьогодні.
#     """
#     # ── Промокод ──
#     promo_tier = today_sum // PROMO_GOAL
#     promo_progress = today_sum % PROMO_GOAL
#     promo_blocks = int(promo_progress / PROMO_GOAL * 10)
#     promo_bar = "█" * promo_blocks + "░" * (10 - promo_blocks)
#
#     if promo_tier > 0:
#         promo_line = (
#             f"🎟 <b>Промокод</b> · отримано {promo_tier} шт ✅\n"
#             f"  Прогрес до наступного: [{promo_bar}] {promo_progress}/{PROMO_GOAL} грн\n"
#         )
#     else:
#         promo_line = (
#             f"🎟 <b>Промокод</b> · {PROMO_GOAL} грн\n"
#             f"  [{promo_bar}] {today_sum}/{PROMO_GOAL} грн\n"
#         )
#
#     # ── Відкат ──
#     cashback_tier = today_sum // CASHBACK_GOAL
#     cashback_progress = today_sum % CASHBACK_GOAL
#     cashback_blocks = int(cashback_progress / CASHBACK_GOAL * 10)
#     cashback_bar = "█" * cashback_blocks + "░" * (10 - cashback_blocks)
#
#     if cashback_tier > 0:
#         earned = int(cashback_tier * CASHBACK_GOAL * CASHBACK_PERCENT)
#         cashback_line = (
#             f"💸 <b>Відкат {int(CASHBACK_PERCENT * 100)}%</b> · нараховано {earned} грн ✅\n"
#             f"  Прогрес до наступного: [{cashback_bar}] {cashback_progress}/{CASHBACK_GOAL} грн\n"
#         )
#     else:
#         cashback_line = (
#             f"💸 <b>Відкат {int(CASHBACK_PERCENT * 100)}%</b> · {CASHBACK_GOAL} грн\n"
#             f"  [{cashback_bar}] {today_sum}/{CASHBACK_GOAL} грн\n"
#         )
#
#     return (
#         f"\n━━━━━━━━━━━━\n"
#         f"📊 <b>ПРОГРЕС СЬОГОДНІ</b>\n\n"
#         f"{promo_line}\n"
#         f"{cashback_line}"
#     )


# ──────────────────────────────────────────────────────────────────────────
#  ІНЛАЙН-КЛАВІАТУРИ
# ──────────────────────────────────────────────────────────────────────────

def profile_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        # [InlineKeyboardButton(text="🔙 Назад до головного меню", callback_data="profile:main_menu")],
    ])


# ──────────────────────────────────────────────────────────────────────────
#  ХЕНДЛЕРИ
# ──────────────────────────────────────────────────────────────────────────

@router.message(F.text == "👤 Мій кабінет")
async def show_profile(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or "—"
    full_name = message.from_user.full_name or "—"

    await add_or_update_user(user_id, username, full_name)
    user_data = await get_user_data(user_id)
    if not user_data:
        await message.answer("⚠️ Ваш профіль ще не створений. Спробуйте пізніше.")
        return

    balance = await get_balance(user_id)
    weekly_coupons = user_data.get("games_played", 0)

    all_checks = await get_issued_checks_for_user(user_id)
    today_sum = _today_sum(all_checks)

    profile_text = build_profile_text(user_id, username, full_name, balance, weekly_coupons)
    
    # Прогрес-бары тимчасово вимкнено
    # progress_text = build_progress_bars(today_sum)
    progress_text = ""

    await message.answer(
        profile_text + progress_text,
        parse_mode="HTML",
        reply_markup=profile_keyboard(),
    )


@router.callback_query(F.data == "profile:main_menu")
async def cb_back_to_main_menu(callback: types.CallbackQuery):
    await callback.message.delete()
    await callback.message.answer(
        "🏠 Головне меню",
        reply_markup=main_menu(),
    )
    await callback.answer()


# ──────────────────────────────────────────────────────────────────────────
#  СПОВІЩЕННЯ ПРО ПРОГРЕС НАГОРОД (промокод / відкат)
# ──────────────────────────────────────────────────────────────────────────

async def _ensure_table(db):
    await db.execute("""
        CREATE TABLE IF NOT EXISTS reward_progress (
            user_id INTEGER NOT NULL,
            reward_date TEXT NOT NULL,
            promo_tier INTEGER NOT NULL DEFAULT 0,
            cashback_tier INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (user_id, reward_date)
        )
    """)


async def get_reward_tiers(user_id: int, reward_date: str) -> tuple[int, int]:
    async with aiosqlite.connect(DB_PATH) as db:
        await _ensure_table(db)
        cur = await db.execute(
            "SELECT promo_tier, cashback_tier FROM reward_progress "
            "WHERE user_id = ? AND reward_date = ?",
            (user_id, reward_date),
        )
        row = await cur.fetchone()
        return (row[0], row[1]) if row else (0, 0)


async def set_reward_tiers(user_id: int, reward_date: str, promo_tier: int, cashback_tier: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await _ensure_table(db)
        await db.execute("""
            INSERT INTO reward_progress (user_id, reward_date, promo_tier, cashback_tier)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id, reward_date) DO UPDATE SET
                promo_tier = excluded.promo_tier,
                cashback_tier = excluded.cashback_tier
        """, (user_id, reward_date, promo_tier, cashback_tier))
        await db.commit()


async def notify_reward_progress(bot, user_id: int, username: str | None, full_name: str):
    all_checks = await get_issued_checks_for_user(user_id)
    today_sum = _today_sum(all_checks)
    today_str = datetime.now(KYIV).strftime("%Y-%m-%d")

    old_promo_tier, old_cashback_tier = await get_reward_tiers(user_id, today_str)
    new_promo_tier = today_sum // PROMO_GOAL
    new_cashback_tier = today_sum // CASHBACK_GOAL

    display_name = f"@{username}" if username else full_name

    if new_promo_tier > old_promo_tier:
        await bot.send_message(
            user_id,
            f"🎉 Вітаємо! Ви можете отримати промокод!\n",
            parse_mode="HTML",
        )
        if ADMIN_ID:
            await bot.send_message(
                ADMIN_ID,
                f"🎟 {display_name} (id <code>{user_id}</code>) отримав промокод "
                f"(всього сьогодні: {new_promo_tier}).",
                parse_mode="HTML",
            )

    if new_cashback_tier > old_cashback_tier:
        gained = int((new_cashback_tier - old_cashback_tier) * CASHBACK_GOAL * CASHBACK_PERCENT)
        await add_to_balance(user_id, gained)

        await bot.send_message(
            user_id,
            f"💸 Вітаємо! Вам доступно відкат <b>{gained} грн</b> "
            f"({int(CASHBACK_PERCENT * 100)}% з {CASHBACK_GOAL} грн).\n",
            parse_mode="HTML",
        )
        if ADMIN_ID:
            await bot.send_message(
                ADMIN_ID,
                f"💸 {display_name} (id <code>{user_id}</code>) отримав відкат {gained} грн.",
                parse_mode="HTML",
            )

    if new_promo_tier > old_promo_tier or new_cashback_tier > old_cashback_tier:
        await set_reward_tiers(user_id, today_str, new_promo_tier, new_cashback_tier)