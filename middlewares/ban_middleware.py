import aiosqlite
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from typing import Callable, Awaitable, Dict, Any
from pathlib import Path
from db import DB_PATH

# DB_PATH = Path(__file__).parent.parent / "users.db"


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
            return  # 🛑 Повністю блокуємо далі

        return await handler(event, data)
