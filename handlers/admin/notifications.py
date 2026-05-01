# from aiogram import Router, F, types
# from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
# from db import get_notifications
# from handlers.config import ADMIN_ID

# router = Router(name="admin_notifications")


# # =============================================================================================
# #                              📜 ІСТОРІЯ СПОВІЩЕНЬ (АДМІН)
# # =============================================================================================

# @router.message(F.text == "📜 Історія сповіщень")
# async def show_notifications(message: types.Message):
#     if message.from_user.id != ADMIN_ID:
#         return await message.answer("⛔ Доступ лише для адміністратора.")

#     page = 1
#     filter_type = None
#     records, total_pages = await get_notifications(page=page, filter_type=filter_type)

#     text = "<b>📜 Історія сповіщень</b>\n\n"
#     if records:
#         text += "\n\n".join(records)
#     else:
#         text += "🔹 Поки немає нових сповіщень."

#     kb = build_notifications_kb(page, total_pages, filter_type)
#     await message.answer(text, parse_mode="HTML", reply_markup=kb)


# # ===============================  ⚙️ ПАГІНАЦІЯ ТА ФІЛЬТРИ   ===============================

# @router.callback_query(F.data.startswith("notif_page:"))
# async def paginate_notifications(cb: CallbackQuery):
#     if cb.from_user.id != ADMIN_ID:
#         return await cb.answer("⛔ Доступ лише для адміністратора.", show_alert=True)

#     data = cb.data.split(":")
#     page = int(data[1])
#     filter_type = data[2] if len(data) > 2 and data[2] != "none" else None

#     records, total_pages = await get_notifications(page=page, filter_type=filter_type)

#     text = "<b>📜 Історія сповіщень</b>\n\n"
#     text += "\n\n".join(records) if records else "🔹 Більше немає записів."

#     kb = build_notifications_kb(page, total_pages, filter_type)
#     await cb.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
#     await cb.answer()


# @router.callback_query(F.data.startswith("notif_filter:"))
# async def filter_notifications(cb: CallbackQuery):
#     if cb.from_user.id != ADMIN_ID:
#         return await cb.answer("⛔ Доступ лише для адміністратора.", show_alert=True)

#     filter_type = cb.data.split(":")[1]
#     page = 1
#     records, total_pages = await get_notifications(page=page, filter_type=filter_type)

#     text = f"<b>📜 Історія сповіщень</b>\n🔍 Фільтр: <code>{filter_type}</code>\n\n"
#     text += "\n\n".join(records) if records else "🔹 Немає записів для цього типу."

#     kb = build_notifications_kb(page, total_pages, filter_type)
#     await cb.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
#     await cb.answer()


# # ===============================   🧩 ДОПОМІЖНА ФУНКЦІЯ КЛАВІАТУРИ   ===============================

# def build_notifications_kb(page: int, total_pages: int, filter_type: str | None):
#     ftype = filter_type or "none"

#     return InlineKeyboardMarkup(
#         inline_keyboard=[
#             [
#                 InlineKeyboardButton(
#                     text="⬅️", callback_data=f"notif_page:{page-1}:{ftype}"
#                 ),
#                 InlineKeyboardButton(
#                     text=f"{page}/{total_pages}", callback_data="noop"
#                 ),
#                 InlineKeyboardButton(
#                     text="➡️", callback_data=f"notif_page:{page+1}:{ftype}"
#                 ),
#             ],
#             [
#                 InlineKeyboardButton(
#                     text="🎰 Слоти", callback_data="notif_filter:slots"
#                 ),
#                 InlineKeyboardButton(
#                     text="🎯 1 із 3", callback_data="notif_filter:one_of_three"
#                 ),
#                 InlineKeyboardButton(
#                     text="🃏 Blackjack", callback_data="notif_filter:blackjack"
#                 ),
#             ],
#             [
#                 InlineKeyboardButton(
#                     text="🎡 Фортуна", callback_data="notif_filter:fortune"
#                 ),
#                 InlineKeyboardButton(
#                     text="🎁 Бонус", callback_data="notif_filter:bonus"
#                 ),
#             ],
#         ]
#     )


from aiogram import Router, F, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from db.admin import get_notifications, get_daily_winnings_summary
from handlers.config import ADMIN_ID

router = Router(name="admin_notifications")


# =============================================================================================
#                              📜 ІСТОРІЯ СПОВІЩЕНЬ (АДМІН)
# =============================================================================================

async def build_notifications_text(page: int, filter_type: str | None) -> tuple[str, int]:
    records, total_pages = await get_notifications(page=page, filter_type=filter_type)
    daily = await get_daily_winnings_summary()

    # text = (
    #     f"<b>📜 Історія сповіщень</b>\n\n"
    #     f"📊 <b>Виграші за сьогодні:</b>\n"
    #     f"  🎰 Слоти: <b>{daily['slots_count'] * 30} грн</b>\n"
    #     f"  🎯 1 із 3: <b>{daily['one_of_three_count'] * 30} грн</b>\n"
    #     f"  🃏 Блекджек: <b>{daily['blackjack_count'] * 30} грн</b>\n"
    #     f"  🎡 Фортуна: <b>{daily['fortune_total']} грн</b>\n\n"
    #     f"  💰 Разом: <b>{daily['grand_total']} грн</b>\n"
    #     f"━━━━━━━━━━━━━━━━━\n\n"
    # )

    text = (
        f"<b>📜 Історія сповіщень</b>\n\n"
        f"📊 <b>Виграші за сьогодні:</b>\n"
        f"  🎰 Слоти: <b>{daily['slots']} грн</b>\n"
        f"  🎯 1 із 3: <b>{daily['one_of_three']} грн</b>\n"
        f"  🃏 Блекджек: <b>{daily['blackjack']} грн</b>\n"
        f"  🎡 Фортуна: <b>{daily['fortune']} грн</b>\n\n"
        f"  💰 <b>Разом: {daily['grand_total']} грн</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
    )

    if filter_type:
        text += f"🔍 Фільтр: <code>{filter_type}</code>\n\n"

    text += "\n\n".join(records) if records else "🔹 Поки немає нових сповіщень."
    return text, total_pages


@router.message(F.text == "📜 Історія сповіщень")
async def show_notifications(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return await message.answer("⛔ Доступ лише для адміністратора.")

    text, total_pages = await build_notifications_text(page=1, filter_type=None)
    await message.answer(text, parse_mode="HTML", reply_markup=build_notifications_kb(1, total_pages, None))


# ===============================  ⚙️ ПАГІНАЦІЯ ТА ФІЛЬТРИ   ===============================

@router.callback_query(F.data.startswith("notif_page:"))
async def paginate_notifications(cb: CallbackQuery):
    if cb.from_user.id != ADMIN_ID:
        return await cb.answer("⛔ Доступ лише для адміністратора.", show_alert=True)

    data = cb.data.split(":")
    page = int(data[1])
    filter_type = data[2] if len(data) > 2 and data[2] != "none" else None

    text, total_pages = await build_notifications_text(page, filter_type)
    await cb.message.edit_text(text, parse_mode="HTML", reply_markup=build_notifications_kb(page, total_pages, filter_type))
    await cb.answer()


@router.callback_query(F.data.startswith("notif_filter:"))
async def filter_notifications(cb: CallbackQuery):
    if cb.from_user.id != ADMIN_ID:
        return await cb.answer("⛔ Доступ лише для адміністратора.", show_alert=True)

    filter_type = cb.data.split(":")[1]

    text, total_pages = await build_notifications_text(page=1, filter_type=filter_type)
    await cb.message.edit_text(text, parse_mode="HTML", reply_markup=build_notifications_kb(1, total_pages, filter_type))
    await cb.answer()


# ===============================   🧩 ДОПОМІЖНА ФУНКЦІЯ КЛАВІАТУРИ   ===============================

def build_notifications_kb(page: int, total_pages: int, filter_type: str | None):
    ftype = filter_type or "none"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⬅️", callback_data=f"notif_page:{page-1}:{ftype}"),
                InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="noop"),
                InlineKeyboardButton(text="➡️", callback_data=f"notif_page:{page+1}:{ftype}"),
            ],
            [
                InlineKeyboardButton(text="🎰 Слоти", callback_data="notif_filter:slots"),
                InlineKeyboardButton(text="🎯 1 із 3", callback_data="notif_filter:one_of_three"),
                InlineKeyboardButton(text="🃏 Blackjack", callback_data="notif_filter:blackjack"),
            ],
            [
                InlineKeyboardButton(text="🎡 Фортуна", callback_data="notif_filter:fortune"),
              
            ],
        ]
    )