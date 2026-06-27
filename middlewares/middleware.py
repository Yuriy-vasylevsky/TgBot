import aiosqlite
import logging
from typing import Callable, Awaitable, Dict, Any

from aiogram import BaseMiddleware, types
from aiogram.types import Message, CallbackQuery

from db import DB_PATH, save_user


class BanMiddleware(BaseMiddleware):
    async def is_banned(self, user_id: int) -> str | None:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT reason FROM banned_users WHERE user_id = ?", (user_id,)
            )
            row = await cursor.fetchone()
        return row[0] if row else None

    async def __call__(
        self,
        handler: Callable[[Any, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any],
    ) -> Any:
        user = getattr(event, "from_user", None)
        if not user:
            return await handler(event, data)

        reason = await self.is_banned(user.id)
        if reason:
            try:
                text = f"🚫 Ви заблоковані в боті.\nПричина: {reason}"
                if isinstance(event, Message):
                    await event.answer(text)
                elif isinstance(event, CallbackQuery):
                    await event.answer(text, show_alert=True)
            except Exception:
                pass
            return

        return await handler(event, data)


class SaveUserMiddleware(BaseMiddleware):
    # ⚠️ Не забудьте в main.py зареєструвати middleware ще й на callback_query:
    #   dp.message.middleware(SaveUserMiddleware())
    #   dp.callback_query.middleware(SaveUserMiddleware())   # ← цей рядок треба додати
    async def __call__(self, handler, event, data):
        if isinstance(event, types.Message):
            await self._handle_message(event, data)
        elif isinstance(event, types.CallbackQuery):
            await self._handle_callback(event, data)

        return await handler(event, data)

    async def _handle_message(self, event: types.Message, data: Dict[str, Any]):
        if not event.from_user or event.chat.type != "private":
            return

        # перевіряємо ДО збереження — чи юзер новий
        async with aiosqlite.connect(DB_PATH) as db:
            cur = await db.execute(
                "SELECT 1 FROM users WHERE user_id = ?", (event.from_user.id,)
            )
            row = await cur.fetchone()
            data["is_new_user"] = row is None

        text = (event.text or "").strip()

        ignored_actions = {
            "1 купон", "2 купони", "3 купони",
            "▶️ Почати гру",
            "ℹ️ Правила та комбінації",
            "🔙 Повернутись до ігор",
        }

        if text in ignored_actions:
            action = None
        elif text:
            action = text[:57] + "..." if len(text) > 60 else text
        elif event.photo:
            action = "відправив фото"
        elif event.sticker:
            action = "відправив стікер"
        elif event.voice:
            action = "відправив голосове"
        elif event.video:
            action = "відправив відео"
        else:
            action = "виконав дію"

        try:
            await save_user(
                event.from_user.id,
                event.from_user.username or "",
                event.from_user.full_name or "",
                action=action,
            )
        except Exception as e:
            logging.error(f"Помилка збереження користувача (message): {e}")

    async def _handle_callback(self, event: types.CallbackQuery, data: Dict[str, Any]):
        if not event.from_user:
            return

        message = event.message
        if not message or message.chat.type != "private":
            return

        try:
            await save_user(
                event.from_user.id,
                event.from_user.username or "",
                event.from_user.full_name or "",
                action=None,  # натискання кнопок не пишемо в історію дій, лише оновлюємо last_active
            )
        except Exception as e:
            logging.error(f"Помилка збереження користувача (callback): {e}")