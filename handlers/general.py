import re
import random
from pathlib import Path
from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import FSInputFile
from menu import actions_menu, main_menu
from db import has_claimed_gift
import config
from games import games_menu as imported_games_menu

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
    await message.answer(config.CARD_NUMBER)


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
    audio_path = Path(__file__).parent.parent / "audio" / "promo_cash.mp3"
    await callback.message.answer_audio(
        FSInputFile(audio_path), title="Промокоди — твій ключ до виграшу!"
    )
    await callback.answer()


# ==========================
# КОД в посилання
# ==========================
class CodeLinkFSM:
    waiting_for_code = "waiting_for_code"


@router.message(F.text == "💫 КОД в посилання")
async def ask_code_for_links(message: types.Message, state: FSMContext):
    await state.set_state(CodeLinkFSM.waiting_for_code)
    await message.answer("Введіть код у форматі: 00-00-00-00-00-00-00")


@router.message(lambda message: re.fullmatch(r"\d{2}(-\d{2}){6}", message.text or ""))
async def global_code_to_links(message: types.Message):
    code = (message.text or "").replace("-", "")
    await message.answer(f"Чемпіон https://spinplanet.net/?login_code={code}")
    await message.answer(f"Суперматік https://code.greenhost.pw/?c={code}")


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
