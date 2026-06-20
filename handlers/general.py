import re
import random
from pathlib import Path
from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import FSInputFile
from handlers.menu import actions_menu, main_menu
from db import has_claimed_gift
import handlers.config as config
from games import games_menu as imported_games_menu


from aiogram.types import Message

router = Router()

ADMIN_ID = config.ADMIN_ID


# ==========================
# Основні кнопки меню
# ==========================
@router.message(F.text == "🎲 Група")
async def send_group(message: types.Message):
    await message.answer(f"Приєднуйтесь до нашої групи: {config.GROUP_LINK}")


@router.message(F.text == "💎 Касир")
async def send_casher(message: types.Message):
    await message.answer(f"Касир: {config.CONTACT_PHONE}")


@router.message(F.text == "🏅 Провайдери")
async def send_providers(message: types.Message):
    await message.answer(f"{config.PROVAIDER}")


@router.message(F.text == "💳 Номер карти")
async def send_card(message: types.Message):
    from db import get_cards

    cards = await get_cards()
    text = "💳 Поточні картки:\n\n" + "\n".join(
        [f"{bank}: <code>{num}</code>" for bank, num in cards]
    )
    text += "\n\n💵 Мінімальний платіж — 200 грн\n💸 Мінімальний вивід — 400 грн\n\n⏰ Касир доступний 9:00–00:00"
    await message.answer(text, parse_mode="HTML")


@router.message(F.text == "💥 Демо гра")
async def send_demo(message: types.Message):
    await message.answer(config.DEMO)


@router.message(F.text == "🔹 Акції")
async def send_actions(message: types.Message):
    await message.answer("Оберіть одну з наших акцій:", reply_markup=actions_menu())


# ==========================
# Відео/аудіо акції
# ==========================
async def send_promo_video(
    message: types.Message, video_file: str, caption: str, btn_text: str, btn_data: str
):
    builder = InlineKeyboardBuilder()
    builder.button(text=btn_text, callback_data=btn_data)
    video_path = Path(__file__).parent.parent / "videos" / video_file
    await message.answer_video(
        FSInputFile(video_path),
        caption=caption,
        reply_markup=builder.as_markup(),
        supports_streaming=True,
    )


@router.message(F.text == "🎮 Бонус на Superomatic")
async def promo_superomatic(message: types.Message):
    await send_promo_video(
        message,
        "1.mp4",
        config.AK1_CAPTION,
        "ℹ️ Детальніше про акцію",
        "promo_superomatic_details",
    )


@router.callback_query(F.data == "promo_superomatic_details")
async def promo_superomatic_details(callback: types.CallbackQuery):
    await callback.message.answer(config.AK1_DETAILS)
    audio_path = Path(__file__).parent.parent / "audio" / "superomatic.mp3"
    await callback.message.answer_audio(
        FSInputFile(audio_path), caption="🎧 Прослухай коротко про акцію!"
    )
    await callback.answer()


@router.message(F.text == "🎲 Сейф")
async def promo_seif(message: types.Message):
    await send_promo_video(
        message,
        "2.mp4",
        config.AK2_CAPTION,
        "ℹ️ Детальніше про акцію",
        "promo_seif_details",
    )


@router.callback_query(F.data == "promo_seif_details")
async def promo_seif_details(callback: types.CallbackQuery):
    await callback.message.answer(config.AK2_DETAILS, parse_mode="Markdown")
    audio_path = Path(__file__).parent.parent / "audio" / "seif.mp3"
    await callback.message.answer_audio(
        FSInputFile(audio_path), caption="🎧 Прослухай коротко про умови сейфу!"
    )
    await callback.answer()


@router.message(F.text == "🃏 Cash Back")
async def promo_cash_back(message: types.Message):
    video_path = Path(__file__).parent.parent / "videos" / "3.mp4"
    await message.answer_video(FSInputFile(video_path), caption=config.AK3)


@router.message(F.text == "🎟 Промокоди")
async def promo_cash(message: types.Message):
    await send_promo_video(
        message, "4.mp4", config.AK4, "ℹ️ Детальніше", "promo_cash_details"
    )


@router.callback_query(F.data == "promo_cash_details")
async def promo_cash_details(callback: types.CallbackQuery):
    await callback.message.answer(config.AK4_DETAILS, parse_mode="Markdown")
    audio_path = Path(__file__).parent.parent / "audio" / "promo.mp3"
    await callback.message.answer_audio(
        FSInputFile(audio_path), title="Промокоди — твій ключ до виграшу!"
    )
    await callback.answer()


# ==========================
# КОД в посилання
# ==========================
import re
from aiogram import F, types
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram import Router


class CodeLinkFSM(StatesGroup):
    waiting_for_code = State()


@router.message(F.text == "💫 КОД в посилання")
async def ask_code_for_links(message: types.Message, state: FSMContext):
    await state.set_state(CodeLinkFSM.waiting_for_code)
    await message.answer("Введіть код у форматі: 00-00-00-00-00-00-00")


# =====================================================================================================


@router.message(F.text == "🔙 Назад до головного меню")
async def back_from_games(message: types.Message):
    user_id = message.from_user.id

    # Перевіряємо, чи користувач вже отримав подарунок
    gift_claimed = await has_claimed_gift(user_id)

    # Формуємо головне меню з актуальним станом подарунка
    keyboard = main_menu(is_admin=(user_id == ADMIN_ID), user_has_gift=gift_claimed)

    await message.answer("Головне меню:", reply_markup=keyboard)


# ==========================
# Меню ігор (для адміна)
# ==========================
@router.message(F.text == "🎮 Ігри")
async def admin_games_menu(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer(
            "🎮 Меню ігор (адмін доступ):", reply_markup=imported_games_menu()
        )
    else:
        await message.answer("⛔ Ця функція лише для адміністратора.")


# __________________________ ПЕРЕГЛЯД І ВИДАЛЕННЯ КОДІВ З БД _____________________________________________

from aiogram import Router, F, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
import aiosqlite
from pathlib import Path

# router = Router()

# DB_PATH = Path(__file__).parent / "users.db"
from db import DB_PATH

# ________________________________________________________________________________________________________


# @router.message(F.text == "📜 Перегляд кодів")
# async def view_codes_handler(message: types.Message):
#     async with aiosqlite.connect(DB_PATH) as db:
#         cursor = await db.execute(
#             "SELECT id, casino_type, code, used FROM casino_codes"
#         )
#         codes = await cursor.fetchall()

#     if not codes:
#         await message.answer(
#             "⚠️ Немає жодного коду в базі.", reply_markup=main_menu(is_admin=True)
#         )
#         return

#     text_lines = ["📜 <b>Список кодів:</b>\n"]
#     for code_id, casino_type, code, used in codes:
#         status = "✅ використаний" if used else "🆓 вільний"
#         text_lines.append(f"<b>{casino_type}</b> — <code>{code}</code> — {status}")
#     text = "\n".join(text_lines)

#     keyboard = ReplyKeyboardMarkup(
#         keyboard=[
#             [KeyboardButton(text="🧹 Очистити всі коди")],
#             [KeyboardButton(text="⬅️ Назад в адмінку")],
#         ],
#         resize_keyboard=True,
#     )

#     await message.answer(text, parse_mode="HTML", reply_markup=keyboard)

@router.message(F.text == "📜 Перегляд кодів")
async def view_codes_handler(message: types.Message):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT id, casino_type, code, used FROM casino_codes"
        )
        codes = await cursor.fetchall()

    if not codes:
        await message.answer(
            "⚠️ Немає жодного коду в базі.", reply_markup=main_menu(is_admin=True)
        )
        return

    total = len(codes)
    used_count = sum(1 for _, _, _, used in codes if used)
    free_count = total - used_count
    total_price = free_count * 30

    text_lines = ["📜 <b>Список кодів:</b>\n"]
    for code_id, casino_type, code, used in codes:
        status = "✅ використаний" if used else "🆓 вільний"
        text_lines.append(f"<b>{casino_type}</b> — <code>{code}</code> — {status}")

    text_lines.append(f"\n📊 <b>Всього:</b> {total} | 🆓 Вільних: {free_count} | ✅ Використаних: {used_count}")
    text_lines.append(f"💰 <b>Вартість вільних кодів:</b> {total_price} грн")

    text = "\n".join(text_lines)

    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🗑 Видалити використані коди")],
            [KeyboardButton(text="🧹 Очистити всі коди")],
            [KeyboardButton(text="⬅️ Назад в адмінку")],
        ],
        resize_keyboard=True,
    )

    await message.answer(text, parse_mode="HTML", reply_markup=keyboard)


@router.message(F.text == "🗑 Видалити використані коди")
async def ask_delete_used_codes(message: types.Message):
    confirm_keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="✅ Так, видалити використані"),
                KeyboardButton(text="❌ Ні, скасувати"),
            ],
        ],
        resize_keyboard=True,
    )
    await message.answer(
        "⚠️ Видалити всі <b>використані</b> коди?",
        parse_mode="HTML",
        reply_markup=confirm_keyboard,
    )


@router.message(F.text == "✅ Так, видалити використані")
async def delete_used_codes(message: types.Message):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM casino_codes WHERE used = 1")
        (count,) = await cursor.fetchone()
        await db.execute("DELETE FROM casino_codes WHERE used = 1")
        await db.commit()

    await message.answer(
        f"🗑 Видалено <b>{count}</b> використаних кодів.",
        parse_mode="HTML",
        reply_markup=main_menu(is_admin=True)
    )

    
@router.message(F.text == "🧹 Очистити всі коди")
async def ask_clear_codes(message: types.Message):
    confirm_keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="✅ Так, очистити"),
                KeyboardButton(text="❌ Ні, скасувати"),
            ],
        ],
        resize_keyboard=True,
    )
    await message.answer(
        "⚠️ Ви впевнені, що хочете <b>очистити всі коди</b>?",
        parse_mode="HTML",
        reply_markup=confirm_keyboard,
    )


@router.message(F.text == "✅ Так, очистити")
async def clear_all_codes(message: types.Message):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM casino_codes")
        await db.commit()

    await message.answer(
        "🧹 Усі коди успішно видалено!", reply_markup=main_menu(is_admin=True)
    )


@router.message(F.text == "❌ Ні, скасувати")
async def cancel_clear_codes(message: types.Message):
    await message.answer(
        "❌ Очищення скасовано.", reply_markup=main_menu(is_admin=True)
    )


@router.message(F.text == "⬅️ Назад в адмінку")
async def back_to_admin(message: types.Message):
    await message.answer(
        "🔧 Повернення в адмін-меню:", reply_markup=main_menu(is_admin=True)
    )


from aiogram import Router, F, types
from aiogram.types import FSInputFile
from handlers.config import ADMIN_ID
from pathlib import Path


@router.message(F.text == "📦 Скачати БД")
async def download_db(message: types.Message):
    """Відправляє адміну файл бази даних users.db"""
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ Ця команда доступна лише адміну.")
        return

    # Шукаємо базу за кількома можливими шляхами
    possible_paths = [
        Path("/data/users.db"),                                    # Railway volume (абсолютний)
        Path(__file__).resolve().parent.parent / "data" / "users.db",  # відносний "data/users.db"
        Path(__file__).resolve().parent.parent / "users.db",       # старий варіант (для Hetzner)
    ]

    db_path = next((p for p in possible_paths if p.exists()), None)

    if db_path is None:
        await message.answer(
            "⚠️ Файл бази даних не знайдено. Перевірені шляхи:\n"
            + "\n".join(str(p) for p in possible_paths)
        )
        return

    await message.answer("⏳ Готую базу даних до відправки...")
    await message.answer_document(
        FSInputFile(db_path), caption=f"📦 База даних користувачів\n📍 {db_path}"
    )