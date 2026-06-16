

# from aiogram import Router, F, types
# from aiogram.utils.keyboard import InlineKeyboardBuilder
# from datetime import datetime

# from handlers.config import ADMIN_ID
# from db import get_payment_logs_by_date

# router = Router(name="payment_history")

# # ==========================
# # НАЛАШТУВАННЯ
# # ==========================

# LABEL_TODAY = "Сьогодні"
# LABEL_YESTERDAY = "Вчора"

# BTN_PREV = "◀ Назад"
# BTN_NEXT = "Вперед ▶"

# BTN_TODAY = "📅 Сьогодні"
# BTN_YESTERDAY = "📅 Вчора"

# SEPARATOR = "─────────────────"


# def format_time(dt_str: str) -> str:
#     try:
#         dt = datetime.fromisoformat(dt_str)
#         return dt.strftime("%H:%M")
#     except Exception:
#         return dt_str


# def build_keyboard(page: int, total_pages: int, day: int):
#     builder = InlineKeyboardBuilder()

#     if page > 1:
#         builder.button(
#             text=BTN_PREV,
#             callback_data=f"ph:{day}:{page - 1}"
#         )

#     if page < total_pages:
#         builder.button(
#             text=BTN_NEXT,
#             callback_data=f"ph:{day}:{page + 1}"
#         )

#     if day == 0:
#         builder.button(
#             text=BTN_YESTERDAY,
#             callback_data="ph:1:1"
#         )
#     else:
#         builder.button(
#             text=BTN_TODAY,
#             callback_data="ph:0:1"
#         )

#     builder.adjust(2, 1)
#     return builder.as_markup()


# async def render_history(
#     day: int,
#     page: int
# ) -> tuple[str, types.InlineKeyboardMarkup]:

#     rows, total_pages, day_total = await get_payment_logs_by_date(
#         date_offset=day,
#         page=page
#     )

#     label = LABEL_TODAY if day == 0 else LABEL_YESTERDAY

#     text = (
#         f"💳 <b>Поповнення — {label}</b>\n\n"
#     )

#     if not rows:
#         text += "Записів немає"
#     else:
#         for row in rows:
#             user_id, username, amount, comment, created_at = row

#             if username and username != "-":
#                 name = (
#                     username
#                     if " " in username
#                     else f"@{username}"
#                 )
#             else:
#                 name = f"ID: {user_id}"

#             time_str = format_time(created_at)

#             text += (
#                 f"👤 {name}\n"
#                 f"💰 {amount} грн | 🕒 {time_str}\n\n"
#             )

#         text += (
#             f"{SEPARATOR}\n"
#             f"💵 <b>Разом за день: {day_total} грн</b>\n"
#             f"<i>Стор. {page} / {total_pages}</i>"
#         )

#     keyboard = build_keyboard(
#         page=page,
#         total_pages=total_pages,
#         day=day
#     )

#     return text, keyboard


# @router.message(F.text == "💳 Історія оплат")
# async def payment_history(message: types.Message):
#     if message.from_user.id != ADMIN_ID:
#         return

#     text, keyboard = await render_history(
#         day=0,
#         page=1
#     )

#     await message.answer(
#         text,
#         parse_mode="HTML",
#         reply_markup=keyboard
#     )


# @router.callback_query(F.data.startswith("ph:"))
# async def payment_history_page(
#     callback: types.CallbackQuery
# ):
#     if callback.from_user.id != ADMIN_ID:
#         return

#     _, day_str, page_str = callback.data.split(":")

#     day = int(day_str)
#     page = int(page_str)

#     text, keyboard = await render_history(
#         day=day,
#         page=page
#     )

#     await callback.message.edit_text(
#         text,
#         parse_mode="HTML",
#         reply_markup=keyboard
#     )

#     await callback.answer()

from aiogram import Router, F, types
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime, timedelta, timezone

from handlers.config import ADMIN_ID
from db import get_payment_logs_by_date

router = Router(name="payment_history")

KYIV_TZ = timezone(timedelta(hours=3))

LABEL_TODAY = "Сьогодні"
LABEL_YESTERDAY = "Вчора"

BTN_PREV = "◀ Назад"
BTN_NEXT = "Вперед ▶"

BTN_TODAY = "📅 Сьогодні"
BTN_YESTERDAY = "📅 Вчора"

SEPARATOR = "─────────────────"


def format_time(dt_str: str) -> str:
    try:
        dt = datetime.fromisoformat(dt_str)
        # Якщо час без timezone — вважаємо що це UTC, конвертуємо в Київ
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc).astimezone(KYIV_TZ)
        else:
            dt = dt.astimezone(KYIV_TZ)
        return dt.strftime("%H:%M")
    except Exception:
        return dt_str


def build_keyboard(page: int, total_pages: int, day: int):
    builder = InlineKeyboardBuilder()

    if page > 1:
        builder.button(text=BTN_PREV, callback_data=f"ph:{day}:{page - 1}")

    if page < total_pages:
        builder.button(text=BTN_NEXT, callback_data=f"ph:{day}:{page + 1}")

    if day == 0:
        builder.button(text=BTN_YESTERDAY, callback_data="ph:1:1")
    else:
        builder.button(text=BTN_TODAY, callback_data="ph:0:1")

    builder.adjust(2, 1)
    return builder.as_markup()


async def render_history(day: int, page: int) -> tuple[str, types.InlineKeyboardMarkup]:
    rows, total_pages, day_total = await get_payment_logs_by_date(
        date_offset=day,
        page=page
    )

    label = LABEL_TODAY if day == 0 else LABEL_YESTERDAY
    text = f"💳 <b>Поповнення — {label}</b>\n\n"

    if not rows:
        text += "Записів немає"
    else:
        for row in rows:
            user_id, username, amount, comment, created_at = row

            if username and username != "-":
                name = username if " " in username else f"@{username}"
            else:
                name = f"ID: {user_id}"

            time_str = format_time(created_at)
            text += f"👤 {name}\n💰 {amount} грн | 🕒 {time_str}\n\n"

        text += (
            f"{SEPARATOR}\n"
            f"💵 <b>Разом за день: {day_total} грн</b>\n"
            f"<i>Стор. {page} / {total_pages}</i>"
        )

    keyboard = build_keyboard(page=page, total_pages=total_pages, day=day)
    return text, keyboard


@router.message(F.text == "💳 Історія оплат")
async def payment_history(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return

    text, keyboard = await render_history(day=0, page=1)
    await message.answer(text, parse_mode="HTML", reply_markup=keyboard)


@router.callback_query(F.data.startswith("ph:"))
async def payment_history_page(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return

    _, day_str, page_str = callback.data.split(":")
    day = int(day_str)
    page = int(page_str)

    text, keyboard = await render_history(day=day, page=page)
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    await callback.answer()