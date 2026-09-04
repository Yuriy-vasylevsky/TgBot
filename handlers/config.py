from pathlib import Path
import os
from pathlib import Path
from dotenv import load_dotenv

import os
from pathlib import Path

DATA_DIR = os.environ.get("DATA_DIR", "/data")  
DB_PATH = Path(DATA_DIR) / "users.db"


CONTACT_PHONE = "https://t.me/KaSSa_4444"
GROUP_LINK ="https://t.me/+Z2dJLGrGRVdmM2Yy"


load_dotenv()

TOKEN = os.getenv("TOKEN")
MONO_TOKEN = os.getenv("MONO_TOKEN")
MONO_ACCOUNT = os.getenv("MONO_ACCOUNT", "0")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))
MONO_CARD = os.getenv("MONO_CARD")

import os


MONO_JAR_SEND_ID = os.getenv("MONO_JAR_SEND_ID")
MONO_JAR_LINK = f"https://send.monobank.ua/{MONO_JAR_SEND_ID}" if MONO_JAR_SEND_ID else None
MONO_JAR_CARD = os.getenv("MONO_JAR_CARD")

# ====================== OPENAI / ПЕРЕВІРКА КВИТАНЦІЙ ======================
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"
GPT_MAX_TIME_DIFFERENCE_MINUTES = int(
    os.getenv("GPT_MAX_TIME_DIFFERENCE_MINUTES", "10")
)
OPENAI_TIMEOUT_SECONDS = int(os.getenv("OPENAI_TIMEOUT_SECONDS", "30"))
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "").strip()
DEEPSEEK_VISION_MODEL = (
    os.getenv("DEEPSEEK_VISION_MODEL", "deepseek-v4-flash-vision-exp").strip()
    or "deepseek-v4-flash-vision-exp"
)
DEEPSEEK_TIMEOUT_SECONDS = int(os.getenv("DEEPSEEK_TIMEOUT_SECONDS", "30"))
MAX_RECEIPT_FILE_SIZE_MB = int(os.getenv("MAX_RECEIPT_FILE_SIZE_MB", "10"))
  
CASINO_API_BASE = "https://chcwhite.net"   
CASINO_TR_PREFIX = "BOT_"  
CASINO_TIMEZONE = os.getenv("CASINO_TIMEZONE", "Europe/Kyiv")


CASINO_PUBLIC_KEY = os.getenv("CASINO_PUBLIC_KEY")
CASINO_SECRET_KEY = os.getenv("CASINO_SECRET_KEY")


# ====================== НАЛАШТУВАННЯ ФОРТУНИ ======================
  # Скільки промо потрібно для одного обертання колеса


CARD_NUMBER = """
💳 Карта 1 : 
💳 карта 2 : 

💵 Мінімальний платіж — 200 грн
💸 Мінімальний вивід — 400 грн

⏰ Зверніть увагу: касир доступний з 9:00 до 00:00
🕒 Іноді може бути довше ⏳
"""

HALP = """
Для того, щоб зробити ставку натисніть кнопку «💳Номер карти💳»...
"""

AK1 = """💥 Лови виграш, поки гаряче!
Отримай +25% на Superomatic до свого депозиту від 300грн.

💳 Бонус нараховується миттєво після поповнення рахунку.
💳 Пам’ятай: під час виведення коштів бонусна сума буде утримана."""


AK2 = """🔐 СЕЙФ — Грошовий квест починається! 💥"""
AK3 = """💎 Отримай 10% Cashback!

Поповни рахунок на 1000 грн протягом дня і отримай назад 10% від суми 💰

⚠️ При виводі кешбек за поточний день віднімається ❌ """

AK4 = """ 💎 Промокоди — твій ключ до виграшу! 🏆
"""

AK4_DETAILS = """✨ Як це працює:

♠️Отримай промокод під час акції або від нашого бота 💌
♥️Активуй його — і дізнайся, який подарунок приготувала тобі удача 🎡
♣️Кожен промокод — це твій шанс спіймати хвилю успіху 🌊
♦️Не зволікай — введи свій код і відчуй смак перемоги 🥇
"""

DEMO = """
🎉 Чемпіон 🎉
Тут ви можете безкоштовно зіграти...
https://spinplanet.net/?login_code=00000000000000
"""

LINK1 = "💵💵💵 Чемпіон💵💵💵 скористайтеся ботом..."
LINK2 = "🍀🍀🍀Cуперматік🍀🍀🍀 https://bit.ly/3Lppt0z"
LINK3 = "Або відправте код у цей чат..."

REF = """
⚡️Відправте ваш код у бот...
"""
AK2_CAPTION = "🔓 Відкрий сейф і дізнайся, чи твоя удача сьогодні з тобою! 💥"

# 🔸 Детальний текст акції "Сейф"
AK2_DETAILS = """💥 СЕЙФ — Грошовий квест починається! 💥

⚡️ У нашому віртуальному сейфі захований грошовий приз:
👻 2000 грн! 🔥

🔸 Як взяти участь:
1️⃣ Грай на наших слотах та впіймай бонус 200 грн 🎰
2️⃣ Зроби скріншот і надішли його в чат 💬
3️⃣ Вгадай код із трьох чисел 🧠
4️⃣ Якщо вгадав — 💰 весь сейф твій!
5️⃣ Якщо ні — комбінація потрапить до списку вже спробуваних 🔄

💸 Переможець отримає весь вміст сейфу прямо на свою картку! 💳

🎯 Хто буде найкмітливішим і найвезучішим цього разу?
🔓 Код чекає свого героя…
"""

# 🔸 Короткий опис під відео Superomatic
AK1_CAPTION = "🎮 Superomatic — твій шанс зловити щедрий бонус сьогодні! 💰"

# 🔸 Детальний текст акції Superomatic
AK1_DETAILS = """🔥 Обертай барабани — ми додамо бонусів!

📅 Пн – Чт — отримуй +10% до депозиту

📅 Пт – Нд — вже +25% на рахунок!

💥 Superomatic заряджений на фортуну! 🍀
💰 Акція діє лише для депозитів від 300 грн.
💳 Бонус нараховується одразу після поповнення рахунку! При виводі бонуси вілнімаються 

"""

PROVAIDER = """ 
♦️ Superomatic - https://kod.atlantik.club

🏆 Champion - https://spinplanet.net/

🥇 Чемпіон 🥇
💹Тут ви можете безкоштовно зіграти  

⚡ https://spinplanet.net/?login_code=00000000000000 ⚡
"""

# 💰 💵 💶 💎 🪙 💳 🤑 🏦 💼 💲
# 💸 🪅 🎁 🏆 🥇 🎖️ 🔑 📈 💹 💫

# 🎰 Азарт, ігри та удача

# 🎰 🎲 ♠️ ♥️ ♦️ ♣️ 🃏 🎯 🎮 🎡
# 🎪 🏅 🔮 🍀 🎆 🧩 🎟️ 🕹️ 🏵️ 🔔

# ⚡ Енергія, динаміка, емоції

# ⚡ 🔥 🚀 💥 🌟 ✨ 💫 🌈 🎇 🎉
# 📢 🎤 🕶️ 🧨 💫 🌪️ 🔊 🧠 🧲 🫶

# ❤️ Емоції та атмосфера

# 😎 😏 😇 😈 🤩 😍 🫰 🫡 🥂 🍸
# 🍾 💃 🕺 🤞 🙌 👑 🪩 🌃 🕰️ 🌠
