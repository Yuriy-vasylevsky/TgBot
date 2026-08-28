from aiogram import F, Router, types
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from handlers.config import ADMIN_ID, DEEPSEEK_API_KEY, OPENAI_API_KEY
from services.receipt_analyzer import (
    RECEIPT_ANALYZER_DEEPSEEK,
    RECEIPT_ANALYZER_OPENAI,
    get_receipt_analyzer,
    set_receipt_analyzer,
)


router = Router(name="admin_receipt_analyzer")


def _analyzer_label(analyzer: str) -> str:
    return {
        RECEIPT_ANALYZER_OPENAI: "GPT (OpenAI)",
        RECEIPT_ANALYZER_DEEPSEEK: "DeepSeek V4 Flash Vision",
    }.get(analyzer, analyzer)


def _analyzer_ready(analyzer: str) -> bool:
    return (
        bool(DEEPSEEK_API_KEY)
        if analyzer == RECEIPT_ANALYZER_DEEPSEEK
        else bool(OPENAI_API_KEY)
    )


def _analyzer_keyboard(selected: str) -> InlineKeyboardMarkup:
    def button_text(analyzer: str) -> str:
        marker = "✅ " if analyzer == selected else ""
        unavailable = " ⚠️" if not _analyzer_ready(analyzer) else ""
        return f"{marker}{_analyzer_label(analyzer)}{unavailable}"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=button_text(RECEIPT_ANALYZER_OPENAI),
                    callback_data=f"receipt_analyzer:set:{RECEIPT_ANALYZER_OPENAI}",
                )
            ],
            [
                InlineKeyboardButton(
                    text=button_text(RECEIPT_ANALYZER_DEEPSEEK),
                    callback_data=f"receipt_analyzer:set:{RECEIPT_ANALYZER_DEEPSEEK}",
                )
            ],
        ]
    )


def _analyzer_text(selected: str, notice: str | None = None) -> str:
    readiness = "✅ API-ключ налаштований" if _analyzer_ready(selected) else "⚠️ API-ключ не налаштований"
    text = (
        "🧠 <b>Аналізатор квитанцій</b>\n\n"
        f"Поточний: <b>{_analyzer_label(selected)}</b>\n"
        f"Стан: {readiness}\n\n"
        "Вибір застосовується до наступних перевірок квитанцій. "
        "Ключі API тут не відображаються та не зберігаються."
    )
    return f"{notice}\n\n{text}" if notice else text


@router.message(F.text == "🧠 Аналізатор квитанцій")
async def open_receipt_analyzer(message: types.Message) -> None:
    if message.from_user.id != ADMIN_ID:
        return
    selected = get_receipt_analyzer()
    await message.answer(
        _analyzer_text(selected),
        parse_mode="HTML",
        reply_markup=_analyzer_keyboard(selected),
    )


@router.callback_query(F.data.startswith("receipt_analyzer:set:"))
async def select_receipt_analyzer(callback: types.CallbackQuery) -> None:
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Немає доступу", show_alert=True)
        return

    analyzer = callback.data.rsplit(":", 1)[-1]
    try:
        set_receipt_analyzer(analyzer)
    except ValueError:
        await callback.answer("Невідомий аналізатор", show_alert=True)
        return

    notice = f"✅ Обрано: <b>{_analyzer_label(analyzer)}</b>."
    if not _analyzer_ready(analyzer):
        notice += "\n⚠️ Додайте API-ключ у .env та перезапустіть бота."
    try:
        await callback.message.edit_text(
            _analyzer_text(analyzer, notice),
            parse_mode="HTML",
            reply_markup=_analyzer_keyboard(analyzer),
        )
    except TelegramBadRequest as error:
        if "message is not modified" not in str(error).lower():
            raise
    await callback.answer("Налаштування збережено")
