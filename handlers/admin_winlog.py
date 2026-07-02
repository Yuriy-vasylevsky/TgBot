from aiogram import Router, F, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from handlers.config import ADMIN_ID
from db.winlog import get_win_summary, get_win_log_page, get_top_winners

router = Router(name="admin_winlog")

TYPE_LABELS = {
    "cashback": "💸 Кешбек",
    "promo":    "🎟 Промокод",
    "game":     "🎮 Особисті ігри",
    "fortune":  "🎡 Колесо фортуни",
    "group":    "👥 Групові ігри",
}

PER_PAGE = 15


def _label(win_type: str) -> str:
    return TYPE_LABELS.get(win_type, win_type)


async def build_summary_text(date_offset: int) -> str:
    summary = await get_win_summary(date_offset)
    day_label = "Сьогодні" if date_offset == 0 else "Вчора"

    lines = [f"📊 <b>Виграші — {day_label} ({summary['date']})</b>\n"]

    if not summary["by_type"]:
        lines.append("Поки що немає жодного виграшу за цей день.")
    else:
        for win_type, data in sorted(
            summary["by_type"].items(), key=lambda x: -x[1]["total"]
        ):
            lines.append(
                f"{_label(win_type)}: <b>{data['total']} грн</b> ({data['count']} шт)"
            )
        lines.append(f"\n💰 <b>Всього за день: {summary['total']} грн</b>")

    top = await get_top_winners(date_offset, limit=5)
    if top:
        lines.append("\n🏆 <b>Топ гравців:</b>")
        for i, t in enumerate(top, 1):
            uname = f"@{t['username']}" if t["username"] and t["username"] != "—" else t["full_name"]
            lines.append(f"{i}. {uname} — <b>{t['total']} грн</b>")

    return "\n".join(lines)


def summary_keyboard(date_offset: int) -> InlineKeyboardMarkup:
    other = 1 - date_offset if date_offset in (0, 1) else 0
    other_label = "📅 Вчора" if date_offset == 0 else "📅 Сьогодні"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=other_label, callback_data=f"winlog:sum:{other}")],
        [InlineKeyboardButton(text="📋 Детальний список", callback_data=f"winlog:list:{date_offset}:1")],
    ])


def list_keyboard(date_offset: int, page: int, total_pages: int) -> InlineKeyboardMarkup:
    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"winlog:list:{date_offset}:{page-1}"))
    nav.append(InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="noop"))
    if page < total_pages:
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"winlog:list:{date_offset}:{page+1}"))

    return InlineKeyboardMarkup(inline_keyboard=[
        nav,
        [InlineKeyboardButton(text="⬅️ До зведення", callback_data=f"winlog:sum:{date_offset}")],
    ])


@router.message(F.text == "📊 Виграші")
async def show_winlog_summary(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    text = await build_summary_text(0)
    await message.answer(text, parse_mode="HTML", reply_markup=summary_keyboard(0))


@router.callback_query(F.data.startswith("winlog:sum:"))
async def cb_winlog_summary(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer()
        return

    date_offset = int(callback.data.split(":")[2])
    text = await build_summary_text(date_offset)
    await callback.message.edit_text(
        text, parse_mode="HTML", reply_markup=summary_keyboard(date_offset)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("winlog:list:"))
async def cb_winlog_list(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer()
        return

    _, _, date_offset_str, page_str = callback.data.split(":")
    date_offset = int(date_offset_str)
    page = int(page_str)

    entries, total_pages = await get_win_log_page(date_offset, page, PER_PAGE)
    day_label = "Сьогодні" if date_offset == 0 else "Вчора"

    if not entries:
        text = f"📋 <b>Список виграшів — {day_label}</b>\n\nПорожньо."
    else:
        lines = [f"📋 <b>Список виграшів — {day_label}</b>\n"]
        for e in entries:
            uname = f"@{e['username']}" if e["username"] and e["username"] != "—" else e["full_name"]
            time_str = e["created_at"].split(" ")[1][:5] if " " in e["created_at"] else e["created_at"]
            lines.append(
                f"🕐 {time_str} | {uname} | {_label(e['win_type'])} ({e['source']}) "
                f"— <b>{e['amount']} грн</b>"
            )
        text = "\n".join(lines)

    await callback.message.edit_text(
        text, parse_mode="HTML",
        reply_markup=list_keyboard(date_offset, page, total_pages)
    )
    await callback.answer()


@router.callback_query(F.data == "noop")
async def cb_noop(callback: types.CallbackQuery):
    await callback.answer()