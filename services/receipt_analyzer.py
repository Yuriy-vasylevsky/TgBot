import asyncio
import base64
import hashlib
import io
import warnings
from dataclasses import dataclass
from datetime import datetime
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
- approve можливий лише для однозначно успішного й завершеного платежу;
- processing, rejected, cancelled, failed та неоднозначний статус завжди manual_review;
- сума має точно дорівнювати очікуваній;
- картка одержувача має збігатися за останніми 4 цифрами;
- дата й час мають бути прочитані однозначно разом із часовим поясом;
- неповний, нечіткий або ймовірно відредагований скриншот завжди manual_review;
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
    min_confidence: float,
    max_time_difference_minutes: int,
) -> tuple[bool, str, int | None]:
    """Повторно перевіряє в коді всі умови, не довіряючи лише decision моделі."""
    checks: list[tuple[bool, str]] = [
        (analysis.is_payment_receipt, "зображення не визначене як квитанція"),
        (analysis.payment_status == "successful", "статус платежу не успішний"),
        (
            analysis.amount_found == expected_amount and analysis.amount_matches,
            "сума платежу не збігається",
        ),
        (
            bool(analysis.recipient_card_last4)
            and analysis.recipient_card_last4 in allowed_card_last4
            and analysis.recipient_card_matches,
            "картка одержувача не збігається",
        ),
        (analysis.image_is_readable, "квитанція недостатньо читабельна"),
        (not analysis.possible_editing, "можливі ознаки редагування"),
        (analysis.decision == "approve", "модель вимагає ручної перевірки"),
        (
            analysis.confidence >= min_confidence,
            "недостатній рівень впевненості",
        ),
    ]
    for passed, reason in checks:
        if not passed:
            return False, reason, None

    if not analysis.payment_datetime:
        return False, "час операції не визначено", None
    try:
        payment_time = datetime.fromisoformat(
            analysis.payment_datetime.replace("Z", "+00:00")
        )
    except ValueError:
        return False, "час операції має невалідний формат", None
    if payment_time.tzinfo is None:
        return False, "часовий пояс операції не визначено", None

    difference_minutes = round(
        abs((now_kyiv - payment_time.astimezone(KYIV_ZONE)).total_seconds()) / 60
    )
    if not analysis.time_matches:
        return False, "модель позначила час як невідповідний", difference_minutes
    if difference_minutes > max_time_difference_minutes:
        return (
            False,
            f"час операції перевищує допустимі {max_time_difference_minutes} хвилин",
            difference_minutes,
        )

    return True, "усі обов'язкові перевірки пройдено", difference_minutes
