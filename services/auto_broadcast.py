import asyncio
import logging

from aiogram.exceptions import TelegramRetryAfter
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from db.auto_broadcast import enqueue_due, claim_delivery, finish_delivery

logger = logging.getLogger(__name__)


def play_button():
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🎮 Грати", callback_data="auto_broadcast:play")
    ]])


async def run_auto_broadcast(bot):
    while True:
        try:
            await enqueue_due()
            for _ in range(20):
                delivery = await claim_delivery()
                if not delivery:
                    break
                while True:
                    try:
                        await bot.send_photo(
                            delivery['user_id'], delivery['photo'], caption=delivery['caption'],
                            parse_mode=None, reply_markup=play_button(),
                        )
                        await finish_delivery(delivery['id'], 'sent')
                        break
                    except TelegramRetryAfter as error:
                        await finish_delivery(delivery['id'], 'pending')
                        await asyncio.sleep(error.retry_after)
                        break
                    except Exception:
                        logger.exception("Auto broadcast delivery failed: %s", delivery['id'])
                        await finish_delivery(delivery['id'], 'failed')
                        break
                await asyncio.sleep(0.05)
        except Exception:
            logger.exception("Auto broadcast scheduler failed")
        await asyncio.sleep(1)
