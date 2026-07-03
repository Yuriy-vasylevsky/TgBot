from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
import logging
import random
import time

from handlers.config import ADMIN_ID
from db import add_money_win, add_daily_game_win
from db.game_cooldown import (
    is_game_on_cooldown,
    get_game_cooldown_remaining,
    set_game_cooldown,
    format_cooldown as format_game_cooldown,
)
from db.wallet import (
    add_to_balance,
    get_daily_net,
    get_yesterday_net,
    get_daily_game_win,
    get_yesterday_game_win,
)

router = Router(name="group_numbers")

router.message.filter(F.chat.type.in_({"group", "supergroup"}))

# chat_id → {"secret": str, "revealed": list[str], "messages": list[int]}
active_numbers_games = {}

PRIZE_AMOUNT = 50
WIN_COOLDOWN_HOURS = 1

# user_id → час, до якого діє кулдаун "вже вигравав"
winners_cooldown = {}


# =====================================
# ДОПОМІЖНІ (кулдауни/виплата — як у wordle)
# =====================================

def _positive_or_zero(value: int) -> int:
    return value if value > 0 else 0


def is_on_cooldown(user_id: int) -> tuple[bool, int]:
    if user_id in winners_cooldown:
        remaining = winners_cooldown[user_id] - time.time()
        if remaining > 0:
            return True, int(remaining)
        del winners_cooldown[user_id]
    return False, 0


def format_cooldown(remaining_seconds: int) -> str:
    hours = remaining_seconds // 3600
    minutes = (remaining_seconds % 3600) // 60
    seconds = remaining_seconds % 60
    parts = []
    if hours: parts.append(f"{hours}г")
    if minutes: parts.append(f"{minutes}хв")
    if seconds and not hours and not minutes: parts.append(f"{seconds}с")
    return " ".join(parts) or "менше хвилини"


async def _payout_winner(chat_id: int, bot, user_id: int, name: str, taken: int) -> int:
    """Повертає суму, яку реально нараховано на баланс (0, якщо нічого не нараховано)."""
    if taken <= 0:
        return 0

    today_net = await get_daily_net(user_id)
    yesterday_net = await get_yesterday_net(user_id)
    total_net = _positive_or_zero(today_net) + _positive_or_zero(yesterday_net)

    if total_net <= 0:
        # Немає депозиту — гроші не нараховуємо, кулдаун гри НЕ ставимо
        await bot.send_message(
            chat_id=chat_id,
            text=(
                f"👤 <b>{name}</b> — виграш <b>{taken} грн</b>\n"
                f"❌ Не було депозиту! Виграш не нараховано❗"
            ),
            parse_mode="HTML"
        )
        return 0

    daily_game_win = await get_daily_game_win(user_id)
    yesterday_game_win = await get_yesterday_game_win(user_id)

    already_won = _positive_or_zero(daily_game_win) + _positive_or_zero(yesterday_game_win)
    # Ліміт пропорційний депозиту: 80 грн на кожні 200 грн депу
    max_allowed_win = int(total_net * 80 / 200)
    available_limit = max(max_allowed_win - already_won, 0)

    payout_amount = min(taken, available_limit)

    if payout_amount > 0:
        await add_to_balance(user_id, payout_amount)
        await add_daily_game_win(user_id, payout_amount)
        # Кулдаун гри ставимо ТІЛЬКИ якщо гроші реально нараховано на баланс
        await set_game_cooldown(user_id)

        from db.winlog import log_win
        await log_win(user_id, None, name, "group", "Secret Code", payout_amount)

    await add_money_win(user_id, taken)

    if payout_amount >= taken:
        await bot.send_message(
            chat_id=chat_id,
            text=(
                f"👤 <b>{name}</b> — виграш <b>{taken} грн</b>\n"
                f"✅ Нараховано на баланс 💸"
            ),
            parse_mode="HTML"
        )
    elif payout_amount > 0:
        await bot.send_message(
            chat_id=chat_id,
            text=(
                f"👤 <b>{name}</b> — виграш <b>{taken} грн</b>\n"
                f"⚠️ Ліміт виграшів вичерпано.\n"
                f"Вам зараховано <b>{payout_amount} грн</b> на баланс."
            ),
            parse_mode="HTML"
        )
    else:
        # Ліміт вичерпано повністю — нічого не нараховано, кулдаун гри НЕ ставимо
        await bot.send_message(
            chat_id=chat_id,
            text=(
                f"👤 <b>{name}</b> — виграш <b>{taken} грн</b>\n"
                f"❌ Ліміт виграшів вичерпано."
            ),
            parse_mode="HTML"
        )

    return payout_amount


@router.message(Command("numbers"))
async def start_numbers(message: Message):
    if message.from_user.id != ADMIN_ID:
        try:
            await message.delete()
        except:
            pass
        return

    chat_id = message.chat.id
    secret = f"{random.randint(0, 99999):05d}"

    active_numbers_games[chat_id] = {
        "secret": secret,
        "revealed": ["❓"] * 5,
        "messages": []
    }

    logging.info(f"🔢 NUMBERS ЗАПУЩЕНО в {chat_id} | Число: {secret}")

    start_msg = await message.answer(
        "🔑 <b>SECRET CODE</b> 🔑\n\n"
        "Я загадав 5-значне число (від 00000 до 99999).\n"
        "Пишіть рівно 5 цифр у чат!\n\n"
        "🟩 — цифра на правильному місці\n"
        "🟨 — цифра є, але не там\n"
        "⬛ — такої цифри немає\n\n"
        f"<b>Приз — {PRIZE_AMOUNT} грн!</b>\n"
        "<b>Перший, хто вгадає — переможець!</b> 🏆\n"
        "Після перемоги чат буде очищено (залишиться тільки старт + перемога).",
        parse_mode="HTML"
    )

    # Зберігаємо ID стартового повідомлення — його не видаляти
    active_numbers_games[chat_id]["messages"].append(start_msg.message_id)

    # Видаляємо команду /numbers
    try:
        await message.delete()
    except:
        pass


def get_feedback(guess: str, secret: str) -> str:
    result = ['⬛'] * 5
    secret_list = list(secret)

    # Спочатку точні збіги (зелені)
    for i in range(5):
        if guess[i] == secret_list[i]:
            result[i] = '🟩'
            secret_list[i] = None  # позначаємо як використану

    # Потім неточні збіги (жовті)
    for i in range(5):
        if result[i] == '⬛' and guess[i] in secret_list:
            result[i] = '🟨'
            secret_list[secret_list.index(guess[i])] = None

    return ''.join(result)


@router.message(
    F.text,
    lambda m: m.chat.id in active_numbers_games
)
async def handle_numbers(message: Message):
    chat_id = message.chat.id
    user = message.from_user
    text = message.text.strip()

    if chat_id not in active_numbers_games:
        return

    if len(text) != 5 or not text.isdigit():
        return  # ігноруємо все, що не схоже на спробу — не смітимо в чат

    game = active_numbers_games[chat_id]
    secret = game["secret"]
    revealed = game["revealed"]
    messages = game["messages"]

    # --- Кулдаун "вже вигравав" (1 година після перемоги) ---
    on_cd, rem = is_on_cooldown(user.id)
    if on_cd:
        cd_msg = await message.answer(
            f"⏳ {user.mention_html()}, ти вже вигравав!\n"
            f"Наступна гра через {format_cooldown(rem)}",
            parse_mode="HTML"
        )
        messages.append(message.message_id)
        messages.append(cd_msg.message_id)
        return

    # --- Загальний ігровий кулдаун (спільний для всіх ігор) ---
    if await is_game_on_cooldown(user.id):
        remaining = await get_game_cooldown_remaining(user.id)
        cd_text = format_game_cooldown(*remaining) if remaining else "невідомо"
        cd_msg = await message.answer(
            f"⏳ {user.mention_html()}, не так швидко! Зачекай ще {cd_text}",
            parse_mode="HTML"
        )
        messages.append(message.message_id)
        messages.append(cd_msg.message_id)
        return

    # Зберігаємо повідомлення гравця
    messages.append(message.message_id)

    feedback = get_feedback(text, secret)

    # Оновлюємо відкриті цифри
    for i in range(5):
        if feedback[i] == '🟩' and revealed[i] == "❓":
            revealed[i] = text[i]

    # Зберігаємо відповідь бота
    resp_msg = await message.answer(
        f"{user.mention_html()} → <b>{text}</b>\n"
        f"{' '.join(feedback)}\n"
        f"{' '.join(revealed)}",
        parse_mode="HTML"
    )
    messages.append(resp_msg.message_id)

    # Перемога
    if text == secret:
        name = f"@{user.username}" if user.username else user.full_name

        win_msg = await message.answer(
            f"🎉 <b>ПЕРЕМОЖЕЦЬ!</b> 🏆\n\n"
            f"{user.mention_html()} вгадав число!\n"
            f"Загадане: <b>{secret}</b>\n\n"
            "Гра завершена. Дякую за участь!",
            parse_mode="HTML"
        )
        messages.append(win_msg.message_id)

        # Нарахування призу з перевіркою депозиту та ліміту виграшів
        payout_amount = await _payout_winner(chat_id, message.bot, user.id, name, PRIZE_AMOUNT)

        # Кулдаун на годину ставимо ТІЛЬКИ якщо гроші реально нарахувались
        if payout_amount > 0:
            winners_cooldown[user.id] = time.time() + WIN_COOLDOWN_HOURS * 3600

        # Захищені повідомлення: стартове + перемога
        protected = [messages[0], win_msg.message_id]

        # Видаляємо все інше
        for msg_id in messages:
            if msg_id in protected:
                continue
            try:
                await message.bot.delete_message(chat_id=chat_id, message_id=msg_id)
            except:
                pass  # вже видалено / немає прав / бот заблокований тощо

        # Завершуємо гру
        del active_numbers_games[chat_id]
        return


# Опціонально — примусове завершення для адміна
@router.message(Command("numbers_stop"))
async def stop_numbers(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    chat_id = message.chat.id
    if chat_id not in active_numbers_games:
        await message.answer("Активної гри «Secret Code» в цьому чаті немає.")
        return

    messages = active_numbers_games[chat_id].get("messages", [])
    if messages:
        protected = [messages[0]]  # тільки стартове
        for msg_id in messages:
            if msg_id in protected:
                continue
            try:
                await message.bot.delete_message(chat_id=chat_id, message_id=msg_id)
            except:
                pass

    del active_numbers_games[chat_id]
    await message.answer("Гра «Secret Code» примусово завершена та очищена.")
    try:
        await message.delete()
    except:
        pass