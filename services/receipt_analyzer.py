import asyncio
import base64
import hashlib
import io
import re
import warnings
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

import imagehash
from aiogram import Bot
from openai import AsyncOpenAI
from PIL import Image, ImageEnhance, ImageFilter, ImageOps, UnidentifiedImageError
from pydantic import BaseModel, ConfigDict, Field


KYIV_ZONE = ZoneInfo("Europe/Kyiv")
SUPPORTED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP"}
CARD_MISMATCH_REASON = (
    "картка одержувача не збігається або її не вдалось правильно розпізнати"
)
CANCELLABLE_PAYMENT_REASON = "платіж ще можна скасувати"


class UnsupportedReceiptFile(ValueError):
    pass


class ReceiptFileTooLarge(ValueError):
    pass


class CardCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["recipient", "sender", "unknown"]
    visible_suffix: str
    context_label: str
    evidence_text: str


class PaymentReceiptAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_payment_receipt: bool
    document_type: Literal[
        "payment_receipt",
        "transfer_success_screen",
        "payment_details_screen",
        "bank_notification",
        "other",
    ]
    payment_status: Literal[
        "successful", "processing", "rejected", "cancelled", "failed", "unknown"
    ]
    payment_status_visible_text: str | None
    payment_can_be_cancelled: bool
    cancellation_visible_text: str | None
    amount_found: int | None
    card_candidates: list[CardCandidate]
    visible_card_number_suffixes: list[str]
    recipient_card_suffix: str | None
    payment_datetime: str | None
    payment_time_source: Literal["operation", "phone_status_bar", "not_visible"]
    payment_time_visible_text: str | None
    image_is_readable: bool
    possible_editing: bool
    confidence: float = Field(ge=0, le=1)
    reason: str


@dataclass(frozen=True)
class PreparedReceipt:
    image_bytes: bytes
    mime_type: str
    file_sha256: str
    perceptual_hash: str


def _normalize_image(original_bytes: bytes) -> PreparedReceipt:
    file_sha256 = hashlib.sha256(original_bytes).hexdigest()
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(original_bytes)) as source:
                source.load()
                if (source.format or "").upper() not in SUPPORTED_IMAGE_FORMATS:
                    raise UnsupportedReceiptFile(
                        f"Непідтримуваний формат зображення: {source.format or 'unknown'}"
                    )
                image = ImageOps.exif_transpose(source).convert("RGB")
    except (
        UnidentifiedImageError,
        OSError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as error:
        raise UnsupportedReceiptFile("Файл не є підтримуваним зображенням") from error

    perceptual_hash = str(imagehash.phash(image))

    # Обмежуємо надмірні розміри, не спотворюючи пропорції квитанції.
    image.thumbnail((4096, 4096), Image.Resampling.LANCZOS)
    longest_side = max(image.size)
    if longest_side < 2000:
        scale = min(3.0, 2000 / longest_side)
        image = image.resize(
            (round(image.width * scale), round(image.height * scale)),
            Image.Resampling.LANCZOS,
        )
    image = ImageOps.autocontrast(image, cutoff=1)
    image = ImageEnhance.Contrast(image).enhance(1.08)
    image = image.filter(ImageFilter.UnsharpMask(radius=1.2, percent=115, threshold=3))
    output = io.BytesIO()
    image.save(output, format="JPEG", quality=92, optimize=True)
    return PreparedReceipt(
        image_bytes=output.getvalue(),
        mime_type="image/jpeg",
        file_sha256=file_sha256,
        perceptual_hash=perceptual_hash,
    )


async def download_and_prepare_receipt(
    bot: Bot,
    file_id: str,
    declared_file_size: int | None,
    max_file_size_mb: int,
) -> PreparedReceipt:
    max_bytes = max_file_size_mb * 1024 * 1024
    if declared_file_size is not None and declared_file_size > max_bytes:
        raise ReceiptFileTooLarge(
            f"Файл перевищує дозволені {max_file_size_mb} МБ"
        )

    telegram_file = await bot.get_file(file_id)
    if not telegram_file.file_path:
        raise UnsupportedReceiptFile("Telegram не повернув шлях до файла")

    buffer = io.BytesIO()
    await bot.download_file(telegram_file.file_path, destination=buffer)
    original_bytes = buffer.getvalue()
    if not original_bytes:
        raise UnsupportedReceiptFile("Отримано порожній файл")
    if len(original_bytes) > max_bytes:
        raise ReceiptFileTooLarge(
            f"Файл перевищує дозволені {max_file_size_mb} МБ"
        )

    return await asyncio.to_thread(_normalize_image, original_bytes)


async def analyze_receipt_with_openai(
    *,
    api_key: str,
    model: str,
    timeout_seconds: int,
    image: PreparedReceipt,
    now_kyiv: datetime,
) -> PaymentReceiptAnalysis:
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY не налаштований")

    prompt = f"""
Прочитай фактичні дані з банківської квитанції або екрана переказу.
Ти не знаєш очікуваної суми чи дозволених карток. Нічого не порівнюй і не
підставляй: повертай лише те, що справді видно на зображенні.

Поточний час Europe/Kyiv: {now_kyiv.isoformat()}

Правила:
- document_type="payment_receipt" став для окремої платіжної квитанції з
  реквізитами операції;
- для екрана банківського застосунку «переказ виконано/успішно» використовуй
  transfer_success_screen, а для сторінки з деталями конкретної операції —
  payment_details_screen;
- bank_notification використовуй лише для окремого push-сповіщення без
  відкритого екрана конкретного платежу; головний екран застосунку та сторонні
  зображення позначай other;
- дослівно перепиши видимий статус операції у payment_status_visible_text;
  якщо окремого статусу не видно, поверни null;
- написи «Виконано успішно», «Операцію виконано успішно», «Платіж успішний»,
  «Переказ успішний» та рівнозначні однозначно означають
  payment_status="successful". Не став unknown лише через те, що це
  сформована банком квитанція без окремої зеленої позначки;
- «В обробці»/«Очікує» означає processing, «Відхилено» — rejected,
  «Скасовано» — cancelled, а «Помилка»/«Не виконано» — failed;
- уважно переглянь усе зображення, особливо кнопки внизу. Якщо видно дію
  «Скасувати платіж», «Скасувати переказ», «Відкликати платіж»,
  «Отменить платеж/перевод», «Cancel payment», «Undo transfer» або аналогічну
  можливість повернути чи скасувати операцію, постав
  payment_can_be_cancelled=true і дослівно перепиши напис у
  cancellation_visible_text;
- якщо можливості скасування ніде не видно, постав
  payment_can_be_cancelled=false та cancellation_visible_text=null;
- amount_found — фактична сума переказу цілим числом; знак мінус збережи,
  якщо він показаний біля вибраної суми;
- спочатку знайди КОЖНУ видиму картку або платіжний інструмент і додай її до
  card_candidates. Для кожної вкажи role, лише фактично видиме закінчення,
  точний найближчий підпис у context_label та короткий дослівний фрагмент у
  evidence_text;
- не пропускай загальні поля «Картка», «Номер картки», «Карта», masked card
  або 16-значний номер лише тому, що біля них не вказана роль. Додай такий
  номер до card_candidates з role="unknown";
- у visible_card_number_suffixes окремо поверни закінчення КОЖНОГО видимого
  карткового номера незалежно від його ролі. Обов'язково перевір текст після
  «Призначення платежу», «Поповнення картки», «Пополнение карты»: 16-значний
  номер у цьому або наступному рядку є номером картки й не може бути
  пропущений;
- не додавай у visible_card_number_suffixes телефон, IBAN із префіксом UA,
  номер квитанції, код операції, ЄДРПОУ чи інші службові ідентифікатори;
- у visible_card_number_suffixes повертай лише реально видимі останні 2–4
  цифри кожної картки; якщо видно повний або маскований номер — поверни його
  останні 4 цифри;
- role="recipient" використовуй тільки коли поруч явно написано
  «Отримувач», «Одержувач», «Отримувач переказу», «Картка отримувача»,
  «На картку», recipient або beneficiary. Поля «номер платіжного інструмента
  отримувача», «номер електронного гаманця отримувача», «рахунок отримувача»
  та «повний номер ... отримувача» також завжди позначай role="recipient";
- role="sender" використовуй для «Платник», «Відправник», «З картки»,
  «Картка списання», sender або payer. Якщо роль не підтверджена підписом,
  використовуй unknown;
- recipient_card_suffix бери лише з реквізитів отримувача: полів
  «Отримувач», «Отримувач переказу», «Картка отримувача», «На картку» або
  аналогічних за змістом;
- якщо 16-значний номер стоїть після підпису «номер рахунку/унікальний
  (повний) номер платіжного інструменту/номер електронного гаманця
  отримувача», це платіжний інструмент ОТРИМУВАЧА: обов'язково додай його до
  card_candidates та поверни його видимі останні цифри у
  recipient_card_suffix;
- у context_label повертай тільки найближчий підпис конкретного номера. Не
  додавай до нього поля «Платник», «Телефон платника» чи інші сусідні рядки,
  якщо вони описують інші реквізити;
- не використовуй для recipient_card_suffix картку платника, відправника,
  картку списання, «З картки» чи номер рахунку платника;
- якщо видно кілька карток, обов'язково розрізни відправника й отримувача та
  поверни закінчення саме картки отримувача; воно має повністю збігатися з
  visible_suffix одного card_candidates з role="recipient";
- якщо картку отримувача визначити неможливо, поверни null, а не номер
  картки відправника;
- для recipient_card_suffix поверни лише видимі кінцеві цифри картки
  отримувача без пробілів і маски ****: зазвичай це 4 цифри, але якщо банк
  показує тільки 2 або 3, поверни саме ці 2 або 3 цифри;
- ніколи не доповнюй дві видимі цифри до чотирьох і не домислюй
  нерозбірливі цифри;
- для payment_datetime спочатку використовуй дату й час самої операції;
- payment_datetime завжди нормалізуй у ISO 8601: YYYY-MM-DDTHH:MM:SS+HH:MM;
- payment_time_source="operation" дозволено лише коли час операції реально
  видно у квитанції або на екрані конкретного платежу; у
  payment_time_visible_text дослівно перепиши видимий фрагмент дати й часу;
- якщо час операції на квитанції відсутній, але у верхній панелі телефона
  чітко видно час, використовуй час телефона, постав
  payment_time_source="phone_status_bar" і дослівно перепиши видимий час у
  payment_time_visible_text;
- якщо використано лише час із панелі телефона без дати, підстав поточну дату
  Europe/Kyiv із цього запиту та часовий пояс +03:00 або актуальне зміщення
  Europe/Kyiv;
- якщо видно і час операції, і час телефона, пріоритет має час операції;
- якщо час не видно ані в квитанції, ані у верхній панелі телефона, постав
  payment_datetime=null, payment_time_source="not_visible" та
  payment_time_visible_text=null; категорично не використовуй поточний час із
  тексту запиту як начебто прочитаний із зображення;
- у reason коротко українською опиши, які фактичні дані вдалося прочитати.
""".strip()

    image_base64 = base64.b64encode(image.image_bytes).decode("ascii")
    data_url = f"data:{image.mime_type};base64,{image_base64}"
    client = AsyncOpenAI(api_key=api_key, timeout=timeout_seconds)
    try:
        async with asyncio.timeout(timeout_seconds):
            response = await client.responses.parse(
                model=model,
                input=[
                    {
                        "role": "system",
                        "content": (
                            "Ти модуль точного розпізнавання банківських "
                            "квитанцій. Не знаєш очікуваних значень, не порівнюєш "
                            "їх і не домислюєш нерозбірливі цифри."
                        ),
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "input_text", "text": prompt},
                            {
                                "type": "input_image",
                                "image_url": data_url,
                                "detail": "high",
                            },
                        ],
                    },
                ],
                text_format=PaymentReceiptAnalysis,
                max_output_tokens=700,
            )
    finally:
        await client.close()

    if response.output_parsed is None:
        raise ValueError("OpenAI не повернув структурований результат")
    return response.output_parsed


_TIME_PATTERN = re.compile(
    r"(?<!\d)(?P<hour>[01]?\d|2[0-3]):(?P<minute>[0-5]\d)"
    r"(?::(?P<second>[0-5]\d))?(?!\d)"
)
_DAY_FIRST_DATE_PATTERN = re.compile(
    r"(?<!\d)(?P<day>0?[1-9]|[12]\d|3[01])[./-]"
    r"(?P<month>0?[1-9]|1[0-2])[./-](?P<year>\d{2}|\d{4})(?!\d)"
)
_YEAR_FIRST_DATE_PATTERN = re.compile(
    r"(?<!\d)(?P<year>\d{4})[./-](?P<month>0?[1-9]|1[0-2])[./-]"
    r"(?P<day>0?[1-9]|[12]\d|3[01])(?!\d)"
)
_CANCELLATION_MARKERS = (
    "скасувати платіж",
    "скасувати переказ",
    "відкликати платіж",
    "відмінити платіж",
    "отменить платеж",
    "отменить перевод",
    "отозвать платеж",
    "cancel payment",
    "cancel transfer",
    "undo transfer",
)
_SUCCESS_STATUS_MARKERS = (
    "виконано успішно",
    "успішно виконано",
    "операцію виконано",
    "операція успішна",
    "платіж успішний",
    "платіж виконано",
    "переказ успішний",
    "переказ виконано",
    "успешно выполнено",
    "платеж выполнен",
    "перевод выполнен",
    "successful",
    "completed successfully",
)
_NON_SUCCESS_STATUS_MARKERS = (
    "не виконано",
    "неуспіш",
    "помилка",
    "відхилено",
    "скасовано",
    "в обробці",
    "очікує",
    "не выполнено",
    "ошибка",
    "отклонено",
    "отменено",
    "processing",
    "pending",
    "failed",
    "rejected",
    "cancelled",
)


def _normalize_card_suffix(value: str | None) -> str | None:
    digits = "".join(character for character in (value or "") if character.isdigit())
    if len(digits) >= 4:
        return digits[-4:]
    if len(digits) >= 2:
        return digits
    return None


def _parse_payment_datetime(value: str, now_kyiv: datetime) -> datetime | None:
    text = " ".join(value.strip().replace(",", " ").split())
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=KYIV_ZONE)
    except ValueError:
        pass

    time_match = _TIME_PATTERN.search(text)
    if not time_match:
        return None

    hour = int(time_match.group("hour"))
    minute = int(time_match.group("minute"))
    second = int(time_match.group("second") or 0)
    date_match = _DAY_FIRST_DATE_PATTERN.search(text)
    if date_match:
        year = int(date_match.group("year"))
        if year < 100:
            year += 2000
        try:
            return datetime(
                year,
                int(date_match.group("month")),
                int(date_match.group("day")),
                hour,
                minute,
                second,
                tzinfo=KYIV_ZONE,
            )
        except ValueError:
            return None

    date_match = _YEAR_FIRST_DATE_PATTERN.search(text)
    if date_match:
        try:
            return datetime(
                int(date_match.group("year")),
                int(date_match.group("month")),
                int(date_match.group("day")),
                hour,
                minute,
                second,
                tzinfo=KYIV_ZONE,
            )
        except ValueError:
            return None

    local_now = now_kyiv.astimezone(KYIV_ZONE)
    candidates = [
        (local_now + timedelta(days=day_shift)).replace(
            hour=hour,
            minute=minute,
            second=second,
            microsecond=0,
        )
        for day_shift in (-1, 0, 1)
    ]
    return min(
        candidates,
        key=lambda candidate: abs((local_now - candidate).total_seconds()),
    )


def evaluate_auto_approval(
    analysis: PaymentReceiptAnalysis,
    *,
    expected_amount: int,
    allowed_card_last4: set[str],
    now_kyiv: datetime,
    max_time_difference_minutes: int,
) -> tuple[bool, str, int | None]:
    """Перевіряє тип документа, видимий час, суму та картку."""
    visible_status = (analysis.payment_status_visible_text or "").casefold()
    visible_status_is_not_successful = bool(visible_status) and any(
        marker in visible_status for marker in _NON_SUCCESS_STATUS_MARKERS
    )
    visible_status_is_successful = bool(visible_status) and any(
        marker in visible_status for marker in _SUCCESS_STATUS_MARKERS
    ) and not visible_status_is_not_successful
    if visible_status_is_successful:
        # Дослівний статус із квитанції надійніший за помилкову категорію GPT.
        analysis.payment_status = "successful"
    status_is_successful = (
        analysis.payment_status == "successful"
        and not visible_status_is_not_successful
    )

    # За вимогою проєкту активна картка в будь-якому видимому полі проходить
    # критерій картки незалежно від визначеної GPT ролі sender/recipient.
    visible_card_suffixes: set[str] = set()
    reported_card_suffix = _normalize_card_suffix(analysis.recipient_card_suffix)
    if reported_card_suffix:
        visible_card_suffixes.add(reported_card_suffix)
    for visible_suffix in analysis.visible_card_number_suffixes:
        normalized_suffix = _normalize_card_suffix(visible_suffix)
        if normalized_suffix:
            visible_card_suffixes.add(normalized_suffix)
    for candidate in analysis.card_candidates:
        candidate_suffix = _normalize_card_suffix(candidate.visible_suffix)
        if candidate_suffix:
            visible_card_suffixes.add(candidate_suffix)
    checks: list[tuple[bool, str]] = [
        (
            not analysis.payment_can_be_cancelled
            and not any(
                marker in (analysis.cancellation_visible_text or "").casefold()
                for marker in _CANCELLATION_MARKERS
            ),
            CANCELLABLE_PAYMENT_REASON,
        ),
        (
            analysis.document_type
            in {
                "payment_receipt",
                "transfer_success_screen",
                "payment_details_screen",
            },
            "зображення не є квитанцією або екраном конкретного платежу",
        ),
        (
            status_is_successful,
            "платіж у квитанції не має успішного завершеного статусу",
        ),
        (
            analysis.amount_found is not None
            and abs(analysis.amount_found) == expected_amount,
            "сума платежу не збігається",
        ),
    ]
    for passed, reason in checks:
        if not passed:
            return False, reason, None

    unambiguous_matches: list[tuple[str, str]] = []
    for suffix in visible_card_suffixes:
        matching_cards = {
            card_last4
            for card_last4 in allowed_card_last4
            if card_last4.endswith(suffix)
        }
        if len(matching_cards) == 1:
            unambiguous_matches.append((suffix, next(iter(matching_cards))))

    if not unambiguous_matches:
        return False, CARD_MISMATCH_REASON, None

    # Повніші видимі закінчення мають пріоритет над короткими масками.
    _, selected_card = max(
        unambiguous_matches,
        key=lambda item: (len(item[0]), item[0]),
    )

    # В адмінському результаті показуємо повні останні 4 цифри активної картки.
    analysis.recipient_card_suffix = selected_card

    if analysis.payment_time_source == "not_visible":
        return False, "час не видно на квитанції або екрані телефона", None
    visible_time_text = (analysis.payment_time_visible_text or "").strip()
    visible_time_match = _TIME_PATTERN.search(visible_time_text)
    if not visible_time_match:
        return False, "немає підтвердження, що час видимий на зображенні", None

    if not analysis.payment_datetime:
        return False, "час операції не визначено", None
    payment_datetime_text = analysis.payment_datetime.strip()
    payment_time = _parse_payment_datetime(payment_datetime_text, now_kyiv)
    if payment_time is None:
        return False, "час операції має невалідний формат", None

    if (
        payment_time.hour != int(visible_time_match.group("hour"))
        or payment_time.minute != int(visible_time_match.group("minute"))
    ):
        return False, "розпізнаний час не збігається з видимим текстом", None

    difference_minutes = round(
        abs((now_kyiv - payment_time.astimezone(KYIV_ZONE)).total_seconds()) / 60
    )
    if difference_minutes > max_time_difference_minutes:
        return (
            False,
            f"час операції перевищує допустимі {max_time_difference_minutes} хвилин",
            difference_minutes,
        )
    return True, "сума, картка та час збігаються", difference_minutes
