
import time
import json
import logging
from html import escape
from pathlib import Path
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import monobank
from handlers.config import (
    ADMIN_ID,
    GPT_MAX_TIME_DIFFERENCE_MINUTES,
    MAX_RECEIPT_FILE_SIZE_MB,
    MONO_ACCOUNT,
    MONO_CARD,
    MONO_JAR_CARD,
    MONO_JAR_LINK,
    MONO_TOKEN,
    OPENAI_API_KEY,
    OPENAI_MODEL,
    OPENAI_TIMEOUT_SECONDS,
)
from db import (
    get_balance,
    add_pending_payment,
    get_pending_payments,
    remove_pending_payment,
    add_to_balance,
    mark_tx_used,
    is_tx_used,
    add_payment_log,
    mark_referral_paid,
    update_daily_net,
    get_cards,
    create_manual_payment,
    delete_pending_manual_payment,
    get_pending_manual_payment_for_retry,
    update_pending_manual_payment_receipt,
    review_manual_payment,
    has_recent_manual_payment,
    set_manual_payment_route,
    register_receipt_fingerprints,
    save_manual_payment_analysis,
    mark_manual_payment_analysis_started,
)
from handlers.menu import main_menu
from services.receipt_analyzer import (
    PaymentReceiptAnalysis,
    ReceiptFileTooLarge,
    UnsupportedReceiptFile,
    analyze_receipt_with_openai,
    download_and_prepare_receipt,
    evaluate_auto_approval,
)

import asyncio

# Налаштування автоматичної перевірки поповнень.
# Змініть ці значення тут, якщо потрібні інші обмеження.
MINUTES_BETWEEN_PAYMENT_REQUESTS = 0
MAX_AMOUNT_FOR_GPT_CHECK = 5000

# user_id -> asyncio.Lock. Паралельні натискання "Перевірити" від одного
# користувача виконуються послідовно, а не одночасно.
_payment_locks: dict[int, asyncio.Lock] = {}
_manual_receipt_locks: dict[int, asyncio.Lock] = {}
router = Router(name="wallet")

MIN_SUM = 200
REFERRAL_BONUS = 50

KYIV_OFFSET = timedelta(hours=3)
KYIV_ZONE = ZoneInfo("Europe/Kyiv")

# Розклад автооплати: з 22:00 до 09:00 (Київ)
AUTO_TOPUP_START_HOUR = 22
AUTO_TOPUP_END_HOUR = 9

# ==================== РЕЖИМ АВТООПЛАТИ (керування адміном) ====================

AUTOPAY_MODE_AUTO = "auto"           # за розкладом 22:00–09:00
AUTOPAY_MODE_FORCE_ON = "force_on"   # адмін примусово увімкнув автооплату
AUTOPAY_MODE_FORCE_OFF = "force_off" # адмін примусово вимкнув автооплату (ручний режим)

_SETTINGS_FILE = Path(__file__).resolve().parent.parent / "data" / "wallet_settings.json"


def _load_autopay_mode() -> str:
    try:
        if _SETTINGS_FILE.exists():
            data = json.loads(_SETTINGS_FILE.read_text(encoding="utf-8"))
            mode = data.get("autopay_mode", AUTOPAY_MODE_AUTO)
            if mode in (AUTOPAY_MODE_AUTO, AUTOPAY_MODE_FORCE_ON, AUTOPAY_MODE_FORCE_OFF):
                return mode
    except Exception as e:
        logging.error(f"❌ Не вдалося прочитати wallet_settings.json: {e}")
    return AUTOPAY_MODE_AUTO


def _save_autopay_mode(mode: str) -> None:
    try:
        _SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        _SETTINGS_FILE.write_text(json.dumps({"autopay_mode": mode}), encoding="utf-8")
    except Exception as e:
        logging.error(f"❌ Не вдалося зберегти wallet_settings.json: {e}")


_autopay_mode: str = _load_autopay_mode()


def _mode_label(mode: str) -> str:
    return {
        AUTOPAY_MODE_AUTO: "🕒 За розкладом (22:00–09:00)",
        AUTOPAY_MODE_FORCE_ON: "✅ Примусово УВІМКНЕНО",
        AUTOPAY_MODE_FORCE_OFF: "🚫 Примусово ВИМКНЕНО (ручний режим)",
    }.get(mode, mode)


def is_auto_topup_time() -> bool:
    """
    True, якщо зараз доступна автоплата через бота.
    Враховує ручний режим адміна (force_on / force_off),
    інакше — розклад 22:00–09:00 за Києвом.
    """
    if _autopay_mode == AUTOPAY_MODE_FORCE_ON:
        return True
    if _autopay_mode == AUTOPAY_MODE_FORCE_OFF:
        return False

    now_kyiv = datetime.utcnow() + KYIV_OFFSET
    hour = now_kyiv.hour
    # проміжок переходить через північ: 22:00 -> 09:00
    return hour >= AUTO_TOPUP_START_HOUR or hour < AUTO_TOPUP_END_HOUR


class WalletStates(StatesGroup):
    enter_amount = State()
    upload_receipt = State()


# ==================== МЕНЮ ГАМАНЦЯ ====================
@router.message(F.text.in_({"💰 Гаманець", "Гаманець"}))
async def wallet_menu(message: Message):
    balance = await get_balance(message.from_user.id)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"Баланс: {balance} грн", callback_data="wallet_balance"
                )
            ],
            [
                InlineKeyboardButton(
                    text="Поповнити баланс", callback_data="wallet_topup"
                )
            ],
        ]
    )
    await message.answer(f"💰 Ваш гаманець\nБаланс: {balance} грн", reply_markup=kb)


# ==================== ПОПОВНЕННЯ ====================
@router.callback_query(F.data == "wallet_topup")
async def start_topup(callback: CallbackQuery, state: FSMContext):
    cancel_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❌ Скасувати", callback_data="wallet_cancel")]
        ]
    )
    await callback.message.answer(
        f"Введіть суму поповнення в гривнях (від {MIN_SUM} грн):",
        reply_markup=cancel_kb,
    )
    await state.update_data(
        topup_mode="auto" if is_auto_topup_time() else "manual"
    )
    await state.set_state(WalletStates.enter_amount)
    await callback.answer()


@router.callback_query(F.data == "wallet_cancel")
async def cancel_topup(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Поповнення скасовано.")
    await callback.answer()



@router.message(WalletStates.enter_amount)
async def process_amount(message: Message, state: FSMContext):
    cancel_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❌ Скасувати", callback_data="wallet_cancel")]
        ]
    )
    try:
        amount_grn = int(message.text)
        if amount_grn < MIN_SUM:
            await message.answer(f"❌ Мінімум {MIN_SUM} грн", reply_markup=cancel_kb)
            return
    except Exception:
        await message.answer("Введи суму поповнення або скасуй платіж", reply_markup=cancel_kb)
        return

    state_data = await state.get_data()
    if state_data.get("topup_mode") == "manual":
        cards = await get_cards()
        cards_text = "\n\n".join(
            f"🏦 {escape(bank)}: <code>{escape(number)}</code>"
            for bank, number in cards
            if number
        ) or "Реквізити тимчасово недоступні."

        await state.update_data(manual_amount=amount_grn)
        await state.set_state(WalletStates.upload_receipt)
        receipt_keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="⚠️ Не можу надіслати квитанцію",
                        callback_data="wallet_no_receipt",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="❌ Скасувати",
                        callback_data="wallet_cancel",
                    )
                ],
            ]
        )
        await message.answer(
            f"💰 <b>Поповнення на {amount_grn} грн</b>\n\n"
            f"Зробіть переказ <b>точно на {amount_grn} грн</b> "
            f"на одну з карток:\n\n"
            f"{cards_text}\n\n"
            f"📸 Після переказу надішліть сюди скриншот оплати.\n"
            f"Заявка буде передана адміністратору на перевірку.",
            parse_mode="HTML",
            reply_markup=receipt_keyboard,
        )
        return

    amount_kop = amount_grn * 100

    payment_id = f"PAYMENT:{int(time.time())}:{message.from_user.id}:{int(time.time() * 1000) % 10000}"

    await add_pending_payment(message.from_user.id, amount_kop, payment_id)

    logging.info(
        f"📤 НОВИЙ ПЛАТІЖ СТВОРЕНИЙ | user_id={message.from_user.id} | "
        f"sum={amount_grn} грн | payment_id='{payment_id}'"
    )


    text = (
        f"💰 Поповнення на <b>{amount_grn} грн</b>\n\n"
        f"Перекажіть <b>точно</b> цю суму на БАНКУ Monobank:\n\n"
        f"За посиланням: {MONO_JAR_LINK}\n\n"
        f"Чи на карту : <code>{MONO_JAR_CARD}</code>\n\n"
        f"❗Після оплати натисни кнопку «Перевірити платіж»"
    )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Перевірити платіж", callback_data="wallet_check"
                )
            ]
        ]
    )

    await message.answer(text, reply_markup=kb, parse_mode="HTML")
    await state.clear()


def _manual_payment_keyboard(payment_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Підтвердити",
                    callback_data=f"manualpay:approve:{payment_id}",
                ),
                InlineKeyboardButton(
                    text="❌ Відхилити",
                    callback_data=f"manualpay:reject:{payment_id}",
                ),
            ]
        ]
    )


def _retry_receipt_keyboard(payment_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔄 Надіслати іншу квитанцію",
                    callback_data=f"wallet_retry_receipt:{payment_id}",
                )
            ]
        ]
    )


def _payment_user_block(user, payment_id: int, amount: int) -> str:
    username = f"@{escape(user.username)}" if user.username else "немає"
    user_link = (
        f'<a href="tg://user?id={user.id}">{escape(user.full_name)}</a>'
    )
    return (
        f"🧾 <b>Заявка на поповнення №{payment_id}</b>\n\n"
        f"👤 {user_link}\n"
        f"🔗 {username}\n"
        f"🆔 <code>{user.id}</code>\n"
        f"💰 Сума: <b>{amount} грн</b>"
    )


def _analysis_admin_text(analysis: PaymentReceiptAnalysis | None) -> str:
    if analysis is None:
        return ""
    found_amount = (
        f"{analysis.amount_found} грн" if analysis.amount_found is not None else "не знайдено"
    )
    card = (
        f"**** {escape(analysis.recipient_card_last4)}"
        if analysis.recipient_card_last4
        else "не знайдено"
    )
    payment_time = escape(analysis.payment_datetime or "не визначено")
    return (
        f"\n\n🤖 <b>Результат автоматичної перевірки</b>\n"
        f"Рішення: ручна перевірка\n"
        f"Впевненість: {analysis.confidence:.0%}\n"
        f"Знайдена сума: {found_amount}\n"
        f"Картка: {card}\n"
        f"Час: {payment_time}"
    )


async def _send_receipt_to_admin(
    bot,
    *,
    receipt_type: str,
    receipt_file_id: str,
    text: str,
    keyboard: InlineKeyboardMarkup | None,
) -> None:
    if receipt_type == "photo":
        await bot.send_photo(
            ADMIN_ID,
            photo=receipt_file_id,
            caption=text,
            parse_mode="HTML",
            reply_markup=keyboard,
        )
    else:
        await bot.send_document(
            ADMIN_ID,
            document=receipt_file_id,
            caption=text,
            parse_mode="HTML",
            reply_markup=keyboard,
        )


async def _route_payment_to_manual_review(
    message: Message,
    *,
    payment_id: int,
    amount: int,
    receipt_type: str,
    receipt_file_id: str,
    reason: str,
    analysis: PaymentReceiptAnalysis | None = None,
    offer_retry: bool = False,
) -> None:
    await set_manual_payment_route(payment_id, reason)
    caption = (
        f"{_payment_user_block(message.from_user, payment_id, amount)}\n\n"
        f"⚠️ <b>Передано на ручну перевірку</b>\n"
        f"Причина: {escape(reason)}"
        f"{_analysis_admin_text(analysis)}"
    )
    keyboard = _manual_payment_keyboard(payment_id)
    try:
        await _send_receipt_to_admin(
            message.bot,
            receipt_type=receipt_type,
            receipt_file_id=receipt_file_id,
            text=caption,
            keyboard=keyboard,
        )
    except Exception:
        logging.exception(
            "Failed to send receipt media to admin | payment_id=%s", payment_id
        )
        await message.bot.send_message(
            ADMIN_ID,
            f"{caption}\n\n⚠️ Файл квитанції не вдалося прикріпити.",
            parse_mode="HTML",
            reply_markup=keyboard,
        )
    logging.info(
        "Manual payment routed to admin | payment_id=%s user_id=%s amount=%s reason=%s",
        payment_id,
        message.from_user.id,
        amount,
        reason,
    )
    retry_available = False
    if offer_retry:
        retry_available = bool(
            await get_pending_manual_payment_for_retry(
                payment_id, message.from_user.id
            )
        )
    if retry_available:
        await message.answer(
            f"⚠️ Автоматична перевірка не змогла підтвердити квитанцію.\n\n"
            f"На квитанції має бути чітко видно:\n"
            f"• <b>час переказу</b>;\n"
            f"• <b>картку, на яку зроблено переказ</b>;\n"
            f"• <b>суму переказу — {amount} грн</b>.\n\n"
            f"Ви можете надіслати іншу квитанцію або нічого не робити й "
            f"зачекати на підтвердження адміністратора.",
            parse_mode="HTML",
            reply_markup=_retry_receipt_keyboard(payment_id),
        )
    else:
        await message.answer(
            f"✅ Квитанцію передано адміністратору.\n\n"
            f"💰 Сума: <b>{amount} грн</b>\n"
            f"⏳ Очікуйте підтвердження платежу.",
            parse_mode="HTML",
        )


async def _send_auto_approval_to_admin(
    message: Message,
    *,
    payment_id: int,
    amount: int,
    receipt_type: str,
    receipt_file_id: str,
    analysis: PaymentReceiptAnalysis,
    computed_time_difference: int,
) -> None:
    card = escape(analysis.recipient_card_last4 or "—")
    operation_time = escape(analysis.payment_datetime or "—")
    caption = (
        f"🤖 <b>Платіж автоматично підтверджено</b>\n\n"
        f"{_payment_user_block(message.from_user, payment_id, amount)}\n"
        f"💳 Картка: **** {card}\n"
        f"🕐 Час операції: {operation_time}\n"
        f"⏱ Різниця: {computed_time_difference} хв\n"
        f"📊 Впевненість GPT: {analysis.confidence:.0%}"
    )
    try:
        await _send_receipt_to_admin(
            message.bot,
            receipt_type=receipt_type,
            receipt_file_id=receipt_file_id,
            text=caption,
            keyboard=None,
        )
    except Exception:
        logging.exception(
            "Failed to attach auto-approved receipt | payment_id=%s", payment_id
        )
        await message.bot.send_message(
            ADMIN_ID,
            f"{caption}\n\n⚠️ Файл квитанції не вдалося прикріпити.",
            parse_mode="HTML",
        )


async def _process_manual_receipt(
    message: Message,
    *,
    amount: int,
    receipt_type: str,
    receipt_file_id: str,
    declared_file_size: int | None,
    payment_id: int | None = None,
) -> None:
    is_retry = payment_id is not None
    if payment_id is None:
        payment_id = await create_manual_payment(
            user_id=message.from_user.id,
            username=message.from_user.username,
            full_name=message.from_user.full_name,
            amount=amount,
            receipt_file_id=receipt_file_id,
            receipt_type=receipt_type,
        )
        logging.info(
            "Manual payment created | payment_id=%s user_id=%s amount=%s",
            payment_id,
            message.from_user.id,
            amount,
        )

    if is_retry:
        updated = await update_pending_manual_payment_receipt(
            payment_id,
            message.from_user.id,
            receipt_file_id,
            receipt_type,
        )
        if not updated:
            await message.answer(
                "ℹ️ Іншу квитанцію для цієї заявки вже було надіслано або "
                "заявку вже розглянув адміністратор.",
                reply_markup=main_menu(),
            )
            return
        logging.info(
            "Manual payment receipt replaced | payment_id=%s user_id=%s",
            payment_id,
            message.from_user.id,
        )

    try:
        prepared = await download_and_prepare_receipt(
            message.bot,
            receipt_file_id,
            declared_file_size,
            MAX_RECEIPT_FILE_SIZE_MB,
        )
    except (UnsupportedReceiptFile, ReceiptFileTooLarge) as error:
        await _route_payment_to_manual_review(
            message,
            payment_id=payment_id,
            amount=amount,
            receipt_type=receipt_type,
            receipt_file_id=receipt_file_id,
            reason=str(error),
            offer_retry=True,
        )
        return
    except Exception as error:
        logging.exception(
            "Receipt download failed | payment_id=%s user_id=%s",
            payment_id,
            message.from_user.id,
        )
        await _route_payment_to_manual_review(
            message,
            payment_id=payment_id,
            amount=amount,
            receipt_type=receipt_type,
            receipt_file_id=receipt_file_id,
            reason=f"помилка завантаження квитанції: {type(error).__name__}",
            offer_retry=True,
        )
        return

    duplicate = await register_receipt_fingerprints(
        payment_id,
        prepared.file_sha256,
        prepared.perceptual_hash,
    )
    if duplicate.get("duplicate"):
        duplicate_kind = "ідентична" if duplicate.get("kind") == "exact" else "дуже схожа"
        await _route_payment_to_manual_review(
            message,
            payment_id=payment_id,
            amount=amount,
            receipt_type=receipt_type,
            receipt_file_id=receipt_file_id,
            reason=(
                f"{duplicate_kind} квитанція вже була у заявці "
                f"№{duplicate.get('payment_id')}"
            ),
            offer_retry=True,
        )
        return

    if amount > MAX_AMOUNT_FOR_GPT_CHECK:
        await _route_payment_to_manual_review(
            message,
            payment_id=payment_id,
            amount=amount,
            receipt_type=receipt_type,
            receipt_file_id=receipt_file_id,
            reason=f"сума перевищує {MAX_AMOUNT_FOR_GPT_CHECK} грн",
        )
        return

    if await has_recent_manual_payment(
        message.from_user.id,
        payment_id,
        MINUTES_BETWEEN_PAYMENT_REQUESTS,
    ):
        await _route_payment_to_manual_review(
            message,
            payment_id=payment_id,
            amount=amount,
            receipt_type=receipt_type,
            receipt_file_id=receipt_file_id,
            reason=(
                f"повторна заявка протягом {MINUTES_BETWEEN_PAYMENT_REQUESTS} хвилин"
            ),
        )
        return

    cards = await get_cards()
    allowed_cards: list[dict[str, str]] = []
    for bank, number in cards:
        digits = "".join(character for character in (number or "") if character.isdigit())
        if len(digits) >= 4:
            allowed_cards.append({"bank": bank, "last4": digits[-4:]})
    if not allowed_cards:
        await _route_payment_to_manual_review(
            message,
            payment_id=payment_id,
            amount=amount,
            receipt_type=receipt_type,
            receipt_file_id=receipt_file_id,
            reason="у системі немає валідних дозволених карток",
        )
        return

    if not OPENAI_API_KEY:
        await _route_payment_to_manual_review(
            message,
            payment_id=payment_id,
            amount=amount,
            receipt_type=receipt_type,
            receipt_file_id=receipt_file_id,
            reason="OpenAI API не налаштований",
        )
        return

    await mark_manual_payment_analysis_started(payment_id)
    logging.info(
        "Starting GPT receipt analysis | payment_id=%s user_id=%s amount=%s model=%s",
        payment_id,
        message.from_user.id,
        amount,
        OPENAI_MODEL,
    )
    try:
        now_kyiv = datetime.now(KYIV_ZONE)
        analysis = await analyze_receipt_with_openai(
            api_key=OPENAI_API_KEY,
            model=OPENAI_MODEL,
            timeout_seconds=OPENAI_TIMEOUT_SECONDS,
            image=prepared,
            expected_amount=amount,
            allowed_cards=allowed_cards,
            now_kyiv=now_kyiv,
            max_time_difference_minutes=GPT_MAX_TIME_DIFFERENCE_MINUTES,
        )
        approved, code_reason, computed_difference = evaluate_auto_approval(
            analysis,
            expected_amount=amount,
            allowed_card_last4={card["last4"] for card in allowed_cards},
            now_kyiv=now_kyiv,
            max_time_difference_minutes=GPT_MAX_TIME_DIFFERENCE_MINUTES,
        )
        route_reason = "auto_approved" if approved else code_reason
        await save_manual_payment_analysis(
            payment_id,
            result_json=analysis.model_dump_json(),
            decision="approve" if approved else "manual_review",
            reason=code_reason,
            confidence=analysis.confidence,
            route_reason=route_reason,
        )
        logging.info(
            "GPT receipt result | payment_id=%s user_id=%s amount=%s "
            "status=%s amount_found=%s card_last4=%s allowed_last4=%s confidence=%.3f "
            "model_decision=%s final=%s reason=%s",
            payment_id,
            message.from_user.id,
            amount,
            analysis.payment_status,
            analysis.amount_found,
            analysis.recipient_card_last4,
            sorted(card["last4"] for card in allowed_cards),
            analysis.confidence,
            analysis.decision,
            "approve" if approved else "manual_review",
            code_reason,
        )
    except Exception as error:
        logging.exception(
            "OpenAI receipt analysis failed | payment_id=%s user_id=%s error=%s",
            payment_id,
            message.from_user.id,
            type(error).__name__,
        )
        reason = f"помилка OpenAI: {type(error).__name__}"
        await save_manual_payment_analysis(
            payment_id,
            result_json=None,
            decision="manual_review",
            reason=reason,
            confidence=None,
            route_reason=reason,
        )
        await _route_payment_to_manual_review(
            message,
            payment_id=payment_id,
            amount=amount,
            receipt_type=receipt_type,
            receipt_file_id=receipt_file_id,
            reason=reason,
        )
        return

    if not approved:
        await _route_payment_to_manual_review(
            message,
            payment_id=payment_id,
            amount=amount,
            receipt_type=receipt_type,
            receipt_file_id=receipt_file_id,
            reason=code_reason,
            analysis=analysis,
            offer_retry=True,
        )
        return

    result = await review_manual_payment(
        payment_id,
        admin_id=0,
        decision="approved",
        review_source="gpt",
    )
    if not result.get("ok"):
        if result.get("reason") == "already_reviewed":
            await message.answer(
                "ℹ️ Адміністратор уже розглянув цю заявку.",
                reply_markup=main_menu(),
            )
            return
        logging.error(
            "Automatic credit failed | payment_id=%s user_id=%s reason=%s",
            payment_id,
            message.from_user.id,
            result.get("reason"),
        )
        await _route_payment_to_manual_review(
            message,
            payment_id=payment_id,
            amount=amount,
            receipt_type=receipt_type,
            receipt_file_id=receipt_file_id,
            reason=f"автоматичне зарахування не виконано: {result.get('reason')}",
            analysis=analysis,
        )
        return

    await message.answer(
        f"✅ Ваш платіж автоматично підтверджено!\n\n"
        f"💰 Зараховано: <b>{amount} грн</b>\n"
        f"💳 Баланс: <b>{result['balance']} грн</b>",
        parse_mode="HTML",
        reply_markup=main_menu(),
    )
    try:
        await _send_auto_approval_to_admin(
            message,
            payment_id=payment_id,
            amount=amount,
            receipt_type=receipt_type,
            receipt_file_id=receipt_file_id,
            analysis=analysis,
            computed_time_difference=computed_difference or 0,
        )
    except Exception:
        logging.exception(
            "Failed to notify admin about auto approval | payment_id=%s",
            payment_id,
        )
    logging.info(
        "Manual payment automatically credited | payment_id=%s user_id=%s amount=%s balance=%s",
        payment_id,
        message.from_user.id,
        amount,
        result["balance"],
    )


@router.message(WalletStates.upload_receipt)
async def receive_manual_receipt(message: Message, state: FSMContext):
    receipt_type: str | None = None
    receipt_file_id: str | None = None
    declared_file_size: int | None = None

    if message.photo:
        receipt_type = "photo"
        receipt_file_id = message.photo[-1].file_id
        declared_file_size = message.photo[-1].file_size
    elif message.document:
        receipt_type = "document"
        receipt_file_id = message.document.file_id
        declared_file_size = message.document.file_size

    if not receipt_file_id or not receipt_type:
        await message.answer(
            "❌ Надішліть квитанцію як фото або документ чи скористайтеся "
            "кнопкою «Не можу надіслати квитанцію»."
        )
        return

    data = await state.get_data()
    amount = data.get("manual_amount")
    retry_payment_id = data.get("retry_payment_id")
    if not amount:
        await state.clear()
        await message.answer("❌ Заявка застаріла. Почніть поповнення ще раз.")
        return

    lock = _manual_receipt_locks.setdefault(message.from_user.id, asyncio.Lock())
    if lock.locked():
        await message.answer("⏳ Ваша попередня квитанція вже обробляється.")
        return

    await state.clear()
    await message.answer("🔍 Квитанцію отримано. Перевіряю платіж...")
    async with lock:
        try:
            await _process_manual_receipt(
                message,
                amount=amount,
                receipt_type=receipt_type,
                receipt_file_id=receipt_file_id,
                declared_file_size=declared_file_size,
                payment_id=retry_payment_id,
            )
        except Exception:
            logging.exception(
                "Unexpected manual receipt error | user_id=%s amount=%s",
                message.from_user.id,
                amount,
            )
            await message.answer(
                "❌ Сталася непередбачена помилка. Зверніться до адміністратора."
            )
        finally:
            _manual_receipt_locks.pop(message.from_user.id, None)


@router.callback_query(F.data.startswith("wallet_retry_receipt:"))
async def retry_manual_receipt(callback: CallbackQuery, state: FSMContext):
    try:
        payment_id = int(callback.data.rsplit(":", 1)[1])
    except (AttributeError, ValueError, IndexError):
        await callback.answer("Некоректна заявка", show_alert=True)
        return

    payment = await get_pending_manual_payment_for_retry(
        payment_id, callback.from_user.id
    )
    if not payment:
        await state.clear()
        await callback.answer(
            "Цю заявку вже підтверджено або відхилено",
            show_alert=True,
        )
        return

    amount = payment["amount"]
    await state.update_data(
        manual_amount=amount,
        retry_payment_id=payment_id,
    )
    await state.set_state(WalletStates.upload_receipt)
    await callback.message.answer(
        f"📎 Надішліть іншу квитанцію для заявки №{payment_id} як фото "
        f"або документ.\n\n"
        f"На ній має бути чітко видно час, картку одержувача та "
        f"суму <b>{amount} грн</b>.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="❌ Скасувати",
                        callback_data="wallet_cancel",
                    )
                ]
            ]
        ),
    )
    await callback.answer("Надішліть нову квитанцію")


@router.callback_query(
    WalletStates.upload_receipt,
    F.data == "wallet_no_receipt",
)
async def submit_manual_payment_without_receipt(
    callback: CallbackQuery, state: FSMContext
):
    data = await state.get_data()
    amount = data.get("manual_amount")
    if not amount:
        await state.clear()
        await callback.answer("Заявка застаріла", show_alert=True)
        return

    payment_id = await create_manual_payment(
        user_id=callback.from_user.id,
        username=callback.from_user.username,
        full_name=callback.from_user.full_name,
        amount=amount,
        receipt_file_id="",
        receipt_type="none",
    )
    await set_manual_payment_route(payment_id, "квитанцію не надано")

    username = (
        f"@{escape(callback.from_user.username)}"
        if callback.from_user.username
        else "немає"
    )
    user_link = (
        f'<a href="tg://user?id={callback.from_user.id}">'
        f"{escape(callback.from_user.full_name)}</a>"
    )
    text = (
        f"🧾 <b>Нова заявка на поповнення №{payment_id}</b>\n\n"
        f"👤 {user_link}\n"
        f"🔗 {username}\n"
        f"🆔 <code>{callback.from_user.id}</code>\n"
        f"💰 Сума: <b>{amount} грн</b>\n\n"
        f"⚠️ <b>Квитанцію не надано</b>"
    )
    admin_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Підтвердити",
                    callback_data=f"manualpay:approve:{payment_id}",
                ),
                InlineKeyboardButton(
                    text="❌ Відхилити",
                    callback_data=f"manualpay:reject:{payment_id}",
                ),
            ]
        ]
    )

    try:
        await callback.bot.send_message(
            ADMIN_ID,
            text,
            parse_mode="HTML",
            reply_markup=admin_keyboard,
        )
    except Exception as error:
        await delete_pending_manual_payment(payment_id, callback.from_user.id)
        logging.error(
            f"❌ Не вдалося передати ручний платіж №{payment_id} адміну: {error}",
            exc_info=True,
        )
        await callback.answer("Помилка надсилання заявки", show_alert=True)
        return

    await state.clear()
    await callback.message.edit_text(
        f"✅ Заявку без квитанції надіслано адміністратору.\n\n"
        f"💰 Сума: <b>{amount} грн</b>\n"
        f"⏳ Очікуйте підтвердження платежу.",
        parse_mode="HTML",
    )
    await callback.answer("Заявку надіслано")


@router.callback_query(F.data.startswith("manualpay:"))
async def review_manual_topup(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Недостатньо прав", show_alert=True)
        return

    try:
        _, action, payment_id_raw = callback.data.split(":")
        payment_id = int(payment_id_raw)
    except (TypeError, ValueError):
        await callback.answer("Некоректна заявка", show_alert=True)
        return

    if action not in {"approve", "reject"}:
        await callback.answer("Некоректна дія", show_alert=True)
        return

    decision = "approved" if action == "approve" else "rejected"
    result = await review_manual_payment(payment_id, callback.from_user.id, decision)
    if not result.get("ok"):
        if result.get("reason") == "already_reviewed":
            status_label = (
                "підтверджено" if result.get("status") == "approved" else "відхилено"
            )
            await callback.answer(
                f"Цей платіж уже {status_label}", show_alert=True
            )
        else:
            await callback.answer("Заявку не знайдено", show_alert=True)
        return

    await callback.answer("Платіж оброблено")
    status_text = (
        "✅ <b>ПІДТВЕРДЖЕНО</b>" if decision == "approved"
        else "❌ <b>ВІДХИЛЕНО</b>"
    )
    try:
        if callback.message.caption is not None:
            await callback.message.edit_caption(
                caption=f"{escape(callback.message.caption)}\n\n{status_text}",
                parse_mode="HTML",
                reply_markup=None,
            )
        else:
            await callback.message.edit_text(
                f"{escape(callback.message.text or '')}\n\n{status_text}",
                parse_mode="HTML",
                reply_markup=None,
            )
    except Exception as error:
        logging.warning(f"Не вдалося оновити заявку №{payment_id}: {error}")

    user_id = result["user_id"]
    amount = result["amount"]
    try:
        if decision == "approved":
            await callback.bot.send_message(
                user_id,
                f"✅ Ваш платіж підтверджено!\n\n"
                f"💰 Зараховано: <b>{amount} грн</b>\n"
                f"💳 Баланс: <b>{result['balance']} грн</b>",
                parse_mode="HTML",
                reply_markup=main_menu(),
            )
        else:
            await callback.bot.send_message(
                user_id,
                f"❌ Платіж на суму <b>{amount} грн</b> відхилено.\n\n"
                f"Якщо це помилка, зверніться до касира.",
                parse_mode="HTML",
                reply_markup=main_menu(),
            )
    except Exception as error:
        logging.error(
            f"❌ Не вдалося повідомити користувача {user_id} "
            f"про ручний платіж №{payment_id}: {error}"
        )



@router.callback_query(F.data == "wallet_check")
@router.message(Command("check"))
async def check_payment(event: Message | CallbackQuery):
    if isinstance(event, CallbackQuery):
        message = event.message
        user_id = event.from_user.id
        await event.answer()
    else:
        message = event
        user_id = event.from_user.id

    if user_id not in _payment_locks:
        _payment_locks[user_id] = asyncio.Lock()
    lock = _payment_locks[user_id]

    if lock.locked():
        await message.answer("⏳ Платіж вже перевіряється, зачекай...")
        return

    async with lock:
        pending = await get_pending_payments()
        user_pending = [p for p in pending if p["user_id"] == user_id]
        if not user_pending:
            await message.answer("❌ Немає активних платежів.")
            return

        p = user_pending[0]
        target_amount_kop = p["amount_kop"]
        target_amount_grn = target_amount_kop // 100
        payment_id = p["comment"]

        await message.answer("🔍 Перевіряю платіж...")

        try:
            client = monobank.Client(token=MONO_TOKEN)
            from_date = datetime.now() - timedelta(days=7)
            statements = client.get_statements(MONO_ACCOUNT, from_date, datetime.now())

            time_window = 600
            best_match = None
            best_match_diff = float("inf")

            for tx in statements:
                tx_amount = tx.get("amount", 0)
                tx_time = tx.get("time", 0)
                tx_id = tx.get("id", "")

                try:
                    payment_timestamp = int(payment_id.split(":")[1])
                    time_diff = abs(tx_time - payment_timestamp)
                except:
                    time_diff = 0

                if await is_tx_used(tx_id):
                    continue

                if tx_amount == target_amount_kop and time_diff <= time_window and tx_amount > 0:
                    if time_diff < best_match_diff:
                        best_match = tx
                        best_match_diff = time_diff

            if not best_match:
                kb = InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="🔄 Перевірити платіж", callback_data="wallet_check")
                ]])
                await message.answer(
                    f"❌ Платіж ще не знайдено.\n\n"
                    f"✓ Відправив точно <b>{target_amount_grn} грн</b>\n"
                    f"✓ На правильну картку: <b>{MONO_JAR_CARD}</b>\n\n"
                    f"Почекай 1–2 хвилини і спробуй знову.",
                    parse_mode="HTML", reply_markup=kb
                )
                return

            # === Успішне зарахування ===
            tx = best_match
            tx_id = tx.get("id", "")

            reserved = await mark_tx_used(tx_id, user_id, target_amount_kop, payment_id)
            if not reserved:
                await message.answer("⚠️ Ця транзакція вже була зарахована.")
                return

            await add_to_balance(user_id, target_amount_grn)
            await update_daily_net(user_id, target_amount_grn)
            await remove_pending_payment(user_id)
            await add_payment_log(
                user_id=user_id,
                username=event.from_user.username or event.from_user.full_name,
                amount=target_amount_grn,
                comment=payment_id,
            )

            # Посилання на реферала
            referral_link = (
                f"@{event.from_user.username}" 
                if event.from_user.username 
                else f'<a href="tg://user?id={user_id}">{event.from_user.full_name}</a>'
            )

            # Сповіщення адміністратору про поповнення
            await message.bot.send_message(
                ADMIN_ID,
                f"💰 Нове поповнення балансу\n\n"
                f"👤 {referral_link}\n"
                f"💵 <b>{target_amount_grn} грн</b>\n"
                f"💳 Баланс: <b>{await get_balance(user_id)} грн</b>",
                parse_mode="HTML"
            )

            # Повідомлення користувачу
            play_kb = ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="🎮 Грати")]],
                resize_keyboard=True,
            )
            await message.answer(
                f"✅ Платіж зараховано!\n\n"
                f"💰 {target_amount_grn} грн\n"
                f"💳 Баланс: {await get_balance(user_id)} грн",
                reply_markup=play_kb,
                parse_mode="HTML"
            )

            # ====================== РЕФЕРАЛЬНИЙ БЛОК ======================
            referrer_id = await mark_referral_paid(user_id)
            logging.info(f"🔗 mark_referral_paid повернув referrer_id = {referrer_id}")

            if referrer_id and referrer_id != user_id:
                await add_to_balance(referrer_id, REFERRAL_BONUS)
                await update_daily_net(referrer_id, REFERRAL_BONUS)

                # Посилання на реферера
                referrer_link = f'<a href="tg://user?id={referrer_id}">{referrer_id}</a>'

                # Сповіщення рефереру
                try:
                    await message.bot.send_message(
                        referrer_id,
                        f"🎉 Ваш реферал поповнив баланс!\n\n"
                        f"👤 Користувач: {referral_link}\n"
                        f"💰 Вам нараховано <b>+{REFERRAL_BONUS} грн</b>",
                        parse_mode="HTML"
                    )
                except Exception as e:
                    logging.error(f"❌ Не вдалося відправити рефереру {referrer_id}: {e}")

                # Сповіщення адміністратору про видачу бонусу
                try:
                    await message.bot.send_message(
                        ADMIN_ID,
                        f"🎁 Реферальний бонус виданий!\n\n"
                        f"👤 Реферер: {referrer_link}\n"
                        f"👤 Реферал: {referral_link}\n"
                        f"💰 Бонус: <b>+{REFERRAL_BONUS} грн</b>",
                        parse_mode="HTML"
                    )
                except Exception as e:
                    logging.error(f"❌ Не вдалося відправити адміну про бонус: {e}")

            logging.info(f"✅ Поповнення успішно завершено для user {user_id}")

        except monobank.TooManyRequests:
            logging.warning(f"⚠️ Ліміт Monobank для user_id={user_id}")
            await message.answer("⏳ Ліміт запитів. Зачекай 60 секунд.")
        except Exception as e:
            logging.error(f"❌ Критична помилка в check_payment: {e}", exc_info=True)
            await message.answer("❌ Помилка при обробці платежу.")


# ==================== АДМІНКА: РУЧНЕ КЕРУВАННЯ АВТООПЛАТОЮ ====================

def autopay_admin_kb() -> InlineKeyboardMarkup:
    def mark(mode: str) -> str:
        return "🔘 " if _autopay_mode == mode else "⚪️ "

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text=f"{mark(AUTOPAY_MODE_AUTO)}🕒 За розкладом (22:00–09:00)",
                callback_data="autopay_mode_auto"
            )],
            [InlineKeyboardButton(
                text=f"{mark(AUTOPAY_MODE_FORCE_ON)}✅ Примусово увімкнути",
                callback_data="autopay_mode_on"
            )],
            [InlineKeyboardButton(
                text=f"{mark(AUTOPAY_MODE_FORCE_OFF)}🚫 Примусово вимкнути (ручний режим)",
                callback_data="autopay_mode_off"
            )],
        ]
    )


@router.message(F.text == "⚙️ Автооплата")
@router.message(Command("autopay"))
async def autopay_admin_menu(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer(
        f"⚙️ <b>Керування автооплатою</b>\n\n"
        f"Поточний режим: <b>{_mode_label(_autopay_mode)}</b>\n\n"
        f"Автооплата працює з 22:00 до 09:00"
        f"Можеш примусово перемкнути в будь-яку сторону — режим збережеться "
        f"навіть після перезапуску бота.",
        parse_mode="HTML",
        reply_markup=autopay_admin_kb(),
    )


@router.callback_query(F.data.startswith("autopay_mode_"))
async def set_autopay_mode(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer()
        return

    global _autopay_mode
    key = callback.data.removeprefix("autopay_mode_")
    mode_map = {
        "auto": AUTOPAY_MODE_AUTO,
        "on": AUTOPAY_MODE_FORCE_ON,
        "off": AUTOPAY_MODE_FORCE_OFF,
    }
    new_mode = mode_map.get(key, AUTOPAY_MODE_AUTO)
    _autopay_mode = new_mode
    _save_autopay_mode(new_mode)

    await callback.message.edit_text(
        f"⚙️ <b>Керування автооплатою</b>\n\n"
        f"Поточний режим: <b>{_mode_label(_autopay_mode)}</b>\n\n"
        f"За розкладом автоплата працює з 22:00 до 09:00 (Київ).",
        parse_mode="HTML",
        reply_markup=autopay_admin_kb(),
    )
    await callback.answer("✅ Збережено")
