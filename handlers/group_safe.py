# from aiogram import Router
# from aiogram.filters import Command
# from aiogram.types import Message
# import json
# from pathlib import Path
# import random
# import string

# from config import ADMIN_ID
# from db import add_promocode

# router = Router(name="group_safe")

# # ==================== НАЛАШТУВАННЯ ====================
# WIN_CELL = 137          # ← міняй тут для нового раунду
# TOTAL_CELLS = 250
# # =====================================================

# STATE_FILE = Path("safe_state.json")

# def load_state():
#     if STATE_FILE.exists():
#         return json.loads(STATE_FILE.read_text(encoding="utf-8"))
#     return {"opened": [], "win_cell": WIN_CELL}

# def save_state(opened):
#     data = {"opened": list(opened), "win_cell": WIN_CELL}
#     STATE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

# def generate_promocode(length: int = 8) -> str:
#     chars = string.ascii_uppercase + string.digits
#     return "".join(random.choices(chars, k=length))


# # ==========================
# # ПРОСТЕ ПОСИЛАННЯ НА СЕЙФ
# # ==========================
# @router.message(Command("safe"))
# async def show_safe(message: Message):
#     state = load_state()
#     opened_count = len(state["opened"])

#     text = (
#         f"🔒 <b>СЕЙФ 250 АКТИВНИЙ</b>\n\n"
#         f"Відкрито: <b>{opened_count}</b> / {TOTAL_CELLS}\n\n"
#         f"🔗 <a href='https://safe-250-web-production.up.railway.app'>Відкрити Сейф 250</a>"
#     )
#     await message.answer(text, parse_mode="HTML", disable_web_page_preview=True)


# # ==========================
# # АДМІН ВІДКРИВАЄ КЛІТИНКУ
# # ==========================
# @router.message(Command("o"))
# async def admin_open_cell(message: Message):
#     if message.from_user.id != ADMIN_ID:
#         return

#     try:
#         cell = int(message.text.split()[1])
#     except:
#         await message.answer("❌ Формат: <code>/o 123</code>", parse_mode="HTML")
#         return

#     if cell < 1 or cell > TOTAL_CELLS:
#         await message.answer(f"❌ Клітинка від 1 до {TOTAL_CELLS}")
#         return

#     state = load_state()
#     opened = set(state["opened"])

#     if cell in opened:
#         await message.answer(f"⚠️ Клітинка {cell} вже відкрита!")
#         return

#     opened.add(cell)
#     save_state(opened)

#     if cell == WIN_CELL:
#         promo = generate_promocode()
#         await add_promocode(promo)

#         await message.bot.send_message(
#             ADMIN_ID,
#             f"🎉 <b>СЕЙФ ЗЛОМАНО!</b>\nКлітинка <b>{cell}</b>\nПромокод:\n<code>{promo}</code>",
#             parse_mode="HTML"
#         )

#         await message.answer(
#             f"✅ <b>ВІДКРИТО! ВИГРАШ!</b> 🏆\nКлітинка <b>{cell}</b> — ВИГРАШНА!\nПромокод: <code>{promo}</code>",
#             parse_mode="HTML"
#         )
#     else:
#         await message.answer(
#             f"❌ <b>Не вгадали</b>\nКлітинка <b>{cell}</b> — порожньо",
#             parse_mode="HTML"
#         )


from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
import json
from pathlib import Path
import random
import string

from config import ADMIN_ID
from db import add_promocode

router = Router(name="group_safe")

TOTAL_CELLS = 250
STATE_FILE = Path("safe_state.json")

def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    # Перший запуск — генеруємо випадкову виграшну клітинку
    return {
        "opened": [],
        "win_cell": random.randint(1, TOTAL_CELLS)
    }

def save_state(opened, win_cell):
    data = {"opened": list(opened), "win_cell": win_cell}
    STATE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def generate_promocode(length: int = 8) -> str:
    chars = string.ascii_uppercase + string.digits
    return "".join(random.choices(chars, k=length))


# ==========================
# ПОКАЗАТИ СЕЙФ (чисте посилання)
# ==========================
@router.message(Command("safe"))
async def show_safe(message: Message):
    state = load_state()
    await message.answer(
        f"🔒 <b>СЕЙФ 250 АКТИВНИЙ</b>\n\n"
        f"Відкрито: <b>{len(state['opened'])}</b> / {TOTAL_CELLS}\n"
        f"Виграшна клітинка: прихована\n\n"
        f"🔗 <a href='https://safe-250-web-production.up.railway.app'>Відкрити Сейф 250</a>",
        parse_mode="HTML",
        disable_web_page_preview=True
    )


# ==========================
# НОВИЙ РАУНД (адмін)
# ==========================
@router.message(Command("new_safe"))
async def new_safe(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    new_win = random.randint(1, TOTAL_CELLS)
    save_state([], new_win)
    await message.answer(
        f"✅ <b>Новий раунд запущено!</b>\n\n"
        f"Виграшна клітинка: <b>нова (прихована)</b>",
        parse_mode="HTML"
    )


# ==========================
# АДМІН ВІДКРИВАЄ КЛІТИНКУ
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

    state = load_state()
    opened = set(state["opened"])
    win_cell = state["win_cell"]

    if cell in opened:
        await message.answer(f"⚠️ Клітинка {cell} вже відкрита!")
        return

    opened.add(cell)

    if cell == win_cell:
        # === ВИГРАШ + АВТО-СКИД ===
        promo = generate_promocode()
        await add_promocode(promo)

        # Скидаємо сейф і генеруємо нову виграшну
        new_win = random.randint(1, TOTAL_CELLS)
        save_state([], new_win)

        await message.bot.send_message(
            ADMIN_ID,
            f"🎉 <b>СЕЙФ ЗЛОМАНО!</b>\n\n"
            f"Клітинка <b>{cell}</b> — ВИГРАШНА!\n"
            f"Промокод:\n<code>{promo}</code>\n\n"
            f"Сейф автоматично скинуто. Нова виграшна: прихована",
            parse_mode="HTML"
        )

        await message.answer(
            f"✅ <b>ВІДКРИТО! ВИГРАШ!</b> 🏆\n\n"
            f"Клітинка <b>{cell}</b> — ВИГРАШНА!\n"
            f"Промокод: <code>{promo}</code>\n\n"
            f"Сейф скинуто — новий раунд розпочато!",
            parse_mode="HTML"
        )
    else:
        save_state(opened, win_cell)
        await message.answer(
            f"❌ <b>Не вгадали</b>\nКлітинка <b>{cell}</b> — порожньо",
            parse_mode="HTML"
        )