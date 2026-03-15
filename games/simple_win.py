
import asyncio
import random
from aiogram import Router, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from handlers.config import ADMIN_ID  # Імпортуємо ADMIN_ID з конфігу
from db import (
    spend_promo_for_fortune,  # Адаптуємо або створюємо нову функцію для списання промо
    get_promo,  # Функція для отримання кількості промо
    add_money_win,  # Функція для додавання виграшу
    save_notification,  # Функція для збереження сповіщення
    ensure_users_table_and_columns,  # Ініціалізація таблиці, якщо потрібно
)

router = Router(name="simple_win_router")
WIN_COST = 7
PRIZE_VALUE = 100


def simple_win_keyboard(current_promo: int = 0) -> InlineKeyboardMarkup:
    status = f"{min(current_promo, WIN_COST)}/{WIN_COST}"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"💰 Отримати 100 грн ({status} 🎟️)",
                    callback_data="simple_win:claim",
                )
            ],
            [
                InlineKeyboardButton(
                    text="📖 Як отримати 🎟️ PROMO?",
                    callback_data="simple_win:info",
                )
            ],
        ]
    )


@router.message(F.text.in_("💰 Бездепиш 100"))
async def simple_win_start(message: Message):
    await ensure_users_table_and_columns()
    promo = await get_promo(message.from_user.id)

    await message.answer(
        f"💰 <b>Швидкий Бездеп</b>\n\n"
        f"🔹 У тебе <b>🎟️</b>: <code>{promo}</code> шт.\n"
        f"🔹 Один раз коштує <b>{WIN_COST} 🎟️</b>\n\n"
        f"🔹 Отримай гарантовані 100 грн якщо у вас був депозит протягом тижня! 💵",
        reply_markup=simple_win_keyboard(promo),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "simple_win:claim")
async def simple_win_claim(cb: CallbackQuery):
    user_id = cb.from_user.id

    if not await spend_promo_for_fortune(user_id, WIN_COST):  # Адаптуємо функцію, або створіть нову якщо потрібно
        current = await get_promo(user_id)
        await cb.answer(
            f"❌ Недостатньо 🎟️ PROMO!\nУ тебе: {current} шт.\nПотрібно: {WIN_COST} шт.",
            show_alert=True,
        )
        return

    await cb.answer("💵 Обробляємо ваш виграш...")
    await perform_simple_win(cb)


# ====================== ПРОСТИЙ ВИГРАШ + СПОВІЩЕННЯ АДМІНУ ======================
async def perform_simple_win(cb: CallbackQuery):
    # === ЗБЕРЕЖЕННЯ ВИГРАШУ ===
    user_id = cb.from_user.id
    username = cb.from_user.username or "-"
    full_name = cb.from_user.full_name or "Unknown"

    await add_money_win(user_id, PRIZE_VALUE)
    await save_notification(
        user_id,
        username,
        full_name,
        "simple_win",
        f"Швидкий виграш: +{PRIZE_VALUE} грн",
    )

    # === СПОВІЩЕННЯ АДМІНУ ===
    admin_text = (
        f"💰 <b>БЕЗДЕПИШ!</b>\n\n"
        f"👤 Гравець: <b>{full_name}</b> (@{username})\n"
        f"💵 Сума: <b>+{PRIZE_VALUE} грн</b>"
    )
    try:
        await cb.bot.send_message(ADMIN_ID, admin_text, parse_mode="HTML")
    except:
        pass  # якщо адмін заблокував бота — не падаємо

    # === РЕЗУЛЬТАТ ГРАВЦЮ ===
    new_promo = await get_promo(user_id)

    result_text = (
        f"🎉 <b>ВИ ОТРИМАЛИ 100 грн!</b>\n\n"
        f"💵 <b>Ваш виграш буде видано касиром одразу на код</b>\n\n"
        f"❌ <b>Якщо протягом цього тижня ви не грали то виграш буде нарахований до депозиту</b>\n\n"
    )

    await cb.message.answer(
        result_text, reply_markup=simple_win_keyboard(new_promo), parse_mode="HTML"
    )


@router.callback_query(F.data == "simple_win:info")
async def show_promo_info(cb: CallbackQuery):
    await cb.answer()
    promo = await get_promo(cb.from_user.id)
    info_text = (
        f"📖 <b>Як отримати 🎟️ PROMO?</b>\n\n"
        f"1. Грайте в групові ігри (⚽, 🏀, 🎳) — вигравайте PROMO за перемоги!\n\n"
        f"2. Отримуйте 🎟️ PROMO за кожні 500 грн депозиту протягом дня.\n\n"
        f"У тебе зараз: <code>{promo}</code> 🎟️ PROMO"
    )
    back_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="← Назад",
                    callback_data="simple_win:back",
                )
            ],
        ]
    )
    await cb.message.edit_text(
        info_text, reply_markup=back_kb, parse_mode="HTML"
    )


@router.callback_query(F.data == "simple_win:back")
async def back_to_simple_win(cb: CallbackQuery):
    await cb.answer()
    promo = await get_promo(cb.from_user.id)
    await cb.message.edit_text(
        f"💰 <b>Швидкий Бездеп</b>\n\n"
        f"У тебе <b>PROMO</b>: <code>{promo}</code> шт.\n"
        f"Один раз коштує <b>{WIN_COST}🎟️ PROMO</b>\n\n"
        f"Отримай гарантовані 100 грн якщо у вас був депозит протягом тижня! 💵",
        reply_markup=simple_win_keyboard(promo),
        parse_mode="HTML",
    )