from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from aiohttp import web
import json
from pathlib import Path
import random
import string
from config import ADMIN_ID

router = Router(name="group_safe")

WIN_CELL = 198
TOTAL_CELLS = 250
STATE_FILE = Path("safe_state.json")

def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {"opened": [], "win_cell": WIN_CELL}


def save_state(opened, win_cell=None):
    current = load_state()
    data = {
        "opened": list(opened),
        "win_cell": win_cell if win_cell is not None else current.get("win_cell", WIN_CELL)
    }
    STATE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def get_win_cell() -> int:
    return load_state().get("win_cell", WIN_CELL)


def generate_promocode(length: int = 8) -> str:
    chars = string.ascii_uppercase + string.digits
    return "".join(random.choices(chars, k=length))


# ==========================
# ПОКАЗАТИ СЕЙФ (група)
# ==========================
@router.message(Command("safe"))
async def show_safe(message: Message):
    state = load_state()
    await message.answer(
        f"🔒 <b>СЕЙФ 250</b> 🔒\n\n"
        f"🔓 Відкрито: <b>{len(state['opened'])}</b> / {TOTAL_CELLS}\n"
        f"🏆 Виграшний номер: <b>❓❓❓</b>\n\n"
        f"🔗 <a href='https://safe-250-web-production.up.railway.app'>Переглянути Сейф</a>",
        parse_mode="HTML",
        disable_web_page_preview=True,
    )

@router.message(Command("open"))
async def admin_open_cell(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    args = message.text.split()
    if len(args) < 2:
        await message.answer("❌ Формат: <code>/o 123</code> або <code>/o 1-10</code>", parse_mode="HTML")
        return

    try:
        arg = args[1]
        if "," in arg:
            # /open 1,2,3,4
            cells_to_open = [int(x.strip()) for x in arg.split(",")]
        elif "-" in arg:
            # /open 1-10
            start, end = map(int, arg.split("-"))
            cells_to_open = list(range(start, end + 1))
        else:
            # /open 123
            cells_to_open = [int(arg)]
    except:
        await message.answer(
            "❌ Формат:\n"
            "<code>/open 123</code> — одна клітинка\n"
            "<code>/open 1-10</code> — діапазон\n"
            "<code>/open 1,5,9,12</code> — декілька",
            parse_mode="HTML"
        )
        return

    # Перевірка діапазону
    if any(c < 1 or c > TOTAL_CELLS for c in cells_to_open):
        await message.answer(f"❌ Клітинки від 1 до {TOTAL_CELLS}")
        return

    if len(cells_to_open) > 50:
        await message.answer("❌ Максимум 50 клітинок за раз")
        return

    state = load_state()
    opened = set(state["opened"])
    win_cell = state.get("win_cell", WIN_CELL)

    already_opened = [c for c in cells_to_open if c in opened]
    new_cells = [c for c in cells_to_open if c not in opened]

    if not new_cells:
        await message.answer(f"⚠️ Всі ці клітинки вже відкриті!")
        return

    opened.update(new_cells)
    save_state(opened)

    # Перевіряємо чи є виграшна серед нових
    if win_cell in new_cells:
        # promo = generate_promocode()
        # await add_promocode(promo)
        await message.bot.send_message(
            ADMIN_ID,
            f"🎉 <b>СЕЙФ ЗЛОМАНО!</b>\n\nКлітинка <b>{win_cell}</b> — ВИГРАШНА!",
            parse_mode="HTML",
        )
        await message.answer(
            f"🎉 <b>ВІТАЄМО! ВИ ВИГРАЛИ 2000 ГРН!</b> 🏆\n\n"
            f"🔓 Клітинка <b>{win_cell}</b> відкрила сейф!\n\n"
            f"💰 Ваш виграш: <b>2000 грн</b>\n",
            # f"🎟 Промокод для отримання:\n<code>{promo}</code>",
            parse_mode="HTML",
        )
    else:
        skipped = f"\n⚠️ Вже були відкриті: {', '.join(map(str, already_opened))}" if already_opened else ""
        await message.answer(
            f"❌ <b>Не вгадали!</b> ❌\n\n"
            f"Відкрито номер №: <b>{', '.join(map(str, sorted(new_cells)))}</b>"
            f"{skipped}",
            parse_mode="HTML",
        )