

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
import random
import string
from config import ADMIN_ID
from db import get_safe_state, save_safe_state

router = Router(name="group_safe")

WIN_CELL = 198
TOTAL_CELLS = 250


async def load_state() -> dict:
    return await get_safe_state()


async def save_state(opened, win_cell=None):
    current = await get_safe_state()
    await save_safe_state({
        "opened": list(opened),
        "win_cell": win_cell if win_cell is not None else current.get("win_cell", WIN_CELL)
    })


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
# @router.message(Command("open"))
# async def admin_open_cell(message: Message):
#     if message.from_user.id != ADMIN_ID:
#         return

#     args = message.text.split()
#     if len(args) < 2:
#         await message.answer(
#             "❌ Формат:\n"
#             "<code>/open 123</code> — одна клітинка\n"
#             "<code>/open 1-10</code> — діапазон\n"
#             "<code>/open 1,5,9,12</code> — декілька",
#             parse_mode="HTML"
#         )
#         return

#     try:
#         arg = args[1]
#         if "," in arg:
#             cells_to_open = [int(x.strip()) for x in arg.split(",")]
#         elif "-" in arg:
#             start, end = map(int, arg.split("-"))
#             cells_to_open = list(range(start, end + 1))
#         else:
#             cells_to_open = [int(arg)]
#     except:
#         await message.answer(
#             "❌ Формат:\n"
#             "<code>/open 123</code> — одна клітинка\n"
#             "<code>/open 1-10</code> — діапазон\n"
#             "<code>/open 1,5,9,12</code> — декілька",
#             parse_mode="HTML"
#         )
#         return

#     if any(c < 1 or c > TOTAL_CELLS for c in cells_to_open):
#         await message.answer(f"❌ Клітинки від 1 до {TOTAL_CELLS}")
#         return

#     if len(cells_to_open) > 50:
#         await message.answer("❌ Максимум 50 клітинок за раз")
#         return

#     state = await load_state()
#     opened = set(state["opened"])
#     win_cell = state.get("win_cell", WIN_CELL)

#     already_opened = [c for c in cells_to_open if c in opened]
#     new_cells = [c for c in cells_to_open if c not in opened]

#     if not new_cells:
#         await message.answer("⚠️ Всі ці клітинки вже відкриті!")
#         return

#     opened.update(new_cells)
#     await save_state(opened)

#     if win_cell in new_cells:
#         await message.bot.send_message(
#             ADMIN_ID,
#             f"🎉 <b>СЕЙФ ЗЛОМАНО!</b>\n\nКлітинка <b>{win_cell}</b> — ВИГРАШНА!",
#             parse_mode="HTML",
#         )
#         await message.answer(
#             f"🎉 <b>ВІТАЄМО! ВИ ВИГРАЛИ 2000 ГРН!</b> 🏆\n\n"
#             f"🔓 Клітинка <b>{win_cell}</b> відкрила сейф!\n\n"
#             f"💰 Ваш виграш: <b>2000 грн</b>",
#             parse_mode="HTML",
#         )
#     else:
#         skipped = f"\n⚠️ Вже були відкриті: {', '.join(map(str, already_opened))}" if already_opened else ""
#         await message.answer(
#             f"❌ <b>Не вгадали!</b> ❌\n\n"
#             f"Відкрито номер №: <b>{', '.join(map(str, sorted(new_cells)))}</b>"
#             f"{skipped}",
#             parse_mode="HTML",
#         )


@router.message(Command("open"))
async def admin_open_cell(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    if len(message.text.split()) < 2:
        await message.answer(
            "❌ Формат:\n"
            "<code>/open 123</code> — одна клітинка\n"
            "<code>/open 1-10</code> — діапазон\n"
            "<code>/open 35,1,46 20 5 87</code> — багато чисел через кому/пробіл\n"
            "<code>/open 1,5,9,12</code>",
            parse_mode="HTML"
        )
        return

    # Беремо все після команди
    raw_arg = message.text.split(maxsplit=1)[1].strip()

    # Замінюємо кому + пробіли на просто кому, потім чистимо
    # Спочатку замінимо всі коми з пробілами на кому без пробілів
    cleaned = raw_arg.replace(", ", ",").replace(" ,", ",")
    # Тепер розділяємо по комі та по пробілу
    parts = cleaned.replace(",", " ").split()

    cells_to_open = []

    for part in parts:
        part = part.strip()
        if not part:
            continue

        if "-" in part:
            try:
                start, end = map(int, part.split("-"))
                if start > end:
                    start, end = end, start
                cells_to_open.extend(range(start, end + 1))
            except:
                await message.answer(f"❌ Некоректний діапазон: {part}")
                return
        else:
            try:
                num = int(part)
                cells_to_open.append(num)
            except:
                await message.answer(f"❌ Не число: {part}")
                return

    if not cells_to_open:
        await message.answer("❌ Не вдалося розпізнати жодного числа")
        return

    # Прибираємо дублікати і сортуємо для зручності
    cells_to_open = sorted(set(cells_to_open))

    if any(c < 1 or c > TOTAL_CELLS for c in cells_to_open):
        await message.answer(f"❌ Клітинки повинні бути від 1 до {TOTAL_CELLS}")
        return

    if len(cells_to_open) > 50:
        await message.answer("❌ Максимум 50 клітинок за раз")
        return

    state = await load_state()
    opened = set(state["opened"])
    win_cell = state.get("win_cell", WIN_CELL)

    already_opened = [c for c in cells_to_open if c in opened]
    new_cells = [c for c in cells_to_open if c not in opened]

    if not new_cells:
        await message.answer("⚠️ Всі вказані клітинки вже відкриті!")
        return

    opened.update(new_cells)
    await save_state(opened, win_cell)  # win_cell передаємо явно, щоб не губився

    if win_cell in new_cells:
        await message.bot.send_message(
            ADMIN_ID,
            f"🎉 <b>СЕЙФ ЗЛОМАНО!</b>\n\nКлітинка <b>{win_cell}</b> — ВИГРАШНА!",
            parse_mode="HTML",
        )
        await message.answer(
            f"🎉 <b>ВІТАЄМО! ВИ ВИГРАЛИ 2000 ГРН!</b> 🏆\n\n"
            f"🔓 Клітинка <b>{win_cell}</b> відкрила сейф!\n\n"
            f"💰 Ваш виграш: <b>2000 грн</b>",
            parse_mode="HTML",
        )
    else:
        skipped = f"\n⚠️ Вже були відкриті: {', '.join(map(str, already_opened))}" if already_opened else ""
        opened_str = ', '.join(map(str, new_cells))
        await message.answer(
            f"✅ Відкрито: <b>{len(new_cells)}</b> клітинок\n"
            f"Номери: <b>{opened_str}</b>"
            f"{skipped}",
            parse_mode="HTML",
        )