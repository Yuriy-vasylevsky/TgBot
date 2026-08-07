from datetime import datetime
from html import escape

from aiogram import F, Router, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from db import get_payment_history_page, get_payment_history_summary
from handlers.config import ADMIN_ID

router = Router(name="payment_history")

PER_PAGE = 12


def _day_label(date_offset: int) -> str:
    return "Сьогодні" if date_offset == 0 else "Вчора"


def _summary_keyboard(date_offset: int) -> InlineKeyboardMarkup:
    other_day = 1 if date_offset == 0 else 0
    other_label = "📅 Вчора" if date_offset == 0 else "📅 Сьогодні"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Виконані",
                    callback_data=f"payhist:list:{date_offset}:completed:1",
                ),
                InlineKeyboardButton(
                    text="⏳ Активні",
                    callback_data=f"payhist:list:{date_offset}:active:1",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=other_label,
                    callback_data=f"payhist:summary:{other_day}",
                )
            ],
        ]
    )


def _list_keyboard(
    date_offset: int,
    status_group: str,
    page: int,
    total_pages: int,
) -> InlineKeyboardMarkup:
    navigation: list[InlineKeyboardButton] = []
    if page > 1:
        navigation.append(
            InlineKeyboardButton(
                text="⬅️",
                callback_data=(
                    f"payhist:list:{date_offset}:{status_group}:{page - 1}"
                ),
            )
        )
    navigation.append(
        InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="payhist:noop")
    )
    if page < total_pages:
        navigation.append(
            InlineKeyboardButton(
                text="➡️",
                callback_data=(
                    f"payhist:list:{date_offset}:{status_group}:{page + 1}"
                ),
            )
        )

    return InlineKeyboardMarkup(
        inline_keyboard=[
            navigation,
            [
                InlineKeyboardButton(
                    text="⬅️ До зведення",
                    callback_data=f"payhist:summary:{date_offset}",
                )
            ],
        ]
    )


async def _summary_text(date_offset: int) -> str:
    summary = await get_payment_history_summary(date_offset)
    return (
        f"💳 <b>Усі оплати — {_day_label(date_offset)} "
        f"({summary['date']})</b>\n\n"
        f"✅ <b>Виконані:</b> {summary['completed_count']}\n"
        f"💰 Зараховано: <b>{summary['approved_total']} грн</b> "
        f"({summary['approved_count']} шт.)\n"
        f"❌ Відхилено: <b>{summary['rejected_count']}</b>\n\n"
        f"⏳ <b>Активні:</b> {summary['active_count']}\n"
        f"💵 Очікують перевірки: <b>{summary['active_total']} грн</b>"
    )


def _format_user(entry: dict) -> str:
    username = (entry.get("username") or "").strip()
    if username and username != "-":
        return f"@{escape(username.lstrip('@'))}"
    full_name = (entry.get("full_name") or "").strip()
    if full_name:
        return escape(full_name)
    return f"ID: <code>{entry['user_id']}</code>"


def _format_time(value: str | None) -> str:
    if not value:
        return "—"
    try:
        return datetime.fromisoformat(value).strftime("%H:%M")
    except (TypeError, ValueError):
        return escape(str(value))


async def _list_text(
    date_offset: int,
    status_group: str,
    page: int,
) -> tuple[str, InlineKeyboardMarkup]:
    entries, total_pages = await get_payment_history_page(
        date_offset, status_group, page, PER_PAGE
    )
    group_label = "Виконані" if status_group == "completed" else "Активні"
    lines = [
        f"💳 <b>{group_label} оплати — {_day_label(date_offset)}</b>\n"
    ]

    if not entries:
        lines.append("Записів немає.")
    else:
        for entry in entries:
            number = entry.get("daily_number") or "—"
            source = "ручна оплата"
            if entry["status"] == "approved":
                status = "✅ зараховано"
            elif entry["status"] == "rejected":
                status = "❌ відхилено"
            else:
                status = "⏳ очікує"
            lines.append(
                f"<b>№{number}</b> · {_format_time(entry['created_at'])} · {status}\n"
                f"👤 {_format_user(entry)}\n"
                f"💰 <b>{entry['amount']} грн</b> · {source}\n"
            )

    lines.append(f"<i>Сторінка {page}/{total_pages}</i>")
    return "\n".join(lines), _list_keyboard(
        date_offset, status_group, page, total_pages
    )


@router.message(F.text.in_({"💳 Всі оплати", "💳 Історія оплат"}))
async def show_payment_summary(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer(
        await _summary_text(0),
        parse_mode="HTML",
        reply_markup=_summary_keyboard(0),
    )


@router.callback_query(F.data.startswith("payhist:summary:"))
async def show_payment_summary_callback(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer()
        return
    date_offset = int(callback.data.rsplit(":", 1)[1])
    await callback.message.edit_text(
        await _summary_text(date_offset),
        parse_mode="HTML",
        reply_markup=_summary_keyboard(date_offset),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("payhist:list:"))
async def show_payment_list(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer()
        return
    _, _, date_offset_raw, status_group, page_raw = callback.data.split(":")
    date_offset = int(date_offset_raw)
    page = int(page_raw)
    text, keyboard = await _list_text(date_offset, status_group, page)
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=keyboard,
    )
    await callback.answer()


@router.callback_query(F.data == "payhist:noop")
async def payment_history_noop(callback: types.CallbackQuery):
    await callback.answer()
