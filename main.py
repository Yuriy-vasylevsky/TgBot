import logging
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from apscheduler.schedulers.background import BackgroundScheduler
from keep_alive import keep_alive
import re

# Вставте ваш токен сюди
TOKEN = '6333700659:AAHI1d1K-WbKQq4IXSb23rSNeOShPZZCbZg'

# Група та контактні дані
GROUP_LINK = 'https://t.me/+Z2dJLGrGRVdmM2Yy'
CONTACT_PHONE = 'https://t.me/KaSSa_4444'
CARD_NUMBER = """
Приват : 5169 3600 2817 8204
Ощад : 4790 7299 2105 9994

Мінімальний платіж 200 грн
Мінімальний вивід 300 грн

Зверніть увагу, що касир доступний з 9:00 до 00:00
"""


HALP = """Для того, щоб зробити ставку натисніть кнопку 

«💳Номер карти💳»,

Вам прийдуть актуальні реквізити.

Відправте на неї сумму яку бажаєте зарахувати на чек, а потім
надішліть нашому касиру підтвердження переводу (Скрін). 

Тоді касир відправить Вам код для гри."""

AK2 = """⚡️У нас є віртуальний сейф, в якому знаходиться грошовий приз:
2️⃣0️⃣0️⃣0️⃣ грн. 

⚡️Сейф має кодовий замок  із комбінацією від 1️⃣ до 2️⃣5️⃣0️⃣. 

⚡️Щоб спробувати підібрати код вам потрібно спіймати на наших слотах бонус 2️⃣0️⃣0️⃣ грн і викласти скріншот в чат   

⚡️Якщо комбінація не підійшла то вона буде закреслена тут : https://docs.google.com/spreadsheets/d/1q7K4lYwFzwhKFxtdNone5bsJdyh5yQ_enFmpAurnpXw/edit?usp=sharing 👀

⚡️Переможець отримує весь вміст сейфу💵 на свою картку😱.

"""

AK1 = """Щоденна акція 
Після того як ви зіграли, ви можете кинути кубик в групі один раз на денью Якщо випаде 4, 5 чи 6 отримуєте 50 грн на новий код
"""

AK3 = """Cash Back
Cash Back (страхувальна сума) повернення частини грошових коштів(10%) у випадку негативного результату гри гостя за період доби (від 1000грн.).
"""

DEMO = """ 🎉 Чемпіон 🎉

Тут ви можете безкоштовно зіграти та подивитися, які слоти є в наявності!

https://spinplanet.net/?login_code=00000000000000

🎰✨Приєднуйтесь до захопливого світу ігор і відчуйте азарт як ніколи раніше! 🎰✨
"""

LINK1 = """   💵💵💵 Чемпіон💵💵💵

  скористайтеся ботом щоб зробити ссилку

  """

LINK2 = """   🍀🍀🍀Cуперматік🍀🍀🍀

 Щоб зайти в гру введіть код тут - https://bit.ly/3Lppt0z

 """

LINK3 = """   
Або відправте код у цей чат  

(для прикладу відправте цей)
00-00-00-00-00-00-00

і він поверне вам ссилку на гру, оберіть відповідну платформу та вперед до нових перемог
 """

REF = """  ⚡️Відправте ваш код в чат у цьому боті 

(для прикладу відправте цей)
00-00-00-00-00-00-00

⚡️ І він поверне вам ссилку на гру.

⚡️ Оберіть відповідну платформу та вперед до нових перемог 🍀"""

# Налаштування логування
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO)
logger = logging.getLogger(__name__)


# Функція для створення головного меню
def main_menu():
    keyboard = [['💫 КОД в посилання'], ['🎲 Група', '💎 Касир'],
                ['💳 Номер карти', '❓ Як грати'],
                ['💲 Вивід', '🎴 Посилання на ігри'], ['🔹 Акції', '💥 Демо гра']]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def actions_menu():
    keyboard = [['🔙 Повернутись до головного меню'],
                ['🎮 Морський бій', '🎲 Сейф'], ['🃏 Cash Back']]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обробник команди /start"""
    await update.message.reply_photo(photo='./4444.jpg')
    await update.message.reply_text(""" 
    🎰 НАЙКРАЩИЙ ІГРОВИЙ ДОСВІД ЧЕКАЄ НА ВАС У ЧЕТВІРКАХ! 🎰
        
    🔹 Чотири виміри АЗАРТУ!
    
    🔹 Знайди їх у SLOTS
        
    🔹 Приєднуйтесь до захопливого світу ігор і відчуйте азарт як ніколи раніше!""",
    
    reply_markup=main_menu())

            # Меню основне

# Код в посилання
async def send_ref(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:

    await update.message.reply_text(f'{REF}')

#  """Відправка посилання на групу"""
async def send_group_link(update: Update,
context: ContextTypes.DEFAULT_TYPE) -> None:
   
    await update.message.reply_text(
    f'Приєднуйтесь до нашої групи: {GROUP_LINK}')

  # """Відправка посилання на групу"""
async def send_money(update: Update,
                     context: ContextTypes.DEFAULT_TYPE) -> None:
  
    await update.message.reply_text(
        f'Для виводу напишіть нашому касиру: {CONTACT_PHONE}')

# """Відправка контакту касира"""
async def send_contact(update: Update,
                       context: ContextTypes.DEFAULT_TYPE) -> None:
 
    await update.message.reply_text(f'Касир:  {CONTACT_PHONE}')

# """Відправка номеру карти"""
async def send_card_number(update: Update,
                           context: ContextTypes.DEFAULT_TYPE) -> None:
  
    await update.message.reply_text(f'{CARD_NUMBER}')

# """Відправка інструкції по іграм"""
async def send_halp(update: Update,
                    context: ContextTypes.DEFAULT_TYPE) -> None:
 
    await update.message.reply_text(f'{HALP}')

# """Демо гра"""
async def send_demo(update: Update,
                    context: ContextTypes.DEFAULT_TYPE) -> None:

    await update.message.reply_text(f'{DEMO}')

# """Силки на ігри"""
async def send_link(update: Update,
                    context: ContextTypes.DEFAULT_TYPE) -> None:

    await update.message.reply_text(f'{LINK1}')
    await update.message.reply_text(f'{LINK2}')
    await update.message.reply_text(f'{LINK3}')

            # Акції

# """Морський бій"""
async def send_mb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
  
    await update.message.reply_photo(photo='./1.jpg')
    await update.message.reply_text(f'{AK1}')

# Сейф
async def send_seif(update: Update,
                    context: ContextTypes.DEFAULT_TYPE) -> None:

    await update.message.reply_photo(photo='./2.jpg')
    await update.message.reply_text(f'{AK2}')

# Кешбек
async def send_cash(update: Update,
                    context: ContextTypes.DEFAULT_TYPE) -> None:

    await update.message.reply_photo(photo='./3.jpg')
    await update.message.reply_text(f'{AK3}')



# """Обробка кодів"""
async def handle_message(update: Update,
                         context: ContextTypes.DEFAULT_TYPE) -> None:
    
    text = update.message.text

    # Регулярний вираз для перевірки формату коду
    code_pattern = re.compile(r'^\d{2}-\d{2}-\d{2}-\d{2}-\d{2}-\d{2}-\d{2}$')
    if code_pattern.match(text):
        code = text.replace('-', '')
        await update.message.reply_text(
            f'Чемпіон https://spinplanet.net/?login_code={code}')
        await update.message.reply_text(
            f'Суперматік https://code.greenhost.pw/?c={code}')
        return

    if text == '🎲 Група':
        await send_group_link(update, context)
    elif text == '💎 Касир':
        await send_contact(update, context)
    elif text == '💳 Номер карти':
        await send_card_number(update, context)
    elif text == '❓ Як грати':
        await send_halp(update, context)
    elif text == '🔹 Акції':
        await update.message.reply_text('Оберіть одну з наших акцій:',
        reply_markup=actions_menu())
    elif text == '🎴 Посилання на ігри':
        await send_link(update, context)
    elif text == '💫 КОД в посилання':
        await send_ref(update, context)
    elif text == '💲 Вивід':
        await send_money(update, context)
    elif text == '💥 Демо гра':
        await send_demo(update, context)
    elif text == '🎮 Морський бій':
        await send_mb(update, context)
    elif text == '🎲 Сейф':
        await send_seif(update, context)
    elif text == '🃏 Cash Back':
        await send_cash(update, context)
    elif text == '🔙 Повернутись до головного меню':
        await update.message.reply_text(
            'Якщо виникли питання, напишіть касиру https://t.me/KaSSa_4444',
            reply_markup=main_menu())
    else:
        await update.message.reply_text(
            "Будь ласка, використовуйте меню для взаємодії. Або відправте код у такому форматі: 00-00-00-00-00-00-00"
        )

# async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
#     print(f"Chat ID: {update.effective_chat.id}")  # 🔹 Ось цей рядок
    
#     text = update.message.text


def main() -> None:
    """Запуск бота."""

    # Створіть додаток
    keep_alive()
    application = Application.builder().token(TOKEN).build()

    # Додайте обробники команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Запуск бота
    try:
        application.run_polling(timeout=60)  # Збільшення тайм-ауту до 60 секунд
    except Exception as e:
        logger.error(f"Сталася помилка: {e}")  # Логування помилок

if __name__ == '__main__':
    main()

