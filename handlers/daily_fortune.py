import asyncio
import logging
from html import escape
from pathlib import Path

from aiogram import F, Router, types
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter, TelegramNetworkError, TelegramServerError
from db.daily_fortune import MAX_DEPOSIT_BASE, fortune_status, reserve_fortune, release_fortune, settle_fortune
from services.promotions import daily_fortune_enabled, daily_darts_enabled
from handlers.config import ADMIN_ID

router = Router(name='daily_deposit_fortune')
logger = logging.getLogger(__name__)
FORTUNE_GROUP_ID = -1001964846494


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
    if not daily_fortune_enabled():
        await message.answer('🎁 Щоденний бонус зараз недоступний. Спробуй пізніше.')
        return
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


@router.message(F.text == '🎁 Щоденний бонус')
async def open_daily_bonus(message: types.Message):
    # The permanent entry point opens the active game directly.
    if daily_darts_enabled():
        await open_darts(message)
    else:
        await open_fortune(message)


@router.callback_query(F.data == 'daily_fortune:roll')
async def roll_fortune(callback: types.CallbackQuery, game='fortune'):
    is_darts = game == 'darts'
    if not (daily_darts_enabled() if is_darts else daily_fortune_enabled()):
        await callback.answer('Щоденний бонус тимчасово недоступний.', show_alert=True)
        return
    emoji = '🎯' if is_darts else '🎲'
    title = 'Дартс' if is_darts else 'Фортуна'
    if not callback.message or callback.message.chat.type != 'private':
        await callback.answer('Відкрий щоденний бонус в особистому чаті з ботом.', show_alert=True)
        return
    result = await reserve_fortune(callback.from_user.id, game=game)
    if not result['success']:
        await callback.answer(unavailable(result).replace('Фортуною', 'щоденним бонусом'), show_alert=True)
        return
    attempt_id = result['attempt_id']
    try:
        await callback.answer('🍀 Випробовуємо удачу!')
    except TelegramAPIError:
        pass
    try:
        dice = await callback.message.answer_dice(emoji=emoji)
    except (TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter):
        await release_fortune(attempt_id)
        await callback.message.answer('Не вдалося виконати кидок. Спробуй ще раз — спробу не використано.')
        return
    except (TelegramNetworkError, TelegramServerError):
        logger.exception('Daily fortune dice delivery uncertain | attempt_id=%s user_id=%s', attempt_id, callback.from_user.id)
        await callback.message.answer('⏳ Не вдалося підтвердити кидок. Звернись до адміністратора, щоб перевірити спробу.')
        return
    reward = await asyncio.shield(settle_fortune(
        attempt_id, dice.dice.value, dice.message_id,
        username=callback.from_user.username, full_name=callback.from_user.full_name,
    ))
    percent = (reward['value'] - 1 if is_darts else reward['value']) * 10
    if reward['bonus'] > 0:
        user = callback.from_user
        username = f" (@{escape(user.username)})" if user.username else ""
        try:
            await callback.bot.send_message(
                ADMIN_ID,
                f"{emoji} Виграш: {title}!\n\n"
                f'👤 <a href="tg://user?id={user.id}">{escape(user.full_name)}</a>{username}\n'
                f"🆔 ID: <code>{user.id}</code>\n"
                f"{emoji} Випало: <b>{reward['value']}</b> ({percent}%)\n"
                f"💳 Депозит: <b>{reward['deposit_amount']} грн</b>\n"
                f"Сума для розрахунку: <b>{reward['bonus_base']} грн</b>\n"
                f"🎁 Зараховано: <b>+{reward['bonus']} грн</b>",
                parse_mode='HTML',
            )
        except TelegramAPIError:
            logger.exception('Daily fortune admin notification failed | attempt_id=%s user_id=%s', attempt_id, user.id)
        try:
            await callback.bot.send_message(
                FORTUNE_GROUP_ID,
                f"{emoji}✨ <b>{title} дарує виграш!</b>\n\n"
                f"🎁 Щойно зараховано <b>+{reward['bonus']} грн</b> бонусу!\n\n"
                "🍀 Вітаємо з виграшем! Нехай щастить і тобі!",
                parse_mode='HTML',
            )
        except TelegramAPIError:
            logger.exception('Daily fortune group notification failed | attempt_id=%s', attempt_id)
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except TelegramBadRequest:
        pass
    await callback.message.answer(
        f"{emoji} Випало <b>{reward['value']}</b> — бонус <b>{percent}%</b>!\n\n"
        f"Депозит: <b>{reward['deposit_amount']} грн</b>\n"
        f"Сума для розрахунку бонусу: <b>{reward['bonus_base']} грн</b>\n"
        f"✅ Зараховано: <b>+{reward['bonus']} грн</b>\n"
        f"💰 Баланс: <b>{reward['balance']} грн</b>", parse_mode='HTML',
    )


async def open_darts(message: types.Message):
    if not daily_darts_enabled():
        await message.answer('🎁 Щоденний бонус зараз недоступний. Спробуй пізніше.')
        return
    result = await fortune_status(message.from_user.id)
    keyboard = None
    if result['success']:
        text = (
            "🎯 <b>Щоденний дартс</b>\n\n"
            "Промах — 0%, далі 10%, 20%, 30%, 40%, центр — 50%!\n"
            f"Останній депозит: <b>{result['deposit_amount']} грн</b>\n"
            f"Бонус рахується із суми до {MAX_DEPOSIT_BASE} грн.\n"
            "Одна спроба на день. Випробуй влучність!"
        )
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[[
            types.InlineKeyboardButton(text='🎯 Кинути дротик', callback_data='daily_darts:roll')
        ]])
    else:
        text = unavailable(result).replace('Фортуною', 'щоденним бонусом')
        if result.get('reason') == 'no_deposit':
            keyboard = types.InlineKeyboardMarkup(inline_keyboard=[[
                types.InlineKeyboardButton(text='💰 Поповнити', callback_data='wallet_open')
            ]])
    await message.answer_photo(
        photo=types.FSInputFile(Path(__file__).resolve().parent.parent / 'images' / 'darc.png'),
        caption=text, parse_mode='HTML', reply_markup=keyboard,
    )


@router.callback_query(F.data == 'daily_darts:roll')
async def roll_darts(callback: types.CallbackQuery):
    await roll_fortune(callback, game='darts')
