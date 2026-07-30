from datetime import datetime, timedelta, timezone
from html import escape

import aiosqlite
from aiogram import F, Router, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from db import DB_PATH
from handlers.config import ADMIN_ID


router = Router(name="admin_losses")

KYIV_TZ = timezone(timedelta(hours=3))
PER_PAGE = 15


def _player_label(
    user_id: int, username: str | None, full_name: str | None
) -> str:
    name = escape(full_name or "Без імені")
    if username:
        return f"{name} (@{escape(username.lstrip('@'))})"
    return f'<a href="tg://user?id={user_id}">{name}</a>'


async def _get_losses() -> tuple[list[dict], list[dict]]:
    today = datetime.now(KYIV_TZ).date()
    yesterday = today - timedelta(days=1)

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT
                user_id,
                username,
                full_name,
                COALESCE(daily_net, 0) AS daily_net,
                COALESCE(yesterday_net, 0) AS yesterday_net,
                last_net_date
            FROM users
            """
        )
        rows = await cursor.fetchall()

    today_losses: list[dict] = []
    yesterday_losses: list[dict] = []

    for row in rows:
        last_date_raw = row["last_net_date"]
        try:
            last_date = datetime.fromisoformat(str(last_date_raw)).date()
        except (TypeError, ValueError):
            last_date = None

        if last_date == today:
            today_value = row["daily_net"]
            yesterday_value = row["yesterday_net"]
        elif last_date == yesterday:
            # Денний reset ще не запускався для цього користувача:
            # його daily_net фактично належить учорашньому дню.
            today_value = 0
            yesterday_value = row["daily_net"]
        else:
            today_value = 0
            yesterday_value = 0

        player = {
            "user_id": row["user_id"],
            "username": row["username"],
            "full_name": row["full_name"],
        }
        if today_value > 0:
            today_losses.append({**player, "amount": today_value})
        if yesterday_value > 0:
            yesterday_losses.append({**player, "amount": yesterday_value})

    today_losses.sort(key=lambda item: item["amount"], reverse=True)
    yesterday_losses.sort(key=lambda item: item["amount"], reverse=True)
    return today_losses, yesterday_losses


def _format_players(players: list[dict]) -> list[str]:
    return [
        (
            f"{index}. {_player_label(item['user_id'], item['username'], item['full_name'])}"
            f" — <b>{item['amount']} грн</b>"
        )
        for index, item in enumerate(players, start=1)
    ]


def _losses_for_day(
    today_losses: list[dict], yesterday_losses: list[dict], date_offset: int
) -> list[dict]:
    return today_losses if date_offset == 0 else yesterday_losses


async def _build_summary_text(date_offset: int) -> str:
    today_losses, yesterday_losses = await _get_losses()
    players = _losses_for_day(today_losses, yesterday_losses, date_offset)
    day_label = "Сьогодні" if date_offset == 0 else "Вчора"
    total = sum(item["amount"] for item in players)

    lines = [
        f"📉 <b>Програші — {day_label}</b>\n",
        f"💰 Всього за день: <b>{total} грн</b>",
        f"👥 Гравців: <b>{len(players)}</b>",
    ]
    if players:
        lines.append("\n🔝 <b>Найбільші програші:</b>")
        lines.extend(_format_players(players[:5]))
    else:
        lines.append("\nПоки що немає програшів за цей день.")
    return "\n".join(lines)


def _summary_keyboard(date_offset: int) -> InlineKeyboardMarkup:
    other_offset = 1 if date_offset == 0 else 0
    other_label = "📅 Вчора" if date_offset == 0 else "📅 Сьогодні"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=other_label,
                    callback_data=f"losses:summary:{other_offset}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="📋 Детальний список",
                    callback_data=f"losses:list:{date_offset}:1",
                )
            ],
        ]
    )


def _list_keyboard(
    date_offset: int, page: int, total_pages: int
) -> InlineKeyboardMarkup:
    navigation: list[InlineKeyboardButton] = []
    if page > 1:
        navigation.append(
            InlineKeyboardButton(
                text="⬅️",
                callback_data=f"losses:list:{date_offset}:{page - 1}",
            )
        )
    navigation.append(
        InlineKeyboardButton(
            text=f"{page}/{total_pages}",
            callback_data="losses:noop",
        )
    )
    if page < total_pages:
        navigation.append(
            InlineKeyboardButton(
                text="➡️",
                callback_data=f"losses:list:{date_offset}:{page + 1}",
            )
        )

    return InlineKeyboardMarkup(
        inline_keyboard=[
            navigation,
            [
                InlineKeyboardButton(
                    text="⬅️ До зведення",
                    callback_data=f"losses:summary:{date_offset}",
                )
            ],
        ]
    )


@router.message(F.text == "📉 Програші")
async def show_losses(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return

    await message.answer(
        await _build_summary_text(0),
        parse_mode="HTML",
        reply_markup=_summary_keyboard(0),
    )


@router.callback_query(F.data.startswith("losses:summary:"))
async def show_losses_summary(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer()
        return

    date_offset = int(callback.data.split(":")[2])
    await callback.message.edit_text(
        await _build_summary_text(date_offset),
        parse_mode="HTML",
        reply_markup=_summary_keyboard(date_offset),
        disable_web_page_preview=True,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("losses:list:"))
async def show_losses_list(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer()
        return

    _, _, date_offset_raw, page_raw = callback.data.split(":")
    date_offset = int(date_offset_raw)
    page = int(page_raw)

    today_losses, yesterday_losses = await _get_losses()
    players = _losses_for_day(today_losses, yesterday_losses, date_offset)
    total_pages = max(1, (len(players) + PER_PAGE - 1) // PER_PAGE)
    page = min(max(page, 1), total_pages)
    start = (page - 1) * PER_PAGE
    page_players = players[start : start + PER_PAGE]
    day_label = "Сьогодні" if date_offset == 0 else "Вчора"

    if page_players:
        lines = [f"📋 <b>Програші — {day_label}</b>\n"]
        for index, item in enumerate(page_players, start=start + 1):
            lines.append(
                f"{index}. "
                f"{_player_label(item['user_id'], item['username'], item['full_name'])}"
                f" — <b>{item['amount']} грн</b>"
            )
        text = "\n".join(lines)
    else:
        text = f"📋 <b>Програші — {day_label}</b>\n\nСписок порожній."

    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=_list_keyboard(date_offset, page, total_pages),
        disable_web_page_preview=True,
    )
    await callback.answer()


@router.callback_query(F.data == "losses:noop")
async def losses_noop(callback: types.CallbackQuery):
    await callback.answer()
