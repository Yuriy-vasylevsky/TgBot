

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
import logging
import random
from datetime import datetime

from handlers.config import ADMIN_ID

router = Router(name="group_wordle")

router.message.filter(F.chat.type.in_({"group", "supergroup"}))

# chat_id → {"secret": str, "revealed": list, "messages": list[int]}
active_wordle_games = {}

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
        "messages": []           # сюди будемо складати id повідомлень для видалення
    }

    logging.info(f"🧠 WORDLE ЗАПУЩЕНО в {chat_id} | Слово: {secret_word}")

    start_msg = await message.answer(
        "🧠 <b>WORDLE СТАРТУВАВ!</b>\n\n"
        "Я загадав 5-буквене українське слово.\n"
        "Пишіть свої варіанти в чат!\n\n"
        "🟩 — буква на своєму місці\n"
        "🟨 — буква є, але не там\n"
        "⬛ — такої букви немає\n\n"
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

    if chat_id not in active_wordle_games:
        return

    game = active_wordle_games[chat_id]
    secret = game["secret"]
    revealed = game["revealed"]
    messages = game["messages"]

    # Зберігаємо ID цього повідомлення (спроби користувача)
    messages.append(message.message_id)

    if len(text) != 5 or not all(c in UKRAINIAN_LETTERS for c in text):
        err_msg = await message.answer(
            f"❌ {user.mention_html()}, потрібно **рівно 5 українських букв**!",
            parse_mode="HTML"
        )
        messages.append(err_msg.message_id)
        return

    feedback = get_wordle_feedback(text, secret)

    # Оновлюємо відкриті букви
    for i in range(5):
        if feedback[i] == '🟩' and revealed[i] == "❓":
            revealed[i] = text[i].upper()

    # Зберігаємо повідомлення з відповіддю бота
    response_msg = await message.answer(
        f"{user.mention_html()} → <b>{text.upper()}</b>\n"
        f"{' '.join(feedback)}\n"
        f"{' '.join(revealed)}",
        parse_mode="HTML"
    )
    messages.append(response_msg.message_id)

    if text == secret:
        win_msg = await message.answer(
            f"🎉 <b>ПЕРЕМОЖЕЦЬ!</b> 🏆\n\n"
            f"{user.mention_html()} вгадав слово!\n"
            f"Загадане: <b>{secret.upper()}</b>\n\n"
            f"Гра завершена. Дякую за участь!",
            parse_mode="HTML"
        )
        messages.append(win_msg.message_id)

        # Очищаємо чат — залишаємо тільки стартове + повідомлення про перемогу
        protected = [messages[0], win_msg.message_id]

        for msg_id in messages:
            if msg_id in protected:
                continue
            try:
                await message.bot.delete_message(chat_id=chat_id, message_id=msg_id)
            except:
                pass  # вже видалено / немає прав тощо

        # Оновлюємо список (на випадок, якщо гра перезапускатиметься)
        active_wordle_games[chat_id]["messages"] = protected

        # Завершуємо гру
        del active_wordle_games[chat_id]
        return


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