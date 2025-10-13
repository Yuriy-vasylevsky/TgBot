import aiosqlite
from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import ReplyKeyboardRemove
from db import (
    get_winrate,
    set_winrate,
    get_all_users_info,
    add_promocode,
    list_promocodes,
    check_promocode,
    set_user_access,
    has_claimed_gift,
)
from menu import admin_menu, main_menu
from games import games_menu as imported_games_menu
from states import WinrateFSM, Broadcast, PromoFSM, EnterPromoFSM, CodeLinkFSM
import config

router = Router()
ADMIN_ID = config.ADMIN_ID

USERS_PER_PAGE = 7


# ==========================
# ⚙️ Адмін панель
# ==========================
@router.message(F.text == "⚙️ Адмін панель")
async def admin_panel(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer("🔐 Адмін панель", reply_markup=admin_menu())
    else:
        await message.answer("⛔ У вас немає доступу")


# ==========================
# 🎯 Winrate
# ==========================
@router.message(F.text == "🎯 Winrate")
async def show_winrate(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    current = await get_winrate()
    percent = round(current * 100)
    await message.answer(
        f"🎯 Поточний winrate: <b>{percent}%</b>\n\nВведіть новий відсоток виграшу (0–100):",
        reply_markup=ReplyKeyboardRemove(),
    )
    await state.set_state(WinrateFSM.waiting_for_value)


@router.message(WinrateFSM.waiting_for_value)
async def set_new_winrate(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        val = int(message.text.strip())
        if not (0 <= val <= 100):
            raise ValueError
        await set_winrate(val / 100)
        await message.answer(
            f"✅ Новий winrate збережено: {val}%", reply_markup=admin_menu()
        )
    except ValueError:
        await message.answer("❌ Введіть число від 0 до 100.")
    await state.clear()


# ==========================
# 👥 Список користувачів
# ==========================
async def send_users_page(message_or_query, users, page: int):
    from datetime import datetime

    users.sort(
        key=lambda x: datetime.fromisoformat(x[3]) if x[3] else datetime.min,
        reverse=True,
    )

    total_pages = (len(users) + USERS_PER_PAGE - 1) // USERS_PER_PAGE
    start = (page - 1) * USERS_PER_PAGE
    end = start + USERS_PER_PAGE
    current_users = users[start:end]

    text = f"👥 <b>Користувачі (сторінка {page}/{total_pages}):</b>\n\n"
    for i, (uid, username, full_name, last_active) in enumerate(
        current_users, start=start + 1
    ):
        last_active_str = last_active or "немає даних"
        text += f"{i}. 👤 <b>{full_name}</b>\n   🔗 @{username or '—'}\n   🕒 {last_active_str}\n\n"

    kb = InlineKeyboardBuilder()
    if page > 1:
        kb.button(text="⬅️ Новіші", callback_data=f"users_page:{page - 1}")
    if end < len(users):
        kb.button(text="➡️ Старіші", callback_data=f"users_page:{page + 1}")
    kb.adjust(2)

    if isinstance(message_or_query, types.CallbackQuery):
        await message_or_query.message.edit_text(
            text, parse_mode="HTML", reply_markup=kb.as_markup()
        )
        await message_or_query.answer()
    else:
        await message_or_query.answer(
            text, parse_mode="HTML", reply_markup=kb.as_markup()
        )


@router.message(F.text == "👥 Список користувачів")
async def list_users(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    users = await get_all_users_info()
    if not users:
        await message.answer("❌ Користувачів ще немає.")
        return
    await send_users_page(message, users, page=1)


@router.callback_query(F.data.startswith("users_page:"))
async def paginate_users(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Лише для адміністратора.", show_alert=True)
        return
    page = int(callback.data.split(":")[1])
    users = await get_all_users_info()
    await send_users_page(callback, users, page)


# ==========================
# 📢 Розсилка
# ==========================
@router.message(F.text == "📢 Розсилка")
async def start_broadcast(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await state.set_state(Broadcast.waiting_for_text)
    cancel_kb = InlineKeyboardBuilder()
    cancel_kb.button(text="❌ Скасувати розсилку", callback_data="cancel_broadcast")
    await message.answer(
        "✍️ Введіть текст розсилки або натисніть «❌ Скасувати розсилку»:",
        reply_markup=cancel_kb.as_markup(),
    )


@router.message(Broadcast.waiting_for_text)
async def process_broadcast_text(message: types.Message, state: FSMContext):
    text = message.text
    confirm_kb = InlineKeyboardBuilder()
    confirm_kb.button(text="✅ Надіслати", callback_data="confirm_broadcast")
    confirm_kb.button(text="❌ Скасувати", callback_data="cancel_broadcast")
    await state.update_data(broadcast_text=text)
    await message.answer(
        f"📨 Текст розсилки:\n\n{text}\n\nНадіслати розсилку?",
        reply_markup=confirm_kb.as_markup(),
    )


@router.callback_query(F.data == "confirm_broadcast")
async def confirm_broadcast(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    text = data.get("broadcast_text")

    async with aiosqlite.connect("users.db") as conn:
        async with conn.execute("SELECT user_id FROM users") as cur:
            rows = await cur.fetchall()

    count = 0
    for (user_id,) in rows:
        try:
            await callback.bot.send_message(user_id, text)
            count += 1
        except Exception:
            continue

    await callback.message.answer(f"✅ Розсилку надіслано {count} користувачам.")
    await state.clear()
    await callback.answer()


@router.callback_query(F.data == "cancel_broadcast")
async def cancel_broadcast(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer("❌ Розсилку скасовано.")
    await callback.answer()


# ==========================
# 🎟 Промокоди
# ==========================
@router.message(F.text == "➕ Створити промокод")
async def create_promocode(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await state.set_state(PromoFSM.waiting_for_code)
    await message.answer(
        "🆕 Введіть новий промокод:", reply_markup=ReplyKeyboardRemove()
    )


@router.message(PromoFSM.waiting_for_code)
async def save_promocode_handler(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    code = message.text.strip()
    await add_promocode(code)
    await message.answer(
        f"✅ Промокод <b>{code}</b> збережено", reply_markup=admin_menu()
    )
    await state.clear()


@router.message(F.text == "🎟 Активні промокоди")
async def show_promocodes(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    codes = await list_promocodes()
    if not codes:
        await message.answer("❌ Немає активних промокодів")
        return

    formatted_codes = "\n".join([f"🎟️ <code>{code}</code>" for code in codes])
    builder = InlineKeyboardBuilder()
    builder.button(text="📋 Скопіювати всі", callback_data="copy_codes")
    builder.button(text="🗑 Очистити всі", callback_data="confirm_clear_codes")
    builder.adjust(1)
    await message.answer(
        f"🎟 <b>Активні промокоди:</b>\n\n{formatted_codes}",
        reply_markup=builder.as_markup(),
    )


@router.callback_query(F.data == "copy_codes")
async def copy_codes_callback(callback: types.CallbackQuery):
    codes = await list_promocodes()
    if not codes:
        await callback.message.answer("❌ Немає активних промокодів")
        await callback.answer()
        return
    codes_text = "\n".join(codes)
    await callback.message.answer(
        f"📋 <b>Скопіюйте промокоди нижче:</b>\n\n<code>{codes_text}</code>"
    )
    await callback.answer("✅ Готово — коди можна скопіювати!")


@router.callback_query(F.data == "confirm_clear_codes")
async def confirm_clear_codes(callback: types.CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Так, видалити", callback_data="clear_codes")
    builder.button(text="❌ Скасувати", callback_data="cancel_clear")
    builder.adjust(2)
    await callback.message.answer(
        "⚠️ Ви впевнені, що хочете <b>видалити всі промокоди</b>?",
        reply_markup=builder.as_markup(),
    )
    await callback.answer()


@router.callback_query(F.data == "clear_codes")
async def clear_codes(callback: types.CallbackQuery):
    await clear_all_promocodes()
    await callback.message.answer("✅ Усі промокоди успішно видалено.")
    await callback.answer("Видалено ✅")


@router.callback_query(F.data == "cancel_clear")
async def cancel_clear(callback: types.CallbackQuery):
    await callback.message.answer("Операцію скасовано.")
    await callback.answer("❌ Скасовано")


# ==========================
# Очистка промокодів
# ==========================
async def clear_all_promocodes():
    async with aiosqlite.connect("users.db") as db:
        await db.execute("DELETE FROM promocodes")
        await db.commit()


# ==========================
# Введення промокоду користувачем
# ==========================
@router.message(F.text == "🎟 Ввести промокод")
async def enter_promocode(message: types.Message, state: FSMContext):
    await state.set_state(EnterPromoFSM.waiting_for_code)
    await message.answer("🔑 Введіть ваш промокод:", reply_markup=ReplyKeyboardRemove())


@router.message(EnterPromoFSM.waiting_for_code)
async def check_user_promo(message: types.Message, state: FSMContext):
    code = message.text.strip()
    user_id = message.from_user.id

    # Перевіряємо, чи користувач вже отримав подарунок
    gift_claimed = await has_claimed_gift(user_id)

    if await check_promocode(code):
        await set_user_access(user_id, True)
        text = (
            "✅ <b>Промокод активовано!</b>\n\n"
            "🎮 Виберіть гру, щоб перевірити свою удачу!\n\n"
            "🎁 Виграні купони можна поставити в казино 🎰"
        )
        await message.answer(text, reply_markup=imported_games_menu())
    else:
        # Передаємо актуальний стан подарунка у меню
        await message.answer(
            "❌ Невірний або вже використаний промокод.",
            reply_markup=main_menu(
                is_admin=(user_id == ADMIN_ID), user_has_gift=gift_claimed
            ),
        )

    # Очищаємо стан FSM
    await state.clear()
