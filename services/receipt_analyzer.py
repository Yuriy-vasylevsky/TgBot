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
    payment_status: Literal[
        "successful", "processing", "rejected", "cancelled", "failed", "unknown"
    ]
    amount_found: int | None
    amount_matches: bool
    recipient_card_last4: str | None
    recipient_card_matches: bool
    payment_datetime: str | None
    time_difference_minutes: int | None
    time_matches: bool
    image_is_readable: bool
    possible_editing: bool
    confidence: float = Field(ge=0, le=1)
    decision: Literal["approve", "manual_review"]
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
    expected_amount: int,
    allowed_cards: list[dict[str, str]],
    now_kyiv: datetime,
    max_time_difference_minutes: int,
) -> PaymentReceiptAnalysis:
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY не налаштований")

    allowed_cards_text = "\n".join(
        f"- {card['bank']}: **** {card['last4']}" for card in allowed_cards
    )
    prompt = f"""
Перевір банківську квитанцію або екран успішного переказу.

Очікувана сума: {expected_amount} грн (ціле число).
Дозволені картки одержувача:
{allowed_cards_text}
Поточний час Europe/Kyiv: {now_kyiv.isoformat()}
Максимальна абсолютна різниця часу: {max_time_difference_minutes} хвилин.

Правила:
- сума має точно дорівнювати очікуваній;
- сума зі знаком мінус означає списання з рахунку платника: наприклад,
  -200 грн потрібно трактувати як переказ на 200 грн, тому amount_matches=true,
  якщо абсолютне значення точно збігається з очікуваною сумою;
- картка одержувача має збігатися за останніми 4 цифрами;
- recipient_card_last4 бери лише з реквізитів отримувача: полів
  «Отримувач», «Отримувач переказу», «Картка отримувача», «На картку» або
  аналогічних за змістом;
- не використовуй для recipient_card_last4 картку платника, відправника,
  картку списання, «З картки» чи номер рахунку платника;
- якщо видно кілька карток, обов'язково розрізни відправника й отримувача та
  поверни останні 4 цифри саме картки отримувача;
- якщо картку отримувача визначити неможливо, поверни null, а не номер
  картки відправника;
- порівнюй лише цифри: якщо прочитані останні 4 цифри точно є у списку
  дозволених карток, recipient_card_matches обов'язково має бути true;
- не вважай картку невідповідною через пробіли, маску **** або те, що на
  квитанції показано повний номер;
- для payment_datetime спочатку використовуй дату й час самої операції;
- якщо час операції на квитанції відсутній, але у верхній панелі телефона
  чітко видно час, використовуй час телефона;
- якщо використано лише час із панелі телефона без дати, підстав поточну дату
  Europe/Kyiv із цього запиту та часовий пояс +03:00 або актуальне зміщення
  Europe/Kyiv;
- якщо видно і час операції, і час телефона, пріоритет має час операції;
- не вигадуй час, якщо його неможливо прочитати в жодному з цих місць;
- decision approve став лише тоді, коли одночасно збігаються сума, останні
  4 цифри картки та час у дозволеному інтервалі;
- інші поля заповнюй для інформації, але вони не змінюють ці три критерії;
- ніколи не повертай остаточне відхилення, лише approve або manual_review;
- у reason коротко поясни рішення українською мовою.
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
                            "Ти консервативний модуль перевірки банківських "
                            "квитанцій. За будь-якого сумніву обирай manual_review."
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
    """Перевіряє лише суму, картку та час за прочитаними моделлю даними."""
    card_digits = "".join(
        character
        for character in (analysis.recipient_card_last4 or "")
        if character.isdigit()
    )
    found_card_last4 = card_digits[-4:] if len(card_digits) >= 4 else None
    checks: list[tuple[bool, str]] = [
        (
            analysis.amount_found is not None
            and abs(analysis.amount_found) == expected_amount,
            "сума платежу не збігається",
        ),
        (
            bool(found_card_last4) and found_card_last4 in allowed_card_last4,
            "картка одержувача не збігається",
        ),
    ]
    for passed, reason in checks:
        if not passed:
            return False, reason, None

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
