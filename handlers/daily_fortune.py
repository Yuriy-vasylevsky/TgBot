import asyncio
import logging
from html import escape
from pathlib import Path

from aiogram import F, Router, types
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter, TelegramNetworkError, TelegramServerError
from db.daily_fortune import MAX_DEPOSIT_BASE, fortune_status, reserve_fortune, release_fortune, settle_fortune
from services.promotions import daily_fortune_enabled
from handlers.config import ADMIN_ID

router = Router(name='daily_deposit_fortune')
logger = logging.getLogger(__name__)


def fortune_keyboard():
    if not daily_fortune_enabled():
        return types.InlineKeyboardMarkup(inline_keyboard=[])
    return types.InlineKeyboardMarkup(inline_keyboard=[[
        types.InlineKeyboardButton(text='🍀 Спробувати удачу', callback_data='daily_fortune:roll')
    ]])


def unavailable(result):
    if result['reason'] == 'no_deposit':
        return 'Для участі потрібен депозит сьогодні. Поповни баланс і спробуй удачу!'
    if result['reason'] == 'pending':
        return '⏳ Попередній кидок обробляється. Якщо результат не з’явиться, звернись до адміністратора.'
    return '✅ Сьогодні ти вже скористався Фортуною. Наступна спроба — завтра після нового депозиту.'


@router.message(F.text == '🎲 Фортуна')
async def open_fortune(message: types.Message):
    result = await fortune_status(message.from_user.id)
    if result['success']:
        caption = f"Останній депозит: <b>{result['deposit_amount']} грн</b>."
    else:
        caption = unavailable(result)
    keyboard = fortune_keyboard() if result['success'] else None
    if result.get('reason') == 'no_deposit':
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[[
            types.InlineKeyboardButton(text='💰 Поповнити', callback_data='wallet_open')
        ]])
    await message.answer_photo(
        photo=types.FSInputFile(Path(__file__).resolve().parent.parent / 'images' / 'kosti.png'),
        caption=caption, parse_mode='HTML',
        reply_markup=keyboard,
    )


@router.callback_query(F.data == 'daily_fortune:roll')
async def roll_fortune(callback: types.CallbackQuery):
    if not callback.message or callback.message.chat.type != 'private':
        await callback.answer('Відкрий Фортуну в особистому чаті з ботом.', show_alert=True)
        return
    result = await reserve_fortune(callback.from_user.id)
    if not result['success']:
        await callback.answer(unavailable(result), show_alert=True)
        return
    attempt_id = result['attempt_id']
    try:
        await callback.answer('🍀 Випробовуємо удачу!')
    except TelegramAPIError:
        pass
    try:
        dice = await callback.message.answer_dice(emoji='🎲')
    except (TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter):
        await release_fortune(attempt_id)
        await callback.message.answer('Не вдалося кинути кубик. Спробуй ще раз — спробу не використано.')
        return
    except (TelegramNetworkError, TelegramServerError):
        logger.exception('Daily fortune dice delivery uncertain | attempt_id=%s user_id=%s', attempt_id, callback.from_user.id)
        await callback.message.answer('⏳ Не вдалося підтвердити кидок. Звернись до адміністратора, щоб перевірити спробу.')
        return
    reward = await asyncio.shield(settle_fortune(attempt_id, dice.dice.value, dice.message_id))
    if reward['bonus'] > 0:
        user = callback.from_user
        username = f" (@{escape(user.username)})" if user.username else ""
        try:
            await callback.bot.send_message(
                ADMIN_ID,
                f"🎲 Виграш у Фортуні!\n\n"
                f'👤 <a href="tg://user?id={user.id}">{escape(user.full_name)}</a>{username}\n'
                f"🆔 ID: <code>{user.id}</code>\n"
                f"🎲 Випало: <b>{reward['value']}</b> ({reward['value'] * 10}%)\n"
                f"💳 Депозит: <b>{reward['deposit_amount']} грн</b>\n"
                f"Сума для розрахунку: <b>{reward['bonus_base']} грн</b>\n"
                f"🎁 Зараховано: <b>+{reward['bonus']} грн</b>",
                parse_mode='HTML',
            )
        except TelegramAPIError:
            logger.exception('Daily fortune admin notification failed | attempt_id=%s user_id=%s', attempt_id, user.id)
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except TelegramBadRequest:
        pass
    await callback.message.answer(
        f"🎲 Випало <b>{reward['value']}</b> — бонус <b>{reward['value'] * 10}%</b>!\n\n"
        f"Депозит: <b>{reward['deposit_amount']} грн</b>\n"
        f"Сума для розрахунку бонусу: <b>{reward['bonus_base']} грн</b>\n"
        f"✅ Зараховано: <b>+{reward['bonus']} грн</b>\n"
        f"💰 Баланс: <b>{reward['balance']} грн</b>", parse_mode='HTML',
    )
