

# import asyncio
# import random
# from aiogram import Router, F
# from aiogram.types import (
#     Message,
#     CallbackQuery,
#     InlineKeyboardMarkup,
#     InlineKeyboardButton,
# )

# from handlers.config import ADMIN_ID
# from db import (
#     spend_promo_for_fortune,
#     get_promo,
#     add_money_win,
#     save_notification,
#     ensure_users_table_and_columns,
#     add_daily_game_win,
# )
# from db.wallet import add_to_balance, get_balance, get_daily_net, get_yesterday_net
# from db import can_receive_prize   # ← правильний імпорт

# router = Router(name="fortune")
# FORTUNE_COST = 4

# # ====================== ПРИЗИ ======================
# PRIZES = [
#     {"title": "30 грн", "value": 30, "emoji": "💵"},
#     {"title": "50 грн", "value": 50, "emoji": "💵"},
#     {"title": "60 грн", "value": 60, "emoji": "💵"},
#     {"title": "100 грн", "value": 100, "emoji": "💵"},
#     {"title": "500 грн", "value": 500, "emoji": "🏆"},
# ]

# WEIGHTS = [40, 32, 20, 8, 0]


# def _positive_or_zero(value: int) -> int:
#     """Якщо значення за день мінусове — ігноруємо його (повертаємо 0)"""
#     return value if value > 0 else 0


# def fortune_keyboard(current_promo: int = 0) -> InlineKeyboardMarkup:
#     status = f"{min(current_promo, FORTUNE_COST)}/{FORTUNE_COST}"
#     return InlineKeyboardMarkup(
#         inline_keyboard=[
#             [
#                 InlineKeyboardButton(
#                     text=f"🎡 Крутити колесо ({status} 🎟️)",
#                     callback_data="fortune:spin",
#                 )
#             ],
#             [
#                 InlineKeyboardButton(
#                     text="📋 Список призів", callback_data="fortune:prizes"
#                 )
#             ],
#             [
#                 InlineKeyboardButton(
#                     text="📖 Як отримати PROMO?",
#                     callback_data="fortune:info",
#                 )
#             ],
#         ]
#     )


# @router.message(F.text.in_("🎡 Колесо фортуни"))
# async def fortune_start(message: Message):
#     await ensure_users_table_and_columns()
#     promo = await get_promo(message.from_user.id)

#     await message.answer(
#         f"🎡 <b>Колесо Фортуни</b>\n\n"
#         f"🔹 У тебе <b>🎟️ PROMO</b>: <code>{promo}</code>\n"
#         f"🔹 Один оберт коштує <b>{FORTUNE_COST} 🎟️</b>\n\n"
#         f"❗ Для запуску колеса потрібно мати депозит (сьогодні або вчора).\n",

#         reply_markup=fortune_keyboard(promo),
#         parse_mode="HTML",
#     )


# @router.callback_query(F.data == "fortune:prizes")
# async def show_prizes(cb: CallbackQuery):
#     await cb.answer()
#     promo = await get_promo(cb.from_user.id)
#     text = "🎁 <b>Можливі призи:</b>\n\n"
#     for p in PRIZES:
#         text += f"{p['emoji']} {p['title']}\n"
#     await cb.message.edit_text(
#         text, reply_markup=fortune_keyboard(promo), parse_mode="HTML"
#     )


# @router.callback_query(F.data == "fortune:spin")
# async def fortune_spin(cb: CallbackQuery):
#     user_id = cb.from_user.id

#     # === Перевірка депозиту сьогодні + вчора (мінусові дні ігноруються) ===
#     today_net = await get_daily_net(user_id)
#     yesterday_net = await get_yesterday_net(user_id)
#     total_net = _positive_or_zero(today_net) + _positive_or_zero(yesterday_net)

#     if total_net < 200:
#         await cb.answer(
#             "❌ Не було депозиту!\n\n",
#             # f"(сьогодні: {today_net} грн | вчора: {yesterday_net} грн)",
#             show_alert=True,
#         )
#         return

#     # === Перевірка ліміту виграшу ===
#     allowed, msg = await can_receive_prize(user_id, prize_amount=30)
#     if not allowed:
#         await cb.answer(msg, show_alert=True)
#         return

#     # === Витрата PROMO ===
#     if not await spend_promo_for_fortune(user_id, FORTUNE_COST):
#         current = await get_promo(user_id)
#         await cb.answer(
#             f"❌ Недостатньо PROMO!\nУ тебе: {current} шт.\nПотрібно: {FORTUNE_COST} шт.",
#             show_alert=True,
#         )
#         return

#     await cb.answer("💵 Запускаємо колесо...")
#     await perform_fortune_spin(cb)


# # ====================== ОСНОВНА ЛОГІКА СПІНУ ======================
# async def perform_fortune_spin(cb: CallbackQuery):
#     load_msg = await cb.message.edit_text("💵 Запускаємо колесо...")

#     async def dollar_anim():
#         for _ in range(3):
#             for n in range(11):
#                 bar = "💵" * n + "▫️" * (10 - n)
#                 try:
#                     await load_msg.edit_text(f"💵 Запускаємо колесо...\n{bar}")
#                 except:
#                     return
#                 await asyncio.sleep(0.22)
#         try:
#             await load_msg.edit_text("💵 Запускаємо колесо...\n💵💵💵💵💵💵💵💵💵💵")
#         except:
#             pass

#     anim_task = asyncio.create_task(dollar_anim())

#     prize = random.choices(PRIZES, weights=WEIGHTS, k=1)[0]
#     prize_value = prize["value"]

#     await asyncio.sleep(3.0)
#     anim_task.cancel()
#     try:
#         await load_msg.delete()
#     except:
#         pass

#     user_id = cb.from_user.id
#     username = cb.from_user.username or "-"
#     full_name = cb.from_user.full_name or "Unknown"

#     # === Фінальна перевірка перед видачею ===
#     allowed, _ = await can_receive_prize(user_id, prize_value)

#     if allowed:
#         await add_to_balance(user_id, prize_value)
#         payout_text = f"<b>+{prize_value} грн</b> нараховано на баланс 💸"
#         admin_status = "на баланс"
#     else:
#         payout_text = f"💸 Виграш <b>{prize_value} грн</b> буде зарахований до депозиту"
#         admin_status = "до депозиту"

#     await add_money_win(user_id, prize_value)
#     await add_daily_game_win(user_id, prize_value)

#     await save_notification(
#         user_id,
#         username,
#         full_name,
#         "fortune",
#         f"Колесо фортуни: +{prize_value} грн ({prize['title']}) {admin_status}",
#     )

#     # Сповіщення адміну
#     admin_text = (
#         f"🎡 <b>НОВИЙ ВИГРАШ У ФОРТУНІ!</b>\n\n"
#         f"👤 Гравець: <b>{full_name}</b> (@{username})\n"
#         f"💵 Сума: <b>+{prize_value} грн</b> | {admin_status}"
#     )
#     try:
#         await cb.bot.send_message(ADMIN_ID, admin_text, parse_mode="HTML")
#     except:
#         pass

#     new_promo = await get_promo(user_id)
#     balance = await get_balance(user_id)

#     result_text = (
#         f"🎉 <b>КОЛЕСО ЗУПИНИЛОСЬ!</b>\n\n"
#         f"{prize['emoji']} <b>Ви виграли {prize['title']}</b>!\n\n"
#         f"{payout_text}"
#     )

#     if allowed:
#         result_text += f"\n💳 Баланс: <b>{balance} грн</b>"

#     await cb.message.answer(
#         result_text, reply_markup=fortune_keyboard(new_promo), parse_mode="HTML"
#     )


# @router.callback_query(F.data == "fortune:info")
# async def show_promo_info(cb: CallbackQuery):
#     await cb.answer()
#     promo = await get_promo(cb.from_user.id)
#     info_text = (
#         f"📖 <b>Як отримати 🎟️ PROMO?</b>\n\n"
#         f"1. Грайте в групові ігри (⚽, 🏀, 🎳) — вигравайте PROMO за перемоги!\n\n"
#         f"2. Отримуйте 🎟️ PROMO за кожні 500 грн депозиту протягом дня.\n\n"
#         f"<b>Правила виплат:</b>\n"
#         f"❗ Для запуску колеса — мінімум 200 грн за останні 48 годин.\n"
#         f"❗ Максимум 80 грн виграшу на кожні 200 грн депозиту.\n"
#         f"   Якщо приз більший за ліміт — йде до депозиту.\n\n"
#         f"У тебе зараз: <code>{promo}</code> 🎟️ PROMO"
#     )
#     back_kb = InlineKeyboardMarkup(
#         inline_keyboard=[
#             [InlineKeyboardButton(text="← Назад", callback_data="fortune:back")]
#         ]
#     )
#     await cb.message.edit_text(
#         info_text, reply_markup=back_kb, parse_mode="HTML"
#     )


# @router.callback_query(F.data == "fortune:back")
# async def back_to_fortune(cb: CallbackQuery):
#     await cb.answer()
#     promo = await get_promo(cb.from_user.id)
#     await cb.message.edit_text(
#         f"🎡 <b>Колесо Фортуни</b>\n\n"
#         f"У тебе <b>PROMO</b>: <code>{promo}</code> шт.\n"
#         f"Один оберт коштує <b>{FORTUNE_COST} PROMO</b>\n\n"
#         f"Крути і вигравай реальні гроші! 💰",
#         reply_markup=fortune_keyboard(promo),
#         parse_mode="HTML",
#     )

import asyncio
import random
from aiogram import Router, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from handlers.config import ADMIN_ID
from db import (
    spend_promo_for_fortune,
    get_promo,
    add_money_win,
    save_notification,
    ensure_users_table_and_columns,
    add_daily_game_win,
)
from db.wallet import add_to_balance, get_balance, get_daily_net, get_yesterday_net
from db import can_receive_prize   # ← правильний імпорт

router = Router(name="fortune")
FORTUNE_COST = 4

# ====================== ПРИЗИ ======================
PRIZES = [
    {"title": "30 грн", "value": 30, "emoji": "💵"},
    {"title": "50 грн", "value": 50, "emoji": "💵"},
    {"title": "60 грн", "value": 60, "emoji": "💵"},
    {"title": "100 грн", "value": 100, "emoji": "💵"},
    {"title": "500 грн", "value": 500, "emoji": "🏆"},
]

WEIGHTS = [40, 32, 20, 8, 0]


def _positive_or_zero(value: int) -> int:
    """Якщо значення за день мінусове — ігноруємо його (повертаємо 0)"""
    return value if value > 0 else 0


def fortune_keyboard(current_promo: int = 0) -> InlineKeyboardMarkup:
    status = f"{min(current_promo, FORTUNE_COST)}/{FORTUNE_COST}"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"🎡 Крутити колесо ({status} 🎟️)",
                    callback_data="fortune:spin",
                )
            ],
            [
                InlineKeyboardButton(
                    text="📋 Список призів", callback_data="fortune:prizes"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📖 Як отримати PROMO?",
                    callback_data="fortune:info",
                )
            ],
        ]
    )


@router.message(F.text.in_("🎡 Колесо фортуни"))
async def fortune_start(message: Message):
    await ensure_users_table_and_columns()
    promo = await get_promo(message.from_user.id)

    await message.answer(
        f"🎡 <b>Колесо Фортуни</b>\n\n"
        f"🔹 У тебе <b>🎟️ PROMO</b>: <code>{promo}</code>\n"
        f"🔹 Один оберт коштує <b>{FORTUNE_COST} 🎟️</b>\n\n"
        f"❗ Для запуску колеса потрібно мати депозит (сьогодні або вчора).\n",
        reply_markup=fortune_keyboard(promo),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "fortune:prizes")
async def show_prizes(cb: CallbackQuery):
    await cb.answer()
    promo = await get_promo(cb.from_user.id)
    text = "🎁 <b>Можливі призи:</b>\n\n"
    for p in PRIZES:
        text += f"{p['emoji']} {p['title']}\n"
    await cb.message.edit_text(
        text, reply_markup=fortune_keyboard(promo), parse_mode="HTML"
    )


@router.callback_query(F.data == "fortune:spin")
async def fortune_spin(cb: CallbackQuery):
    user_id = cb.from_user.id

    # === Перевірка депозиту сьогодні + вчора (мінусові дні ігноруються) ===
    today_net = await get_daily_net(user_id)
    yesterday_net = await get_yesterday_net(user_id)
    total_net = _positive_or_zero(today_net) + _positive_or_zero(yesterday_net)

    if total_net < 200:
        await cb.answer(
            "❌ Не було депозиту!\n\n",
            show_alert=True,
        )
        return

    # === Перевірка ліміту виграшу ===
    allowed, msg = await can_receive_prize(user_id, prize_amount=30)
    if not allowed:
        await cb.answer(msg, show_alert=True)
        return

    # === Витрата PROMO ===
    if not await spend_promo_for_fortune(user_id, FORTUNE_COST):
        current = await get_promo(user_id)
        await cb.answer(
            f"❌ Недостатньо PROMO!\nУ тебе: {current} шт.\nПотрібно: {FORTUNE_COST} шт.",
            show_alert=True,
        )
        return

    await cb.answer("💵 Запускаємо колесо...")
    await perform_fortune_spin(cb)


# ====================== ОСНОВНА ЛОГІКА СПІНУ ======================
async def perform_fortune_spin(cb: CallbackQuery):
    load_msg = await cb.message.edit_text("💵 Запускаємо колесо...")

    async def dollar_anim():
        for _ in range(3):
            for n in range(11):
                bar = "💵" * n + "▫️" * (10 - n)
                try:
                    await load_msg.edit_text(f"💵 Запускаємо колесо...\n{bar}")
                except:
                    return
                await asyncio.sleep(0.22)
        try:
            await load_msg.edit_text("💵 Запускаємо колесо...\n💵💵💵💵💵💵💵💵💵💵")
        except:
            pass

    anim_task = asyncio.create_task(dollar_anim())

    prize = random.choices(PRIZES, weights=WEIGHTS, k=1)[0]
    prize_value = prize["value"]

    await asyncio.sleep(3.0)
    anim_task.cancel()
    try:
        await load_msg.delete()
    except:
        pass

    user_id = cb.from_user.id
    username = cb.from_user.username or "-"
    full_name = cb.from_user.full_name or "Unknown"

    # === Фінальна перевірка перед видачею ===
    allowed, _ = await can_receive_prize(user_id, prize_value)

    if allowed:
        # Виграш дозволений — нараховуємо на баланс і рахуємо як ігровий виграш
        await add_to_balance(user_id, prize_value)
        await add_daily_game_win(user_id, prize_value)
        payout_text = f"<b>+{prize_value} грн</b> нараховано на баланс 💸"
        admin_status = "на баланс"
    else:
        # Ліміт вичерпано — приз йде до депозиту,
        # тому НЕ рахуємо його як виграш у іграх
        payout_text = f"💸 Виграш <b>{prize_value} грн</b> буде зарахований до депозиту"
        admin_status = "до депозиту"

    await add_money_win(user_id, prize_value)

    await save_notification(
        user_id,
        username,
        full_name,
        "fortune",
        f"Колесо фортуни: +{prize_value} грн ({prize['title']}) {admin_status}",
    )

    # Сповіщення адміну
    admin_text = (
        f"🎡 <b>НОВИЙ ВИГРАШ У ФОРТУНІ!</b>\n\n"
        f"👤 Гравець: <b>{full_name}</b> (@{username})\n"
        f"💵 Сума: <b>+{prize_value} грн</b> | {admin_status}"
    )
    try:
        await cb.bot.send_message(ADMIN_ID, admin_text, parse_mode="HTML")
    except:
        pass

    new_promo = await get_promo(user_id)
    balance = await get_balance(user_id)

    result_text = (
        f"🎉 <b>КОЛЕСО ЗУПИНИЛОСЬ!</b>\n\n"
        f"{prize['emoji']} <b>Ви виграли {prize['title']}</b>!\n\n"
        f"{payout_text}"
    )

    if allowed:
        result_text += f"\n💳 Баланс: <b>{balance} грн</b>"

    await cb.message.answer(
        result_text, reply_markup=fortune_keyboard(new_promo), parse_mode="HTML"
    )


@router.callback_query(F.data == "fortune:info")
async def show_promo_info(cb: CallbackQuery):
    await cb.answer()
    promo = await get_promo(cb.from_user.id)
    info_text = (
        f"📖 <b>Як отримати 🎟️ PROMO?</b>\n\n"
        f"1. Грайте в групові ігри (⚽, 🏀, 🎳) — вигравайте PROMO за перемоги!\n\n"
        f"2. Отримуйте 🎟️ PROMO за кожні 500 грн депозиту протягом дня.\n\n"
        f"<b>Правила виплат:</b>\n"
        f"❗ Для запуску колеса — мінімум 200 грн за останні 48 годин.\n"
        f"❗ Максимум 80 грн виграшу на кожні 200 грн депозиту.\n"
        f"   Якщо приз більший за ліміт — йде до депозиту.\n\n"
        f"У тебе зараз: <code>{promo}</code> 🎟️ PROMO"
    )
    back_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="← Назад", callback_data="fortune:back")]
        ]
    )
    await cb.message.edit_text(
        info_text, reply_markup=back_kb, parse_mode="HTML"
    )


@router.callback_query(F.data == "fortune:back")
async def back_to_fortune(cb: CallbackQuery):
    await cb.answer()
    promo = await get_promo(cb.from_user.id)
    await cb.message.edit_text(
        f"🎡 <b>Колесо Фортуни</b>\n\n"
        f"У тебе <b>PROMO</b>: <code>{promo}</code> шт.\n"
        f"Один оберт коштує <b>{FORTUNE_COST} PROMO</b>\n\n"
        f"Крути і вигравай реальні гроші! 💰",
        reply_markup=fortune_keyboard(promo),
        parse_mode="HTML",
    )