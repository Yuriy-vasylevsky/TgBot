from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
import random
import string

from config import ADMIN_ID
from db import add_promocode, get_safe_win_cell, set_safe_win_cell

router = Router(name="group_safe")

TOTAL_CELLS = 250


def generate_promocode(length: int = 8) -> str:
    chars = string.ascii_uppercase + string.digits
    return "".join(random.choices(chars, k=length))


# ==========================
# ПОКАЗАТИ СЕЙФ
# ==========================
@router.message(Command("safe"))
async def show_safe(message: Message):
    win_cell = await get_safe_win_cell()
    opened_count = 0  # поки що не зберігаємо кількість в БД, можна додати пізніше

    await message.answer(
        f"🔒 <b>СЕЙФ 250 АКТИВНИЙ</b>\n\n"
        f"Відкрито: <b>{opened_count}</b> / {TOTAL_CELLS}\n"
        f"Виграшна клітинка: прихована\n\n"
        f"🔗 <a href='https://safe-250-web-production.up.railway.app'>Відкрити Сейф 250</a>",
        parse_mode="HTML",
        disable_web_page_preview=True
    )


# ==========================
# ЗМІНИТИ ВИГРАШНЕ ЧИСЛО
# ==========================
@router.message(Command("set_win"))
async def set_win_cell(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    try:
        new_win = int(message.text.split()[1])
        if not 1 <= new_win <= TOTAL_CELLS:
            raise ValueError
    except:
        await message.answer("❌ Використання: <code>/set_win 197</code>", parse_mode="HTML")
        return

    await set_safe_win_cell(new_win)
    await message.answer(
        f"✅ <b>Виграшне число змінено!</b>\n\n"
        f"Нове виграшне: <b>{new_win}</b>",
        parse_mode="HTML"
    )


# ==========================
# СКИНУТИ ВІДКРИТІ КЛІТИНКИ (новий раунд)
# ==========================
@router.message(Command("new_safe"))
async def new_safe(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    # Просто очищуємо список відкритих (win_cell лишається)
    # Якщо хочеш зберігати opened в БД — можемо додати, зараз для простоти скидаємо через JSON або додамо пізніше
    # Поки що просто повідомлення
    await message.answer(
        f"✅ <b>Сейф скинуто!</b>\n\n"
        f"Всі відкриті клітинки очищено.\n"
        f"Виграшне число залишилось те саме.",
        parse_mode="HTML"
    )


# ==========================
# ВІДКРИТИ КЛІТИНКУ
# ==========================
@router.message(Command("o"))
async def admin_open_cell(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    try:
        cell = int(message.text.split()[1])
    except:
        await message.answer("❌ Формат: <code>/o 123</code>", parse_mode="HTML")
        return

    if cell < 1 or cell > TOTAL_CELLS:
        await message.answer(f"❌ Клітинка від 1 до {TOTAL_CELLS}")
        return

    win_cell = await get_safe_win_cell()

    if cell == win_cell:
        promo = generate_promocode()   # можна залишити для адміна в ЛС
        await add_promocode(promo)

        await message.bot.send_message(
            ADMIN_ID,
            f"🎉 Промокод згенеровано: <code>{promo}</code>",
            parse_mode="HTML"
        )

        await message.answer(
            f"🎉 <b>ВІТАЮ! ВИ ВИГРАЛИ 2000 грн!</b> 🏆\n\n"
            f"Клітинка <b>{cell}</b> була виграшною!\n\n"
            f"Сейф скинуто (всі клітинки знову вільні)",
            parse_mode="HTML"
        )

        # Тут можна додати очищення opened в БД якщо зберігатимеш
    else:
        await message.answer(
            f"❌ <b>Не вгадали</b>\nКлітинка <b>{cell}</b> — порожньо",
            parse_mode="HTML"
        )