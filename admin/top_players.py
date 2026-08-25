from html import escape
from math import ceil

from aiogram import F, Router, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from db import get_top_players_by_losses
from handlers.config import ADMIN_ID


router = Router(name="admin_top_players")

PLAYERS_PER_PAGE = 10


def _player_name(player: dict) -> str:
    full_name = escape((player.get("full_name") or "Без імені").strip())
    username = player.get("username")
    user_id = int(player["user_id"])
    identity = f"@{escape(username)}" if username else f"<code>{user_id}</code>"
    return f'<a href="tg://user?id={user_id}">{full_name}</a> · {identity}'


def _pagination_keyboard(page: int, total_pages: int) -> InlineKeyboardMarkup | None:
    if total_pages <= 1:
        return None

    buttons: list[InlineKeyboardButton] = []
    if page > 1:
        buttons.append(
            InlineKeyboardButton(
                text="⬅️",
                callback_data=f"top_players:{page - 1}",
            )
        )
    buttons.append(
        InlineKeyboardButton(
            text=f"{page}/{total_pages}",
            callback_data="top_players:noop",
        )
    )
    if page < total_pages:
        buttons.append(
            InlineKeyboardButton(
                text="➡️",
                callback_data=f"top_players:{page + 1}",
            )
        )
    return InlineKeyboardMarkup(inline_keyboard=[buttons])


async def _build_top_players(page: int) -> tuple[str, InlineKeyboardMarkup | None]:
    page = max(1, page)
    players, total_players, total_loss = await get_top_players_by_losses(
        limit=PLAYERS_PER_PAGE,
        offset=(page - 1) * PLAYERS_PER_PAGE,
    )
    total_pages = max(1, ceil(total_players / PLAYERS_PER_PAGE))

    if page > total_pages:
        page = total_pages
        players, total_players, total_loss = await get_top_players_by_losses(
            limit=PLAYERS_PER_PAGE,
            offset=(page - 1) * PLAYERS_PER_PAGE,
        )

    if not players:
        return (
            "🏆 <b>ТОП ГРАВЦІВ</b>\n\n"
            "Поки немає гравців із зафіксованим програшем.",
            None,
        )

    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    start_position = (page - 1) * PLAYERS_PER_PAGE + 1
    lines: list[str] = []
    for position, player in enumerate(players, start=start_position):
        place = medals.get(position, f"{position}.")
        lines.append(
            f"{place} {_player_name(player)}\n"
            f"   💔 <b>{int(player['total_loss'])} грн</b>"
        )

    text = (
        "🏆 <b>ТОП ГРАВЦІВ ЗА ПРОГРАШЕМ</b>\n\n"
        + "\n\n".join(lines)
        + "\n\n─────────────────\n"
        f"👥 Гравців: <b>{total_players}</b>\n"
        f"💔 Загальний програш: <b>{total_loss} грн</b>"
    )
    return text, _pagination_keyboard(page, total_pages)


@router.message(F.text == "🏆 Топ гравці")
async def show_top_players(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return

    text, keyboard = await _build_top_players(1)
    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=keyboard,
        disable_web_page_preview=True,
    )


@router.callback_query(F.data.startswith("top_players:"))
async def paginate_top_players(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Доступно лише адміністратору", show_alert=True)
        return

    page_raw = callback.data.split(":", maxsplit=1)[1]
    if page_raw == "noop":
        await callback.answer()
        return

    try:
        page = int(page_raw)
    except ValueError:
        await callback.answer()
        return

    text, keyboard = await _build_top_players(page)
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=keyboard,
        disable_web_page_preview=True,
    )
    await callback.answer()
