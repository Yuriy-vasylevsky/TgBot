import asyncio
import random
from aiogram import Router, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from handlers.config import FORTUNE_COST, ADMIN_ID  # ← додали ADMIN_ID
from db import (
    spend_promo_for_fortune,
    get_promo,
    add_money_win,
    save_notification,
    ensure_users_table_and_columns,
)

router = Router(name="fortune")

# ====================== ПРИЗИ ======================
PRIZES = [
    {"title": "30 грн", "value": 30, "emoji": "💵"},
    {"title": "50 грн", "value": 50, "emoji": "💵"},
    {"title": "60 грн", "value": 60, "emoji": "💵"},
    {"title": "100 грн", "value": 100, "emoji": "💵"},
    {"title": "500 грн", "value": 500, "emoji": "🏆"},
]

WEIGHTS = [40, 30, 20, 8, 2]  # 500 грн тепер реально може випасти


def fortune_keyboard(current_promo: int = 0) -> InlineKeyboardMarkup:
    status = f"{min(current_promo, FORTUNE_COST)}/{FORTUNE_COST}"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"🎡 Крутити колесо ({status} PROMO)",
                    callback_data="fortune:spin",
                )
            ],
            [
                InlineKeyboardButton(
                    text="📋 Список призів", callback_data="fortune:prizes"
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
        f"У тебе <b>PROMO</b>: <code>{promo}</code> шт.\n"
        f"Один оберт коштує <b>{FORTUNE_COST} PROMO</b>\n\n"
        f"Крути і вигравай реальні гроші! 💰",
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

    if not await spend_promo_for_fortune(user_id, FORTUNE_COST):
        current = await get_promo(user_id)
        await cb.answer(
            f"❌ Недостатньо PROMO!\nУ тебе: {current} шт.\nПотрібно: {FORTUNE_COST} шт.",
            show_alert=True,
        )
        return

    await cb.answer("💵 Запускаємо колесо...")
    await perform_fortune_spin(cb)


# ====================== ПОВНА ДОЛАРОВА АНІМАЦІЯ + СПОВІЩЕННЯ АДМІНУ ======================
async def perform_fortune_spin(cb: CallbackQuery):
    load_msg = await cb.message.edit_text("💵 Запускаємо колесо...")

    async def dollar_anim():
        for _ in range(3):  # 3 повних проходи
            for n in range(11):  # 0 → 10
                bar = "💵" * n + "▫️" * (10 - n)
                try:
                    await load_msg.edit_text(f"💵 Запускаємо колесо...\n{bar}")
                except:
                    return
                await asyncio.sleep(0.22)
        # фінальний повний бар
        try:
            await load_msg.edit_text("💵 Запускаємо колесо...\n💵💵💵💵💵💵💵💵💵💵")
        except:
            pass

    anim_task = asyncio.create_task(dollar_anim())

    # === ВИПАДКОВИЙ ПРИЗ ===
    prize = random.choices(PRIZES, weights=WEIGHTS, k=1)[0]

    await asyncio.sleep(3.0)  # даємо анімації повністю відіграти

    anim_task.cancel()
    try:
        await load_msg.delete()
    except:
        pass

    # === ЗБЕРЕЖЕННЯ ВИГРАШУ ===
    user_id = cb.from_user.id
    username = cb.from_user.username or "-"
    full_name = cb.from_user.full_name or "Unknown"

    await add_money_win(user_id, prize["value"])
    await save_notification(
        user_id,
        username,
        full_name,
        "fortune",
        f"Колесо фортуни: +{prize['value']} грн ({prize['title']})",
    )

    # === СПОВІЩЕННЯ АДМІНУ ===
    admin_text = (
        f"🎡 <b>НОВИЙ ВИГРАШ У ФОРТУНІ!</b>\n\n"
        f"👤 Гравець: <b>{full_name}</b> (@{username})\n"
        f"💵 Сума: <b>+{prize['value']} грн</b>"
    )
    try:
        await cb.bot.send_message(ADMIN_ID, admin_text, parse_mode="HTML")
    except:
        pass  # якщо адмін заблокував бота — не падаємо

    # === РЕЗУЛЬТАТ ГРАВЦЮ ===
    new_promo = await get_promo(user_id)

    result_text = (
        f"🎉 <b>КОЛЕСО ЗУПИНИЛОСЬ!</b>\n\n"
        f"{prize['emoji']} <b>Ви виграли {prize['title']}</b>!\n\n"
    )

    await cb.message.answer(
        result_text, reply_markup=fortune_keyboard(new_promo), parse_mode="HTML"
    )
