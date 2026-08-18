from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
import asyncio
import logging
import random
import time
from datetime import datetime

from handlers.config import ADMIN_ID
from db import add_money_win, add_daily_game_win
from db.game_cooldown import (
    is_game_on_cooldown,
    get_game_cooldown_remaining,
    set_game_cooldown_for_win,
    GAME_COOLDOWN_HOURS,
    GAME_COOLDOWN_MIN_WIN,
    format_cooldown as format_game_cooldown,
)
from db.wallet import (
    add_to_balance,
    get_daily_net,
    get_yesterday_net,
    get_daily_game_win,
    get_yesterday_game_win,
)

router = Router(name="group_wordle")

router.message.filter(F.chat.type.in_({"group", "supergroup"}))

# chat_id → стан гри (слово, відкриті літери, повідомлення та lock)
active_wordle_games = {}

PRIZE_AMOUNT = 50
WIN_COOLDOWN_HOURS = GAME_COOLDOWN_HOURS

# user_id → час, до якого діє кулдаун "вже вигравав"
winners_cooldown = {}


# =====================================
# ДОПОМІЖНІ (кулдауни/виплата — як у skarb)
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
        await set_game_cooldown_for_win(user_id, payout_amount)

        from db.winlog import log_win
        await log_win(user_id, None, name, "group", "Wordle", payout_amount)

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


# === ВСІ СЛОВА (тільки 5-буквені) ===
RAW_WORDS = [
    "аарон", "аахен", "абаза", "абазь", "абака", "аббас", "абвер", "абзац", "абиде", "абияк",
    "аборт", "абощо", "абрек", "абрис", "абхаз", "аваль", "аванс", "авдій", "авеню", "аврал",
    "аврам", "автол", "автор", "агава", "агеєв", "агент", "аґрус", "адамс", "адась", "аделя",
    "адепт", "адрес", "ажажа", "ажгон", "ажень", "ажнюк", "азарт", "азіат", "акант", "акорд",
    "актив", "акула", "акциз", "акція", "алжир", "алібі", "аллах", "алмаз", "алтай", "альфа",
    "алюмн", "алярм", "амбар", "амбон", "амвон", "аміак", "ампір", "ангар", "аніме", "аніон",
    "аніта", "аннюк", "анонс", "антей", "антик", "антін", "анфас", "аорта", "апажа", "апака",
    "апсид", "аргон", "ареал", "арена", "арешт", "арина", "аркан", "аркуш", "армія", "аруба",
    "архів", "асєєв", "аскер", "аскет", "астма", "аська", "атака", "атаки", "атлас", "атлет",
    "атюша", "афект", "афера", "афікс", "ахати", "бабак", "бабах", "бабин", "бабій", "бабка",
    "бабня", "багач", "багно", "баддя", "бажан", "бажик", "базар", "базис", "байка", "байло",
    "байор", "бакай", "бакан", "бакун", "бакша", "балет", "балик", "балія", "балка", "балюк",
    "баляс", "банан", "банер", "бануш", "баняк", "барак", "баран", "барва", "бареж", "баржа",
    "барит", "бариш", "барій", "барка", "барок", "барон", "басак", "баско", "басок", "басюк",
    "батий", "батир", "батіг", "батон", "бахір", "бахур", "бачук", "башта", "бащак", "баюра",
    "бгати", "бебик", "бевзь", "бевка", "бегей", "бедик", "безус", "бейдж", "бекас", "белах",
    "бемба", "бенюк", "бердо", "берет", "берло", "берма", "бетон", "бешко", "бидло", "бидля",
    "бикив", "билля", "бинда", "битка", "битки", "биток", "битюг", "битюк", "бицюк", "бичок",
    "блоха", "бобер", "бобри", "бубон", "будяк", "буран", "буряк", "бусол", "бутон", "вагон",
    "вазон", "варан", "вдача", "вечір", "вишня", "вікно", "віник", "вірка", "вітер", "вовна",
    "волик", "ворона", "вудка", "газон", "гараж", "гірка", "гопак", "горіх", "горох", "горло",
    "гроза", "гроно", "гроші", "груша", "гуска", "двері", "диван", "дощик", "дрова", "дятел",
    "жабка", "живіт", "жінка", "жупан", "зайці", "замок", "здача", "зірка", "злива", "зміна",
    "зомбі", "кабан", "кавун", "казка", "калач", "качка", "качан", "килим", "кілок", "кішка",
    "книга", "кобра", "козел", "комар", "комод", "корба", "котик", "крупа", "крига", "крило",
    "криса", "крона", "курка", "курча", "лампа", "лимон", "ложка", "лопух", "майка", "мавпа",
    "масло", "миска", "мишка", "мозок", "молот", "мороз", "нірка", "нічка", "палац", "папір",
    "перон", "пиріг", "пісня", "плече", "плита", "поріг", "потяг", "проза", "просо", "пшоно",
    "пупок", "рабин", "ранок", "ринок", "річка", "робот", "роман", "рукав", "садок", "серце",
    "силач", "скоба", "скала", "слива", "слово", "сніг", "сонце", "сонях", "сорок", "сорома",
    "стадо", "стіна", "сходи", "такса", "татко", "театр", "теніс", "тісто", "трава", "тукан",
    "тумба", "фільм", "флора", "фраза", "хата", "хобот", "хмара", "цапля", "цегла", "цокіт",
    "цукор", "чашка", "чобіт", "човен", "школа", "шкіра", "штука", "щітка", "явище", "яблук",
    "ялина", "банка", "буква", "гілка", "гірка", "дочка", "думка", "земля", "зерно", "казка",
    "карти", "книжка", "кошка", "листя", "ліжко", "лісник", "майка", "медик", "місто", "ніжка",
    "овес", "папка", "пляж", "радіо", "свічка", "сірка", "сніг", "сова", "танк", "тіло", "факт",
    "хата", "цифра", "чашка", "шафа", "щипці", "юшка", "яблук", "ялина", "борщ", "вагон",
    "весна", "вовна", "газон", "гірка", "гостя", "дочка", "дядько", "жінка", "зірка", "кішка",
    "книжка", "листя", "місто", "нічка", "овес", "папка", "пісня", "пляж", "радіо", "річка",
    "свічка", "сірка", "сніг", "сова", "танк", "тіло", "трав", "факт", "хата", "цифра", "чашка",
    "шафа", "щипці", "юшка", "яблук", "ялина"
]

WORDLE_WORDS = [w for w in RAW_WORDS if len(w) == 5]

UKRAINIAN_LETTERS = set("абвгґдеєжзиіїйклмнопрстуфхцчшщьюя")


def get_wordle_feedback(guess: str, secret: str) -> str:
    result = ['⬛'] * 5
    secret_list = list(secret)

    # Спочатку зелені (точне місце)
    for i in range(5):
        if guess[i] == secret_list[i]:
            result[i] = '🟩'
            secret_list[i] = None

    # Потім жовті (є, але не там)
    for i in range(5):
        if result[i] == '⬛' and guess[i] in secret_list:
            result[i] = '🟨'
            secret_list[secret_list.index(guess[i])] = None

    return ''.join(result)


# ==========================
# ЗАПУСК ГРИ (тільки адмін)
# ==========================
@router.message(Command("wordle"))
async def start_wordle(message: Message):
    if message.from_user.id != ADMIN_ID:
        try:
            await message.delete()
        except:
            pass
        return

    chat_id = message.chat.id
    secret_word = random.choice(WORDLE_WORDS)

    active_wordle_games[chat_id] = {
        "secret": secret_word,
        "revealed": ["❓"] * 5,
        "messages": [],          # сюди будемо складати id повідомлень для видалення
        "winner_id": None,
        "lock": asyncio.Lock(),
    }

    logging.info(f"🧠 WORDLE ЗАПУЩЕНО в {chat_id} | Слово: {secret_word}")

    start_msg = await message.answer(
        "🧠 <b>WORDLE СТАРТУВАВ!</b>\n\n"
        "Я загадав 5-буквене українське слово.\n"
        "Пишіть свої варіанти в чат!\n\n"
        "🟩 — буква на своєму місці\n"
        "🟨 — буква є, але не там\n"
        "⬛ — такої букви немає\n\n"
        f"<b>Приз — {PRIZE_AMOUNT} грн!</b>\n"
        "<b>Перший, хто вгадає — переможець!</b> 🏆\n"
        "Усі спроби будуть очищені після перемоги.",
        parse_mode="HTML"
    )

    # Зберігаємо стартове повідомлення (його НЕ видаляти)
    active_wordle_games[chat_id]["messages"].append(start_msg.message_id)

    # Видаляємо команду /wordle
    try:
        await message.delete()
    except:
        pass


# ==========================
# ОБРОБКА СПРОБ
# ==========================
@router.message(
    F.text,
    lambda m: m.chat.id in active_wordle_games
)
async def handle_wordle(message: Message):
    chat_id = message.chat.id
    user = message.from_user
    text = message.text.strip().lower()

    game = active_wordle_games.get(chat_id)
    if game is None:
        return

    if len(text) != 5 or not all(c in UKRAINIAN_LETTERS for c in text):
        return  # ігноруємо все, що не схоже на спробу — не смітимо в чат

    # Усі спроби однієї гри обробляються по черзі. Після очікування lock
    # обов'язково звіряємо об'єкт гри: за цей час її могли завершити або
    # перезапустити. Це гарантує рівно одного переможця.
    async with game["lock"]:
        if active_wordle_games.get(chat_id) is not game:
            return
        if game["winner_id"] is not None:
            return

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

        # Правильна відповідь резервує перемогу до першої відправки або
        # виплати. Інші одночасні обробники побачать winner_id та завершаться.
        if text == secret:
            game["winner_id"] = user.id

        messages.append(message.message_id)
        feedback = get_wordle_feedback(text, secret)

        for i in range(5):
            if feedback[i] == '🟩' and revealed[i] == "❓":
                revealed[i] = text[i].upper()

        response_msg = await message.answer(
            f"{user.mention_html()} → <b>{text.upper()}</b>\n"
            f"{' '.join(feedback)}\n"
            f"{' '.join(revealed)}",
            parse_mode="HTML"
        )
        messages.append(response_msg.message_id)

        if text != secret:
            return

        name = f"@{user.username}" if user.username else user.full_name

        win_msg = await message.answer(
            f"🎉 <b>ПЕРЕМОЖЕЦЬ!</b> 🏆\n\n"
            f"{user.mention_html()} вгадав слово!\n"
            f"Загадане: <b>{secret.upper()}</b>\n\n"
            f"Гра завершена. Дякую за участь!",
            parse_mode="HTML"
        )
        messages.append(win_msg.message_id)

        # Нарахування призу з перевіркою депозиту та ліміту виграшів
        payout_amount = await _payout_winner(chat_id, message.bot, user.id, name, PRIZE_AMOUNT)

        # Кулдаун на годину ставимо ТІЛЬКИ якщо гроші реально нарахувались
        if payout_amount >= GAME_COOLDOWN_MIN_WIN:
            winners_cooldown[user.id] = time.time() + WIN_COOLDOWN_HOURS * 3600

        # Очищаємо чат — залишаємо тільки стартове + повідомлення про перемогу
        protected = [messages[0], win_msg.message_id]

        for msg_id in messages:
            if msg_id in protected:
                continue
            try:
                await message.bot.delete_message(chat_id=chat_id, message_id=msg_id)
            except:
                pass  # вже видалено / немає прав тощо

        # Завершуємо гру
        if active_wordle_games.get(chat_id) is game:
            del active_wordle_games[chat_id]


# Опціонально: команда для примусового завершення / очищення (для адміна)
@router.message(Command("wordle_stop"))
async def stop_wordle(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    chat_id = message.chat.id
    if chat_id not in active_wordle_games:
        await message.answer("Активної гри Wordle в цьому чаті немає.")
        return

    # Очищаємо майже все
    messages = active_wordle_games[chat_id].get("messages", [])
    if messages:
        protected = [messages[0]]  # залишаємо тільки стартове
        for msg_id in messages:
            if msg_id in protected:
                continue
            try:
                await message.bot.delete_message(chat_id=chat_id, message_id=msg_id)
            except:
                pass

    del active_wordle_games[chat_id]
    await message.answer("Гра Wordle примусово завершена та очищена.")
    try:
        await message.delete()
    except:
        pass
