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
from PIL import Image, ImageOps, UnidentifiedImageError
from pydantic import BaseModel, ConfigDict, Field


KYIV_ZONE = ZoneInfo("Europe/Kyiv")
SUPPORTED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP"}


class UnsupportedReceiptFile(ValueError):
    pass


class ReceiptFileTooLarge(ValueError):
    pass


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
    amount_found: int | None
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
- amount_found — фактична сума переказу цілим числом; знак мінус збережи,
  якщо він показаний біля вибраної суми;
- recipient_card_suffix бери лише з реквізитів отримувача: полів
  «Отримувач», «Отримувач переказу», «Картка отримувача», «На картку» або
  аналогічних за змістом;
- не використовуй для recipient_card_suffix картку платника, відправника,
  картку списання, «З картки» чи номер рахунку платника;
- якщо видно кілька карток, обов'язково розрізни відправника й отримувача та
  поверни останні 4 цифри саме картки отримувача;
- якщо картку отримувача визначити неможливо, поверни null, а не номер
  картки відправника;
- для recipient_card_suffix поверни лише видимі кінцеві цифри картки
  отримувача без пробілів і маски ****: зазвичай це 4 цифри, але якщо банк
  показує тільки 2 або 3, поверни саме ці 2 або 3 цифри;
- ніколи не доповнюй дві видимі цифри до чотирьох і не домислюй
  нерозбірливі цифри;
- для payment_datetime спочатку використовуй дату й час самої операції;
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


def evaluate_auto_approval(
    analysis: PaymentReceiptAnalysis,
    *,
    expected_amount: int,
    allowed_card_last4: set[str],
    now_kyiv: datetime,
    max_time_difference_minutes: int,
) -> tuple[bool, str, int | None]:
    """Перевіряє тип документа, видимий час, суму та картку."""
    card_digits = "".join(
        character
        for character in (analysis.recipient_card_suffix or "")
        if character.isdigit()
    )
    if len(card_digits) >= 4:
        found_card_suffix = card_digits[-4:]
    elif len(card_digits) >= 2:
        found_card_suffix = card_digits[-len(card_digits):]
    else:
        found_card_suffix = None

    matching_cards = (
        {
            card_last4
            for card_last4 in allowed_card_last4
            if card_last4.endswith(found_card_suffix)
        }
        if found_card_suffix
        else set()
    )
    checks: list[tuple[bool, str]] = [
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
            analysis.payment_status == "successful",
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

    if not found_card_suffix or not matching_cards:
        return False, "картка одержувача не збігається", None
    if len(matching_cards) > 1:
        return False, "видимих цифр недостатньо для однозначного вибору картки", None

    if analysis.payment_time_source == "not_visible":
        return False, "час не видно на квитанції або екрані телефона", None
    visible_time_text = (analysis.payment_time_visible_text or "").strip()
    visible_time_match = re.search(
        r"(?<!\d)(?P<hour>[01]?\d|2[0-3]):(?P<minute>[0-5]\d)"
        r"(?::(?P<second>[0-5]\d))?(?!\d)",
        visible_time_text,
    )
    if not visible_time_match:
        return False, "немає підтвердження, що час видимий на зображенні", None

    if not analysis.payment_datetime:
        return False, "час операції не визначено", None
    payment_datetime_text = analysis.payment_datetime.strip()
    try:
        payment_time = datetime.fromisoformat(
            payment_datetime_text.replace("Z", "+00:00")
        )
    except ValueError:
        time_only = re.fullmatch(
            r"(?P<hour>[01]?\d|2[0-3]):(?P<minute>[0-5]\d)"
            r"(?::(?P<second>[0-5]\d))?",
            payment_datetime_text,
        )
        if not time_only:
            return False, "час операції має невалідний формат", None

        hour = int(time_only.group("hour"))
        minute = int(time_only.group("minute"))
        second = int(time_only.group("second") or 0)
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
        payment_time = min(
            candidates,
            key=lambda candidate: abs((local_now - candidate).total_seconds()),
        )
    if payment_time.tzinfo is None:
        payment_time = payment_time.replace(tzinfo=KYIV_ZONE)

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
