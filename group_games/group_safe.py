

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
import random
import string
from handlers.config import ADMIN_ID
from db import get_safe_state, save_safe_state

router = Router(name="group_safe")

WIN_CELL = 198
TOTAL_CELLS = 250


async def load_state() -> dict:
    state = await get_safe_state()
    if not state or not isinstance(state, dict):
        state = {}
    
    state.setdefault("opened", [])
    state.setdefault("win_cell", WIN_CELL)
    state.setdefault("users", {})          # ← вже було
    return state


async def save_state(opened=None, win_cell=None, users=None):
    """Оновлена версія — автоматично очищає лідерборд при повному скиданні сейфа"""
    current = await load_state()
    
    new_opened = list(opened) if opened is not None else current["opened"]
    new_win_cell = win_cell if win_cell is not None else current["win_cell"]
    
    # 🔥 ОСНОВНА ФІШКА: якщо сейф повністю очищається — скидаємо і users
    if opened is not None and len(new_opened) == 0:
        new_users = {}
    else:
        new_users = users if users is not None else current.get("users", {})

    updated = {
        "opened": new_opened,
        "win_cell": new_win_cell,
        "users": new_users,
    }
    await save_safe_state(updated)

async def get_win_cell() -> int:
    state = await get_safe_state()
    return state.get("win_cell", WIN_CELL)


def generate_promocode(length: int = 8) -> str:
    chars = string.ascii_uppercase + string.digits
    return "".join(random.choices(chars, k=length))


# ==========================
# ПОКАЗАТИ СЕЙФ (група)
# ==========================
@router.message(Command("safe"))
async def show_safe(message: Message):
    state = await load_state()
    await message.answer(
        f"🔒 <b>СЕЙФ 250</b> 🔒\n\n"
        f"🔓 Відкрито: <b>{len(state['opened'])}</b> / {TOTAL_CELLS}\n"
        f"🏆 Виграшний номер: <b>❓❓❓</b>\n\n"
        f"🔗 <a href='https://safe-250-web-production.up.railway.app'>Переглянути Сейф</a>",
        parse_mode="HTML",
        disable_web_page_preview=True,
    )


# ==========================
# АДМІН ВІДКРИВАЄ КЛІТИНКУ
# ==========================




@router.message(Command("open"))
async def admin_open_cell(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    # ==========================
    # ОТРИМУЄМО ГРАВЦЯ + МЕНШЕН
    # ==========================
    target_user = None
    mention = ""
    if message.reply_to_message and message.reply_to_message.from_user:
        target_user = message.reply_to_message.from_user
        if target_user.username:
            mention = f"@{target_user.username}"
        else:
            mention = f"<a href='tg://user?id={target_user.id}'>{target_user.full_name}</a>"
        mention = f"<b>{mention}</b> "

    # ==========================
    # ПАРСИНГ + ВСІ ПЕРЕВІРКИ (без змін)
    # ==========================
    if len(message.text.split()) < 2:
        await message.answer(f"{mention}❌ Формат:\n<code>/open 123</code> ...", parse_mode="HTML")
        return

    raw_arg = message.text.split(maxsplit=1)[1].strip()
    cleaned = raw_arg.replace(", ", ",").replace(" ,", ",")
    parts = cleaned.replace(",", " ").split()

    cells_to_open = []
    for part in parts:
        part = part.strip()
        if not part: continue
        if "-" in part:
            try:
                start, end = map(int, part.split("-"))
                if start > end: start, end = end, start
                cells_to_open.extend(range(start, end + 1))
            except:
                await message.answer(f"{mention}❌ Некоректний діапазон: {part}", parse_mode="HTML")
                return
        else:
            try:
                cells_to_open.append(int(part))
            except:
                await message.answer(f"{mention}❌ Не число: {part}", parse_mode="HTML")
                return

    if not cells_to_open:
        await message.answer(f"{mention}❌ Не вдалося розпізнати жодного числа", parse_mode="HTML")
        return

    cells_to_open = sorted(set(cells_to_open))

    if any(c < 1 or c > TOTAL_CELLS for c in cells_to_open):
        await message.answer(f"{mention}❌ Клітинки повинні бути від 1 до {TOTAL_CELLS}", parse_mode="HTML")
        return
    if len(cells_to_open) > 50:
        await message.answer(f"{mention}❌ Максимум 50 клітинок за раз", parse_mode="HTML")
        return

    # ==========================
    # РОБОТА З БАЗОЮ + ЗАПИС ГРАВЦЯ
    # ==========================
    state = await load_state()
    opened = set(state["opened"])
    win_cell = state.get("win_cell", WIN_CELL)
    users = state["users"].copy()                     # <-- копія для оновлення

    already_opened = [c for c in cells_to_open if c in opened]
    new_cells = [c for c in cells_to_open if c not in opened]

    if not new_cells:
        await message.answer(f"{mention}⚠️ <b>Всі вказані клітинки вже відкриті!</b>", parse_mode="HTML")
        return

    # === ЗАПИСУЄМО ГРАВЦЯ (якщо є reply) ===
    if target_user and new_cells:
        user_id = str(target_user.id)
        display_name = f"@{target_user.username}" if target_user.username else target_user.full_name
        
        current_count = users.get(user_id, {}).get("count", 0)
        users[user_id] = {
            "display_name": display_name,           # оновлюється при кожному відкритті
            "count": current_count + len(new_cells)
        }

    opened.update(new_cells)
    await save_state(opened=opened, win_cell=win_cell, users=users)   # зберігаємо все

    # ==========================
    # ВИГРАШ
    # ==========================
    if win_cell in new_cells:
        await message.answer(
            f"{mention}🎉 <b>СЕЙФ ЗЛОМАНО!</b> 🏆\n\n"
            f"🔓 Клітинка <b>{win_cell}</b> — ВИГРАШНА!\n"
            f"💰 Виграш: <b>2000 грн</b>",
            parse_mode="HTML"
        )
        await message.bot.send_message(
            ADMIN_ID,
            f"🎉 СЕЙФ ЗЛОМАНО!\nГравець: {mention.strip()}\nКлітинка: {win_cell}",
            parse_mode="HTML"
        )
        return

    # ==========================
    # НЕ ВГАДАЛИ
    # ==========================
    skipped = f"\n⚠️ Вже були відкриті: {', '.join(map(str, already_opened))}" if already_opened else ""
    opened_str = ', '.join(map(str, new_cells))

    await message.answer(
        f"{mention}❌ <b>Не вгадали!</b> ❌\n\n"
        f"✅ Перевірено: <b>{len(new_cells)}</b> клітинок\n"
        f"Номери: <b>{opened_str}</b>{skipped}",
        parse_mode="HTML"
    )









