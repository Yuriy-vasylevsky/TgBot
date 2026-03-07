# import aiosqlite
# from aiogram import BaseMiddleware
# from aiogram.types import Message, CallbackQuery
# from typing import Callable, Awaitable, Dict, Any
# from pathlib import Path
# from aiogram import Bot, Dispatcher
# from db import DB_PATH
# from db import save_user

# dp = Dispatcher()


# # ==========================
# # Middleware — користувачі
# # ==========================

# class BanMiddleware(BaseMiddleware):
#     async def is_banned(self, user_id: int) -> str | None:
#         """Перевіряє, чи користувач заблокований"""
#         async with aiosqlite.connect(DB_PATH) as db:
#             cursor = await db.execute(
#                 "SELECT reason FROM banned_users WHERE user_id = ?", (user_id,)
#             )
#             row = await cursor.fetchone()
#         return row[0] if row else None

#     async def __call__(
#         self,
#         handler: Callable[[Any, Dict[str, Any]], Awaitable[Any]],
#         event: Message | CallbackQuery,
#         data: Dict[str, Any],
#     ) -> Any:
#         user = getattr(event, "from_user", None)
#         if not user:
#             return await handler(event, data)

#         reason = await self.is_banned(user.id)
#         if reason:
#             try:
#                 text = f"🚫 Ви заблоковані в боті.\nПричина: {reason}"
#                 if isinstance(event, Message):
#                     await event.answer(text)
#                 elif isinstance(event, CallbackQuery):
#                     await event.answer(text, show_alert=True)
#             except Exception:
#                 pass
#             return  # 🛑 Повністю блокуємо далі

#         return await handler(event, data)


# # ==========================
# # Middleware — автозбереження користувача ТІЛЬКИ В ПРИВАТІ
# # ==========================
# from aiogram import BaseMiddleware, types
# import logging


# class SaveUserMiddleware(BaseMiddleware):
#     async def __call__(self, handler, event, data):
#         if not isinstance(event, types.Message):
#             return await handler(event, data)

#         if not event.from_user:
#             return await handler(event, data)

#         # Тільки приватні чати
#         if event.chat.type != "private":
#             return await handler(event, data)

#         text = (event.text or "").strip()

#         # Список текстів, які НЕ потрібно фіксувати як дії
#         ignored_actions = {
#             "1 купон",
#             "2 купони",
#             "3 купони",
#             # за бажанням додай інші кнопки гри, які не хочеш бачити в історії
#             "▶️ Почати гру",
#             "ℹ️ Правила та комбінації",
#             "🔙 Повернутись до ігор",
#         }

#         # Якщо текст — це одна з ігнорованих кнопок → пропускаємо збереження дії
#         if text in ignored_actions:
#             return await handler(event, data)

#         # ────────────── тільки для дозволених повідомлень ──────────────
#         try:
#             # Формуємо короткий опис дії
#             if text:
#                 if len(text) > 60:
#                     action = f"{text[:57]}..."
#                 else:
#                     action = f"{text}"
#             elif event.photo:
#                 action = "відправив фото"
#             elif event.sticker:
#                 action = "відправив стікер"
#             elif event.voice:
#                 action = "відправив голосове"
#             elif event.video:
#                 action = "відправив відео"
#             else:
#                 action = "виконав дію"

#             await save_user(
#                 event.from_user.id,
#                 event.from_user.username or "",
#                 event.from_user.full_name or "",
#                 action=action,
#             )
#         except Exception as e:
#             logging.error(f"Помилка збереження користувача: {e}")

#         return await handler(event, data)


# # Реєстрація залишається без змін
# # dp.message.middleware(SaveUserMiddleware())
import aiosqlite
import logging
from typing import Callable, Awaitable, Dict, Any

from aiogram import BaseMiddleware, types
from aiogram.types import Message, CallbackQuery

# ==================== ІМПОРТИ З НОВОЇ СТРУКТУРИ DB ====================
from db import DB_PATH, save_user


# ==========================
# Middleware — БАН
# ==========================
class BanMiddleware(BaseMiddleware):
    async def is_banned(self, user_id: int) -> str | None:
        """Перевіряє, чи користувач заблокований"""
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
            return  # блокуємо подальшу обробку

        return await handler(event, data)


# ==========================
# Middleware — автозбереження користувача (тільки приват)
# ==========================
class SaveUserMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        if not isinstance(event, types.Message):
            return await handler(event, data)

        if not event.from_user or event.chat.type != "private":
            return await handler(event, data)

        text = (event.text or "").strip()

        # Ігноруємо кнопки, які не хочемо фіксувати в історії
        ignored_actions = {
            "1 купон", "2 купони", "3 купони",
            "▶️ Почати гру",
            "ℹ️ Правила та комбінації",
            "🔙 Повернутись до ігор",
        }

        if text in ignored_actions:
            return await handler(event, data)

        # Формуємо короткий опис дії
        if text:
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
            logging.error(f"Помилка збереження користувача: {e}")

        return await handler(event, data)