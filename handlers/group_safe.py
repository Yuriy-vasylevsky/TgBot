from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
import json
from pathlib import Path

from config import ADMIN_ID

router = Router(name="group_safe")

# ==================== НАЛАШТУВАННЯ ====================
WIN_CELL = 137          # ←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←
TOTAL_CELLS = 250
# =====================================================

STATE_FILE = Path("safe_state.json")

def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {"opened": [], "win_cell": WIN_CELL}

def save_state(opened, win_cell):
    data = {"opened": list(opened), "win_cell": win_cell}
    STATE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ==========================
# ПОКАЗАТИ СЕЙФ
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
# НОВИЙ СЕЙФ З ВКАЗАНИМ ЧИСЛОМ
# ==========================
@router.message(Command("new_safe"))
async def new_safe(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    try:
        new_win = int(message.text.split()[1])
        if not 1 <= new_win <= TOTAL_CELLS:
            await message.answer("❌ Число має бути від 1 до 250")
            return
    except:
        await message.answer("❌ Використання: <code>/new_safe 197</code>", parse_mode="HTML")
        return

    save_state([], new_win)
    await message.answer(
        f"✅ <b>Новий сейф запущено!</b>\n\n"
        f"Виграшна клітинка: <b>{new_win}</b> (прихована для гравців)\n"
        f"Всі клітинки скинуто.",
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
        # === ВИГРАШ ===
        save_state([], win_cell)   # не скидаємо win_cell, тільки очищаємо відкриті

        await message.answer(
            f"🎉 <b>ВІТАЮ! ВИ ВИГРАЛИ 2000 грн!</b> 🏆\n\n"
            f"Клітинка <b>{cell}</b> була виграшною!",
            parse_mode="HTML"
        )
    else:
        save_state(opened, win_cell)
        await message.answer(
            f"❌ <b>Не вгадали</b>\nКлітинка <b>{cell}</b> — порожньо",
            parse_mode="HTML"
        )