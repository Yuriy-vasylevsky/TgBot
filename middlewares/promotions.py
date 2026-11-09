from aiogram import BaseMiddleware, types
from services.promotions import (
    promotions_enabled, PROMO_BUTTONS, promo_callback,
    piggy_bank_enabled, piggy_callback, disabled_callback,
)


class PromotionsMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        if promotions_enabled() and piggy_bank_enabled():
            return await handler(event, data)
        state = data.get("state")
        current = await state.get_state() if state else None
        pending = not promotions_enabled() and bool(current and current.split(":")[0] in {"PromoFSM", "EnterPromoFSM"})
        promo_blocked = not promotions_enabled() and ((
            isinstance(event, types.Message) and (event.text in PROMO_BUTTONS or pending)
        ) or (isinstance(event, types.CallbackQuery) and promo_callback(event.data)))
        piggy_blocked = not piggy_bank_enabled() and (
            (isinstance(event, types.Message) and event.text == "🐷 Скарбничка")
            or (isinstance(event, types.CallbackQuery) and piggy_callback(event.data))
        )
        if not (promo_blocked or piggy_blocked):
            return await handler(event, data)
        if pending:
            await state.clear()
        text = ("⏸ Скарбничку тимчасово вимкнено." if piggy_blocked
                else "⏸ Промокоди та колесо фортуни тимчасово вимкнено.")
        if isinstance(event, types.CallbackQuery):
            await event.answer(text, show_alert=True)
            if event.message and event.message.reply_markup:
                rows = [
                    filtered for row in event.message.reply_markup.inline_keyboard
                    if (filtered := [b for b in row if not disabled_callback(b.callback_data)])
                ]
                await event.message.edit_reply_markup(
                    reply_markup=types.InlineKeyboardMarkup(inline_keyboard=rows)
                )
        else:
            from handlers.menu import main_menu
            from handlers.config import ADMIN_ID
            await event.answer(text, reply_markup=main_menu(is_admin=event.from_user.id == ADMIN_ID))
