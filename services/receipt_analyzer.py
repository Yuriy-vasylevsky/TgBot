import asyncio
import base64
import hashlib
import io
import logging
import json
import os
import re
import warnings
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

import imagehash
from aiogram import Bot
from openai import AsyncOpenAI
from PIL import Image, ImageEnhance, ImageFilter, ImageOps, UnidentifiedImageError
from pydantic import BaseModel, ConfigDict, Field


KYIV_ZONE = ZoneInfo("Europe/Kyiv")
SUPPORTED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP"}
DETAIL_IMAGE_TARGET_LONG_SIDE = 2400
DETAIL_IMAGE_MAX_SCALE = 3.0
PHONE_STATUS_BAR_HEIGHT_RATIO = 0.14
RECEIPT_ANALYZER_OPENAI = "gpt"
RECEIPT_ANALYZER_DEEPSEEK = "deepseek"
RECEIPT_ANALYZERS = {RECEIPT_ANALYZER_OPENAI, RECEIPT_ANALYZER_DEEPSEEK}
_RECEIPT_ANALYZER_SETTINGS_FILE = Path(
    os.getenv("DATA_DIR", "data")
) / "receipt_analyzer_settings.json"
CARD_MISMATCH_REASON = (
    "картка одержувача не збігається або її не вдалось правильно розпізнати"
)
PAYMENT_DETAILS_MISMATCH_REASON = (
    "знайдені картка або IBAN одержувача не збігаються з дозволеними реквізитами"
)
PAYMENT_DETAILS_NOT_RECOGNIZED_REASON = (
    "картку або IBAN одержувача не вдалось правильно розпізнати"
)
CANCELLABLE_PAYMENT_REASON = "платіж ще можна скасувати"


class UnsupportedReceiptFile(ValueError):
    pass


class ReceiptFileTooLarge(ValueError):
    pass


def get_receipt_analyzer() -> str:
    """Return the administrator-selected receipt analyzer, defaulting to GPT."""
    try:
        data = json.loads(_RECEIPT_ANALYZER_SETTINGS_FILE.read_text(encoding="utf-8"))
        analyzer = data.get("receipt_analyzer")
        if analyzer in RECEIPT_ANALYZERS:
            return analyzer
    except FileNotFoundError:
        pass
    except (OSError, json.JSONDecodeError):
        logging.exception("Unable to load receipt analyzer settings")
    return RECEIPT_ANALYZER_OPENAI


def set_receipt_analyzer(analyzer: str) -> None:
    """Persist the analyzer choice without ever storing API credentials."""
    if analyzer not in RECEIPT_ANALYZERS:
        raise ValueError(f"Unsupported receipt analyzer: {analyzer}")
    _RECEIPT_ANALYZER_SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _RECEIPT_ANALYZER_SETTINGS_FILE.write_text(
        json.dumps({"receipt_analyzer": analyzer}),
        encoding="utf-8",
    )


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
    visible_ibans: list[str]
    recipient_iban: str | None
    payment_datetime: str | None
    payment_time_source: Literal["operation", "phone_status_bar", "not_visible"]
    payment_time_visible_text: str | None
    image_is_readable: bool
    possible_editing: bool
    confidence: float = Field(ge=0, le=1)
    reason: str


class PaymentTimeEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    time_is_visible: bool
    source: Literal["operation", "phone_status_bar", "not_visible"]
    payment_datetime: str | None
    visible_text: str | None
    confidence: float = Field(ge=0, le=1)
    reason: str


def _needs_time_recheck(analysis: PaymentReceiptAnalysis) -> bool:
    """Detect the unsafe contradiction returned in some vision responses."""
    return (
        analysis.payment_time_source == "not_visible"
        and bool((analysis.payment_datetime or "").strip())
    )


def _apply_verified_time_evidence(
    analysis: PaymentReceiptAnalysis,
    evidence: PaymentTimeEvidence,
) -> None:
    has_complete_visible_evidence = (
        evidence.time_is_visible
        and evidence.source in {"operation", "phone_status_bar"}
        and bool((evidence.payment_datetime or "").strip())
        and bool((evidence.visible_text or "").strip())
    )
    if has_complete_visible_evidence:
        analysis.payment_datetime = evidence.payment_datetime
        analysis.payment_time_source = evidence.source
        analysis.payment_time_visible_text = evidence.visible_text
    else:
        # Не залишаємо дату, яку перша відповідь могла взяти з поточного часу
        # запиту, якщо окрема перевірка не знайшла видимого доказу на зображенні.
        analysis.payment_datetime = None
        analysis.payment_time_source = "not_visible"
        analysis.payment_time_visible_text = None
    analysis.reason = (
        f"{analysis.reason}; повторна перевірка часу: {evidence.reason}"
    )


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


def _detail_crop_boxes(width: int, height: int) -> list[tuple[int, int, int, int]]:
    """Build overlapping crops so small receipt digits reach the vision model."""

    def axis_ranges(length: int, count: int) -> list[tuple[int, int]]:
        segment = length / count
        overlap = max(1, round(segment * 0.18))
        return [
            (
                max(0, round(index * segment) - overlap),
                min(length, round((index + 1) * segment) + overlap),
            )
            for index in range(count)
        ]

    aspect_ratio = width / height
    if aspect_ratio <= 0.87:
        row_count = 4 if height / width >= 1.6 else 3
        return [
            (0, top, width, bottom)
            for top, bottom in axis_ranges(height, row_count)
        ]
    if aspect_ratio >= 1.15:
        column_count = 3 if width / height >= 1.6 else 2
        return [
            (left, 0, right, height)
            for left, right in axis_ranges(width, column_count)
        ]

    horizontal_ranges = axis_ranges(width, 2)
    vertical_ranges = axis_ranges(height, 2)
    return [
        (left, top, right, bottom)
        for top, bottom in vertical_ranges
        for left, right in horizontal_ranges
    ]


def _build_receipt_detail_crops(image_bytes: bytes) -> list[bytes]:
    """Return enlarged overlapping fragments of the already-normalized receipt."""

    with Image.open(io.BytesIO(image_bytes)) as source:
        image = source.convert("RGB")

    # Першим фрагментом окремо даємо верхню смугу. На екранах успішного
    # переказу час часто є тільки в status bar і губиться серед усієї сторінки.
    status_bar_bottom = max(1, round(image.height * PHONE_STATUS_BAR_HEIGHT_RATIO))
    crop_boxes = [
        (0, 0, image.width, status_bar_bottom),
        *_detail_crop_boxes(image.width, image.height),
    ]

    crops: list[bytes] = []
    for box in crop_boxes:
        crop = image.crop(box)
        longest_side = max(crop.size)
        if longest_side < DETAIL_IMAGE_TARGET_LONG_SIDE:
            scale = min(
                DETAIL_IMAGE_MAX_SCALE,
                DETAIL_IMAGE_TARGET_LONG_SIDE / longest_side,
            )
            crop = crop.resize(
                (round(crop.width * scale), round(crop.height * scale)),
                Image.Resampling.LANCZOS,
            )
        crop = ImageOps.autocontrast(crop, cutoff=1)
        crop = ImageEnhance.Contrast(crop).enhance(1.1)
        crop = crop.filter(
            ImageFilter.UnsharpMask(radius=1.0, percent=135, threshold=2)
        )
        output = io.BytesIO()
        crop.save(output, format="JPEG", quality=94, optimize=True)
        crops.append(output.getvalue())
    return crops


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


async def _recheck_receipt_time_with_openai(
    *,
    client: AsyncOpenAI,
    model: str,
    timeout_seconds: int,
    image_content: list[dict],
    now_kyiv: datetime,
    initial_analysis: PaymentReceiptAnalysis,
) -> PaymentTimeEvidence:
    prompt = f"""
Перевір ТІЛЬКИ видимий час на цих зображеннях однієї банківської квитанції.
Перша перевірка дала суперечливий результат: payment_datetime=
{initial_analysis.payment_datetime!r}, але payment_time_source="not_visible".
Не вважай попередній payment_datetime доказом і прочитай зображення заново.

Перше зображення — повний документ, друге — збільшена верхня смуга, решта —
збільшені фрагменти. Поточний час Europe/Kyiv: {now_kyiv.isoformat()}.

Правила:
- спочатку шукай явно підписані дату й час операції на квитанції; якщо вони
  читаються, source="operation", visible_text — дослівний видимий фрагмент;
- якщо часу операції немає, перевір системну панель телефона. HH:MM є часом
  телефона лише поруч з індикаторами батареї, мережі, Wi-Fi або іншими
  системними значками; тоді source="phone_status_bar";
- якщо на панелі телефона видно тільки HH:MM без дати, для payment_datetime
  використай поточну київську дату з цього запиту та актуальне зміщення;
- time_is_visible=true став лише коли точний час реально читається на одному
  із зображень. Не бери поточний час із тексту запиту та нічого не домислюй;
- якщо час не читається, поверни time_is_visible=false, source="not_visible",
  payment_datetime=null і visible_text=null;
- якщо time_is_visible=true, payment_datetime має бути ISO 8601, а
  visible_text обов'язково має дослівно містити прочитаний HH:MM.
""".strip()
    async with asyncio.timeout(timeout_seconds):
        response = await client.responses.parse(
            model=model,
            input=[
                {
                    "role": "system",
                    "content": (
                        "Ти незалежний модуль перевірки доказу часу на "
                        "банківських квитанціях. Не довіряй попередньому "
                        "результату без видимого підтвердження."
                    ),
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": prompt},
                        *image_content,
                    ],
                },
            ],
            text_format=PaymentTimeEvidence,
            max_output_tokens=250,
        )
    if response.output_parsed is None:
        raise ValueError("OpenAI не повернув результат повторної перевірки часу")
    return response.output_parsed


async def analyze_receipt_with_openai(
    *,
    api_key: str,
    model: str,
    timeout_seconds: int,
    image: PreparedReceipt,
    now_kyiv: datetime,
    base_url: str | None = None,
) -> PaymentReceiptAnalysis:
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY не налаштований")

    prompt = f"""
Прочитай фактичні дані з банківської квитанції або екрана переказу.
Ти не знаєш очікуваної суми чи дозволених карток. Нічого не порівнюй і не
підставляй: повертай лише те, що справді видно на зображенні.

Перше зображення — повна квитанція. Друге зображення — спеціально збільшена
верхня смуга цього самого зображення для читання системного часу телефона.
Решта зображень — збільшені фрагменти ЦІЄЇ Ж квитанції з перекриттям. Це не
окремі платежі: використовуй фрагменти, щоб повторно звірити дрібний текст і
цифри з повним зображенням.

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
- окремо знайди КОЖЕН повністю видимий IBAN і поверни його у visible_ibans.
  IBAN починається з двох латинських літер і двох контрольних цифр; пробіли
  між групами прибери, літери поверни великими. Особливо перевір поля «IBAN»,
  «IBAN отримувача», «Рахунок отримувача», recipient account та beneficiary;
- у recipient_iban поверни повний IBAN лише тоді, коли найближчий підпис явно
  вказує на отримувача/одержувача/beneficiary. Якщо роль неясна — поверни його
  тільки у visible_ibans, а recipient_iban=null;
- не домислюй і не виправляй символи IBAN. Частково видимий, маскований або
  нерозбірливий IBAN не додавай до visible_ibans і recipient_iban;
- у visible_card_number_suffixes повертай лише реально видимі останні 2–4
  цифри кожної картки; якщо видно повний або маскований номер — поверни його
  останні 4 цифри;
- кожне закінчення картки прочитай щонайменше двічі: спочатку на повному
  зображенні, потім на найчіткішому збільшеному фрагменті. Звіряй останні
  цифри справа наліво, не плутай 0/6/8/9, 1/7 та 3/8 і надавай перевагу
  чіткішому збільшеному фрагменту;
- якщо повне зображення і фрагмент начебто дають різні цифри, не вибирай
  варіант за контекстом і не підставляй типовий номер. Поверни лише ті останні
  2–3 цифри, які справді читаються однаково; якщо навіть вони не певні — не
  додавай цей номер;
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
- перед тим як ставити payment_time_source="not_visible", ОБОВ'ЯЗКОВО окремо
  переглянь друге зображення. Якщо там видно час формату HH:MM поруч з ознаками
  системної панелі телефона — індикаторами мережі, Wi-Fi, батареї чи іншими
  системними значками — це валідний видимий час телефона. Наприклад, «21:27»
  у верхньому лівому куті такого екрана треба повернути як
  payment_time_visible_text="21:27" і payment_time_source="phone_status_bar";
- не вважай часом телефона довільне HH:MM із верхньої частини паперової або
  PDF-квитанції: для phone_status_bar разом із часом мають бути видимі ознаки
  саме системної панелі телефона;
- якщо використано лише час із панелі телефона без дати, підстав поточну дату
  Europe/Kyiv із цього запиту та часовий пояс +03:00 або актуальне зміщення
  Europe/Kyiv;
- якщо видно і час операції, і час телефона, пріоритет має час операції;
- якщо час не видно ані в квитанції, ані у верхній панелі телефона, постав
  payment_datetime=null, payment_time_source="not_visible" та
  payment_time_visible_text=null; категорично не використовуй поточний час із
  тексту запиту як начебто прочитаний із зображення;
- ці три поля мають бути узгоджені: заборонено повертати непорожній
  payment_datetime разом із payment_time_source="not_visible". Якщо
  payment_datetime заповнений, source має точно вказувати, де цей час видно,
  а payment_time_visible_text має містити дослівний видимий фрагмент;
- у reason коротко українською опиши, які фактичні дані вдалося прочитати.
""".strip()

    detail_crops = await asyncio.to_thread(
        _build_receipt_detail_crops,
        image.image_bytes,
    )
    receipt_images = [image.image_bytes, *detail_crops]
    image_content = [
        {
            "type": "input_image",
            "image_url": (
                "data:image/jpeg;base64,"
                + base64.b64encode(receipt_image).decode("ascii")
            ),
            "detail": "high",
        }
        for receipt_image in receipt_images
    ]
    client = AsyncOpenAI(
        api_key=api_key,
        timeout=timeout_seconds,
        **({"base_url": base_url} if base_url else {}),
    )
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
                            *image_content,
                        ],
                    },
                ],
                text_format=PaymentReceiptAnalysis,
                max_output_tokens=700,
            )
        analysis = response.output_parsed
        if analysis is None:
            raise ValueError("OpenAI не повернув структурований результат")

        if _needs_time_recheck(analysis):
            try:
                time_evidence = await _recheck_receipt_time_with_openai(
                    client=client,
                    model=model,
                    timeout_seconds=timeout_seconds,
                    image_content=image_content,
                    now_kyiv=now_kyiv,
                    initial_analysis=analysis,
                )
            except Exception:
                # Без успішної повторної перевірки суперечливий результат не
                # послаблюємо: evaluate_auto_approval передасть його адміну.
                logging.exception("OpenAI receipt time recheck failed")
            else:
                _apply_verified_time_evidence(analysis, time_evidence)
        return analysis
    finally:
        await client.close()


async def analyze_receipt_with_deepseek(
    *,
    api_key: str,
    model: str,
    timeout_seconds: int,
    image: PreparedReceipt,
    now_kyiv: datetime,
) -> PaymentReceiptAnalysis:
    """Analyze a receipt with DeepSeek's OpenAI-compatible Vision API."""
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY не налаштований")
    return await analyze_receipt_with_openai(
        api_key=api_key,
        model=model,
        timeout_seconds=timeout_seconds,
        image=image,
        now_kyiv=now_kyiv,
        base_url="https://api.deepseek.com",
    )


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
_BLOCKING_STATUS_MARKERS = (
    "не виконано",
    "неуспіш",
    "помилка",
    "відхилено",
    "скасовано",
    "не выполнено",
    "ошибка",
    "отклонено",
    "отменено",
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


def _normalize_iban(value: str | None) -> str | None:
    normalized = "".join(
        character
        for character in (value or "").upper()
        if character.isalnum()
    )
    if not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]{11,30}", normalized):
        return None
    return normalized


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
    allowed_ibans: set[str] | None = None,
) -> tuple[bool, str, int | None]:
    """Перевіряє тип документа, видимий час, суму та картку або IBAN."""
    visible_status = (analysis.payment_status_visible_text or "").casefold()
    visible_status_is_blocking = bool(visible_status) and any(
        marker in visible_status for marker in _BLOCKING_STATUS_MARKERS
    )
    visible_status_is_successful = bool(visible_status) and any(
        marker in visible_status for marker in _SUCCESS_STATUS_MARKERS
    ) and not visible_status_is_blocking
    if visible_status_is_successful:
        # Дослівний статус із квитанції надійніший за помилкову категорію GPT.
        analysis.payment_status = "successful"
    status_is_allowed = (
        analysis.payment_status not in {"failed", "rejected", "cancelled"}
        and not visible_status_is_blocking
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

    normalized_allowed_ibans = {
        normalized
        for iban in (allowed_ibans or set())
        if (normalized := _normalize_iban(iban))
    }
    visible_ibans = {
        normalized
        for iban in [analysis.recipient_iban, *analysis.visible_ibans]
        if (normalized := _normalize_iban(iban))
    }
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
            status_is_allowed,
            "у квитанції вказано негативний статус платежу",
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

    # Для IBAN звіряємо лише останні 4 цифри. Це робить перевірку стійкою до
    # OCR-помилок у довгій середині рахунку та відповідає перевірці карток.
    visible_iban_last4 = {iban[-4:] for iban in visible_ibans}
    matching_ibans = {
        allowed_iban
        for allowed_iban in normalized_allowed_ibans
        if allowed_iban[-4:] in visible_iban_last4
    }
    if not unambiguous_matches and not matching_ibans:
        if normalized_allowed_ibans:
            mismatch_reason = (
                PAYMENT_DETAILS_MISMATCH_REASON
                if visible_card_suffixes or visible_ibans
                else PAYMENT_DETAILS_NOT_RECOGNIZED_REASON
            )
        else:
            mismatch_reason = CARD_MISMATCH_REASON
        return False, mismatch_reason, None

    selected_card = None
    if unambiguous_matches:
        # Повніші видимі закінчення мають пріоритет над короткими масками.
        _, selected_card = max(
            unambiguous_matches,
            key=lambda item: (len(item[0]), item[0]),
        )

        # В адмінському результаті показуємо повні останні 4 цифри активної картки.
        analysis.recipient_card_suffix = selected_card

    selected_iban = sorted(matching_ibans)[0] if matching_ibans else None
    if selected_iban:
        analysis.recipient_iban = selected_iban

    if analysis.payment_time_source == "not_visible":
        return False, "час не видно на квитанції або екрані телефона", None
    visible_time_text = (analysis.payment_time_visible_text or "").strip()
    visible_time_match = _TIME_PATTERN.search(visible_time_text)
    if not visible_time_match:
        return False, "немає підтвердження, що час видимий на зображенні", None

    # Structured output іноді правильно знаходить видимий HH:MM і його
    # джерело, але лишає payment_datetime порожнім. У такому разі безпечно
    # відновлюємо дату/час із самого видимого тексту: для HH:MM парсер обирає
    # найближчу київську дату (вчора/сьогодні/завтра), після чого нижче все
    # одно діє звичайне обмеження max_time_difference_minutes.
    payment_datetime_text = (analysis.payment_datetime or visible_time_text).strip()
    payment_time = _parse_payment_datetime(payment_datetime_text, now_kyiv)
    if payment_time is None:
        return False, "час операції має невалідний формат", None
    if not (analysis.payment_datetime or "").strip():
        analysis.payment_datetime = payment_time.isoformat()

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
    payment_detail = "IBAN" if selected_iban and not selected_card else "картка"
    return True, f"сума, {payment_detail} та час збігаються", difference_minutes
