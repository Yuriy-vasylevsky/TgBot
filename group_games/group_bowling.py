from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, ContentType
import logging
from datetime import datetime, timedelta, timezone
import random
import string

from handlers.config import ADMIN_ID
from db import DB_PATH, add_promocode
import aiosqlite

router = Router(name="group_bowling")

# Працюємо тільки в групах
router.message.filter(F.chat.type.in_({"group", "supergroup"}))

# chat_id → {user_id: кількість страйків}
active_bowling_games = {}

# chat_id → список message_id, які можна видалити після завершення гри
bowling_messages = {}

KYIV_TZ = timezone(timedelta(hours=3))


async def is_promo_on_cooldown(user_id: int) -> bool:
    """Перевіряє, чи користувач ще на кулдауні"""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT promo_cooldown_until FROM users WHERE user_id = ?",
            (user_id,)
        ) as cur:
            row = await cur.fetchone()
            if not row or not row[0]:
                return False

            cooldown_until = datetime.fromisoformat(row[0])
            now = datetime.now(KYIV_TZ)
            return now < cooldown_until


async def get_promo_cooldown_remaining(user_id: int) -> tuple[int, int] | None:
    """Повертає (години, хвилини), що залишилось, або None якщо кулдаун минув"""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT promo_cooldown_until FROM users WHERE user_id = ?",
            (user_id,)
        ) as cur:
            row = await cur.fetchone()
            if not row or not row[0]:
                return None

            cooldown_until = datetime.fromisoformat(row[0])
            now = datetime.now(KYIV_TZ)

            if now >= cooldown_until:
                return None

            delta = cooldown_until - now
            hours = int(delta.total_seconds() // 3600)
            minutes = int((delta.total_seconds() % 3600) // 60)
            return hours, minutes


async def set_promo_cooldown(user_id: int, hours: int = 12):
    """Встановлює кулдаун на N годин від поточного моменту"""
    future = datetime.now(KYIV_TZ) + timedelta(hours=hours)
    future_str = future.isoformat(timespec="seconds")

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            UPDATE users 
            SET promo_cooldown_until = ? 
            WHERE user_id = ?
            """,
            (future_str, user_id)
        )
        await db.commit()


def generate_promocode(length: int = 8) -> str:
    characters = string.ascii_uppercase + string.digits
    return "".join(random.choices(characters, k=length))


# ==========================
# ЗАПУСК ГРИ (тільки адмін)
# ==========================
@router.message(Command("bowling"))
async def start_bowling(message: Message):
    if message.from_user.id != ADMIN_ID:
        try:
            await message.delete()
        except:
            pass
        return

    chat_id = message.chat.id

    # Ініціалізація
    active_bowling_games[chat_id] = {}
    bowling_messages[chat_id] = []

    logging.info(f"🎳 БОУЛІНГ ЗАПУЩЕНО в чаті {chat_id}")

    start_msg = await message.answer(
        "🎳 <b>БОУЛІНГ СТАРТУВАВ!</b> 🎳\n\n"
    
         "🏆 Приз —  🎟️ промокод!\n\n",
        parse_mode="HTML"
    )
    bowling_messages[chat_id].append(start_msg.message_id)  # 0 — стартове, захищене

    # Бот кидає перший боулінг
    bot_dice = await message.bot.send_dice(chat_id=chat_id, emoji="🎳")
    bowling_messages[chat_id].append(bot_dice.message_id)

    # Видаляємо команду /bowling
    try:
        await message.delete()
    except:
        pass


# ==========================
# ОБРОБКА КИДКІВ 🎳
# ==========================
@router.message(F.content_type == ContentType.DICE, F.dice.emoji == "🎳")
async def handle_bowling_dice(message: Message):
    chat_id = message.chat.id
    user = message.from_user
    user_id = user.id

    if chat_id not in active_bowling_games:
        try:
            await message.delete()
        except:
            pass
        return

    # Зберігаємо повідомлення для можливого видалення
    bowling_messages.setdefault(chat_id, []).append(message.message_id)

    game = active_bowling_games[chat_id]

    if user_id not in game:
        game[user_id] = 0

    score = message.dice.value

    if score != 6:
        return  # не страйк — нічого не робимо

    game[user_id] += 1
    strikes = game[user_id]

    if strikes >= 2:
        # Перевірка кулдауну
        if await is_promo_on_cooldown(user_id):
            remaining = await get_promo_cooldown_remaining(user_id)
            if remaining:
                h, m = remaining
                cd_msg = await message.answer(
                    f"{user.mention_html()}, дай шанс іншим гравцям!\n"
                    f"⏳ <b>{h} год {m} хв</b> ⏳",
                    parse_mode="HTML"
                )
                bowling_messages[chat_id].append(cd_msg.message_id)
                return  # Гра продовжується, без очищення та завершення

        # Промокод
        promo = generate_promocode()
        await add_promocode(promo)

        # Встановлюємо кулдаун
        await set_promo_cooldown(user_id, hours=12)

        # Надсилання в приват + fallback
        sent_to_private = False
        try:
            await message.bot.send_message(
                chat_id=user_id,
                text=(
                    f"🎉 <b>Вітаємо з перемогою в Боулінгу!</b>\n\n"
                    f"Твій приз:\n"
                    f"<code>{promo}</code>\n\n"
                    "Використовуй його в боті 👇\n"
             
                ),
                parse_mode="HTML"
            )
            sent_to_private = True
        except Exception as e:
            logging.warning(f"Не вдалося надіслати промокод гравцю {user_id}: {e}")

        # Повідомлення про перемогу
        if sent_to_private:
            win_text = (
                f"🎉 <b>ПЕРЕМОЖЕЦЬ!</b> 🏆\n\n"
                f"{user.mention_html()} вибив <b>ДВА СТРАЙКИ</b>!\n\n"
                f"🎳 🎳"
            )
        else:
            win_text = (
                f"🎉 <b>ПЕРЕМОЖЕЦЬ!</b> 🏆\n\n"
                f"{user.mention_html()} вибив <b>ДВА СТРАЙКИ</b>!\n\n"
                f"Вам потрібно активувати бота\n\n"
     
            )

        win_msg = await message.answer(win_text, parse_mode="HTML")
        bowling_messages[chat_id].append(win_msg.message_id)

        # Очищаємо чат — залишаємо тільки стартове + повідомлення про перемогу
        await cleanup_bowling_chat(chat_id, message.bot, protected_extra=win_msg.message_id)

        # Завершуємо гру
        if chat_id in active_bowling_games:
            del active_bowling_games[chat_id]

        return

    # Прогрес (не страйк — не доходимо сюди, але на всяк випадок)
    if strikes > 0:
        progress_msg = await message.answer(
            f"🔥 {user.mention_html()} — <b>{strikes}/2 страйків</b>",
            parse_mode="HTML"
        )
        bowling_messages[chat_id].append(progress_msg.message_id)


async def cleanup_bowling_chat(chat_id: int, bot, protected_extra: int | None = None):
    """Видаляє всі збережені повідомлення крім стартового та protected_extra"""
    if chat_id not in bowling_messages:
        return

    protected = [bowling_messages[chat_id][0]]  # стартове
    if protected_extra:
        protected.append(protected_extra)

    for msg_id in bowling_messages[chat_id]:
        if msg_id in protected:
            continue
        try:
            await bot.delete_message(chat_id=chat_id, message_id=msg_id)
        except:
            pass  # ігноруємо помилки (немає прав, вже видалено тощо)

    # Оновлюємо список — тільки захищені повідомлення
    bowling_messages[chat_id] = [mid for mid in bowling_messages[chat_id] if mid in protected]