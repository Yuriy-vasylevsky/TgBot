# import random
# import string
# import aiosqlite
# from aiogram import Router, F, types
# from aiogram.fsm.context import FSMContext
# from aiogram.fsm.state import StatesGroup, State
# from aiogram.types import (
#     ReplyKeyboardRemove,
#     ReplyKeyboardMarkup,
#     KeyboardButton,
#     InlineKeyboardMarkup,
#     InlineKeyboardButton,
# )
# from aiogram.utils.keyboard import InlineKeyboardBuilder

# from db import (
#     add_promocode,
#     list_promocodes,
#     check_promocode,
#     set_user_access,
#     has_claimed_gift,
#     increment_games_played,
# )
# from handlers.states import PromoFSM, EnterPromoFSM
# from handlers.menu import main_menu
# from handlers.config import ADMIN_ID, DB_PATH
# from games import games_menu as imported_games_menu  # ← імпорт меню ігор

# router = Router(name="admin_promocodes")


# class PromoFSM(StatesGroup):
#     waiting_for_code = State()   # ручний промокод
#     waiting_for_count = State()


# # ==========================
# # 🎟 Створення промокодів (адмін)
# # ==========================
# @router.message(F.text == "➕ Створити промокод")
# async def create_promocode(message: types.Message, state: FSMContext):
#     if message.from_user.id != ADMIN_ID:
#         return
#     await state.set_state(PromoFSM.waiting_for_code)
#     await message.answer(
#         "🆕 Введіть новий промокод:", reply_markup=ReplyKeyboardRemove()
#     )


# @router.message(PromoFSM.waiting_for_code)
# async def save_promocode_handler(message: types.Message, state: FSMContext):
#     if message.from_user.id != ADMIN_ID:
#         return
#     code = message.text.strip()
#     await add_promocode(code)
#     await message.answer(
#         f"✅ Промокод <b>{code}</b> збережено",
#         reply_markup=main_menu(is_admin=True),
#         parse_mode="HTML",
#     )
#     await state.clear()


# # ---------------- Автоматична генерація ----------------
# @router.message(F.text == "🤞 Згенерувати промо")
# async def ask_promo_count(message: types.Message, state: FSMContext):
#     if message.from_user.id != ADMIN_ID:
#         return

#     await state.set_state(PromoFSM.waiting_for_count)

#     num_kb = ReplyKeyboardMarkup(
#         keyboard=[
#             [KeyboardButton(text=str(i)) for i in range(1, 6)],
#             [KeyboardButton(text="10")],
#         ],
#         resize_keyboard=True,
#     )

#     cancel_kb = InlineKeyboardMarkup(
#         inline_keyboard=[[
#             InlineKeyboardButton(text="❌ Відмінити", callback_data="cancel_promo_gen")
#         ]]
#     )

#     await message.answer(
#         "🔢 Введіть або виберіть кількість промокодів для генерації:",
#         reply_markup=num_kb,
#     )
#     await message.answer(
#         "👇 Якщо передумали, натисніть нижче:",
#         reply_markup=cancel_kb,
#     )


# @router.message(PromoFSM.waiting_for_count)
# async def generate_promocodes(message: types.Message, state: FSMContext):
#     if message.from_user.id != ADMIN_ID:
#         return
#     try:
#         count = int(message.text)
#         if count <= 0 or count > 100:
#             raise ValueError
#     except ValueError:
#         await message.answer("⚠️ Введіть число від 1 до 100 або натисніть кнопку.")
#         return

#     generated = []
#     for _ in range(count):
#         code = "PROMO-" + "".join(
#             random.choices(string.ascii_uppercase + string.digits, k=6)
#         )
#         await add_promocode(code)
#         generated.append(code)

#     text = "\n".join(generated)
#     await message.answer(
#         f"✅ Згенеровано {count} промокодів:\n\n<code>{text}</code>",
#         parse_mode="HTML",
#         reply_markup=main_menu(is_admin=True),
#     )
#     await state.clear()


# @router.callback_query(F.data == "cancel_promo_gen")
# async def cancel_promo_gen(callback: types.CallbackQuery, state: FSMContext):
#     await state.clear()
#     await callback.message.answer("❌ Створення промокодів скасовано.")
#     await callback.message.answer(
#         "🔙 Повертаємось у головне меню.",
#         reply_markup=main_menu(is_admin=callback.from_user.id == ADMIN_ID),
#     )
#     await callback.answer()


# # ==========================
# # 🎟 Активні Promo (адмін)
# # ==========================
# @router.message(F.text == "🎟 Активні Promo")
# async def show_promocodes(message: types.Message):
#     if message.from_user.id != ADMIN_ID:
#         return
#     codes = await list_promocodes()
#     if not codes:
#         await message.answer("❌ Немає активних промокодів")
#         return

#     formatted_codes = "\n".join([f"🎟️ <code>{code}</code>" for code in codes])
#     builder = InlineKeyboardBuilder()
#     builder.button(text="📋 Скопіювати всі", callback_data="copy_codes")
#     builder.button(text="🗑 Очистити всі", callback_data="confirm_clear_codes")
#     builder.adjust(1)
#     await message.answer(
#         f"🎟 <b>Активні промокоди:</b>\n\n{formatted_codes}",
#         reply_markup=builder.as_markup(),
#         parse_mode="HTML",
#     )


# @router.callback_query(F.data == "copy_codes")
# async def copy_codes_callback(callback: types.CallbackQuery):
#     codes = await list_promocodes()
#     if not codes:
#         await callback.message.answer("❌ Немає активних промокодів")
#         await callback.answer()
#         return
#     codes_text = "\n".join(codes)
#     await callback.message.answer(
#         f"📋 <b>Скопіюйте промокоди нижче:</b>\n\n<code>{codes_text}</code>"
#     )
#     await callback.answer("✅ Готово — коди можна скопіювати!")


# @router.callback_query(F.data == "confirm_clear_codes")
# async def confirm_clear_codes(callback: types.CallbackQuery):
#     builder = InlineKeyboardBuilder()
#     builder.button(text="✅ Так, видалити", callback_data="clear_codes")
#     builder.button(text="❌ Скасувати", callback_data="cancel_clear")
#     builder.adjust(2)
#     await callback.message.answer(
#         "⚠️ Ви впевнені, що хочете <b>видалити всі промокоди</b>?",
#         reply_markup=builder.as_markup(),
#         parse_mode="HTML",
#     )
#     await callback.answer()


# @router.callback_query(F.data == "clear_codes")
# async def clear_codes(callback: types.CallbackQuery):
#     async with aiosqlite.connect(DB_PATH) as db:
#         await db.execute("DELETE FROM promocodes")
#         await db.commit()
#     await callback.message.answer("✅ Усі промокоди успішно видалено.")
#     await callback.answer("Видалено ✅")


# @router.callback_query(F.data == "cancel_clear")
# async def cancel_clear(callback: types.CallbackQuery):
#     await callback.message.answer("Операцію скасовано.")
#     await callback.answer("❌ Скасовано")


# # ==========================
# # Введення промокоду користувачем
# # ==========================
# @router.message(F.text == "🎟 Ввести промокод")
# async def enter_promocode(message: types.Message, state: FSMContext):
#     await state.set_state(EnterPromoFSM.waiting_for_code)
#     await message.answer("🔑 Введіть ваш промокод:", reply_markup=ReplyKeyboardRemove())


# @router.message(EnterPromoFSM.waiting_for_code)
# async def check_user_promo(message: types.Message, state: FSMContext):
#     code = message.text.strip()
#     user_id = message.from_user.id
#     gift_claimed = await has_claimed_gift(user_id)

#     if await check_promocode(code):
#         await set_user_access(user_id, True)
#         await increment_games_played(user_id)
#         text = (
#             "✅ <b>Промокод активовано!</b>\n\n"
#             "🎮 Виберіть гру, щоб перевірити свою удачу!\n\n"
#             "🎁 Виграні купони можна поставити в казино 🎰"
#         )
#         await message.answer(text, reply_markup=imported_games_menu())
#     else:
#         await message.answer(
#             "❌ Невірний або вже використаний промокод.",
#             reply_markup=main_menu(
#                 is_admin=(user_id == ADMIN_ID), user_has_gift=gift_claimed
#             ),
#         )

#     await state.clear()


import random
import string
import aiosqlite
from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import (
    ReplyKeyboardRemove,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from db import (
    add_promocode,
    list_promocodes,
    check_promocode,
    set_user_access,
    has_claimed_gift,
    increment_games_played,
    DB_PATH,  # ← імпортуємо DB_PATH з db.py, а не з handlers.config
)
from handlers.states import PromoFSM, EnterPromoFSM
from handlers.menu import main_menu
from handlers.config import ADMIN_ID
from games import games_menu as imported_games_menu

router = Router(name="admin_promocodes")

PROMO_PRICE = 30  # ціна одного промокоду в гривнях


class PromoFSM(StatesGroup):
    waiting_for_code = State()
    waiting_for_count = State()


# ==========================
# 🎟 Створення промокодів (адмін)
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
        f"✅ Промокод <b>{code}</b> збережено",
        reply_markup=main_menu(is_admin=True),
        parse_mode="HTML",
    )
    await state.clear()


# ---------------- Автоматична генерація ----------------
@router.message(F.text == "🤞 Згенерувати промо")
async def ask_promo_count(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return

    await state.set_state(PromoFSM.waiting_for_count)

    num_kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=str(i)) for i in range(1, 6)],
            [KeyboardButton(text="10")],
        ],
        resize_keyboard=True,
    )

    cancel_kb = InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text="❌ Відмінити", callback_data="cancel_promo_gen")
        ]]
    )

    await message.answer(
        "🔢 Введіть або виберіть кількість промокодів для генерації:",
        reply_markup=num_kb,
    )
    await message.answer(
        "👇 Якщо передумали, натисніть нижче:",
        reply_markup=cancel_kb,
    )


@router.message(PromoFSM.waiting_for_count)
async def generate_promocodes(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        count = int(message.text)
        if count <= 0 or count > 100:
            raise ValueError
    except ValueError:
        await message.answer("⚠️ Введіть число від 1 до 100 або натисніть кнопку.")
        return

    generated = []
    for _ in range(count):
        code = "PROMO-" + "".join(
            random.choices(string.ascii_uppercase + string.digits, k=6)
        )
        await add_promocode(code)
        generated.append(code)

    text = "\n".join(generated)
    total = count * PROMO_PRICE
    await message.answer(
        f"✅ Згенеровано {count} промокодів:\n\n<code>{text}</code>\n\n"
        f"💰 Вартість: {count} × {PROMO_PRICE} грн = <b>{total} грн</b>",
        parse_mode="HTML",
        reply_markup=main_menu(is_admin=True),
    )
    await state.clear()


@router.callback_query(F.data == "cancel_promo_gen")
async def cancel_promo_gen(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer("❌ Створення промокодів скасовано.")
    await callback.message.answer(
        "🔙 Повертаємось у головне меню.",
        reply_markup=main_menu(is_admin=callback.from_user.id == ADMIN_ID),
    )
    await callback.answer()


# ==========================
# 🎟 Активні Promo (адмін)
# ==========================
@router.message(F.text == "🎟 Активні Promo")
async def show_promocodes(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    codes = await list_promocodes()
    if not codes:
        await message.answer("❌ Немає активних промокодів")
        return

    count = len(codes)
    total = count * PROMO_PRICE
    formatted_codes = "\n".join([f"🎟️ <code>{code}</code>" for code in codes])

    builder = InlineKeyboardBuilder()
    builder.button(text="📋 Скопіювати всі", callback_data="copy_codes")
    builder.button(text="🗑 Очистити всі", callback_data="confirm_clear_codes")
    builder.adjust(1)

    await message.answer(
        f"🎟 <b>Активні промокоди:</b>\n\n"
        f"{formatted_codes}\n\n"
        f"📦 Кількість: <b>{count} шт</b>\n"
        f"💰 Вартість: <b>{count} × {PROMO_PRICE} грн = {total} грн</b>",
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
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
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "clear_codes")
async def clear_codes(callback: types.CallbackQuery):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM promocodes")
        await db.commit()
    await callback.message.answer("✅ Усі промокоди успішно видалено.")
    await callback.answer("Видалено ✅")


@router.callback_query(F.data == "cancel_clear")
async def cancel_clear(callback: types.CallbackQuery):
    await callback.message.answer("Операцію скасовано.")
    await callback.answer("❌ Скасовано")


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
    gift_claimed = await has_claimed_gift(user_id)

    if await check_promocode(code):
        # ✅ Видаляємо використаний промокод з бази
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM promocodes WHERE code = ?", (code,))
            await db.commit()

        await set_user_access(user_id, True)
        await increment_games_played(user_id)
        text = (
            "✅ <b>Промокод активовано!</b>\n\n"
            "🎮 Виберіть гру, щоб перевірити свою удачу!\n\n"
            "🎁 Виграні купони можна поставити в казино 🎰"
        )
        await message.answer(text, reply_markup=imported_games_menu())
    else:
        await message.answer(
            "❌ Невірний або вже використаний промокод.",
            reply_markup=main_menu(
                is_admin=(user_id == ADMIN_ID), user_has_gift=gift_claimed
            ),
        )

    await state.clear()