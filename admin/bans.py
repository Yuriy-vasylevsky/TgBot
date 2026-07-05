# import aiosqlite
# from aiogram import Router, F, types
# from aiogram.fsm.context import FSMContext
# from aiogram.fsm.state import StatesGroup, State
# from aiogram.types import Message
# from db import ban_user, unban_user, DB_PATH
# from handlers.config import ADMIN_ID
# from handlers.menu import main_menu

# router = Router(name="admin_bans")


# async def is_banned(user_id: int) -> bool:
#     """Використовується в middleware"""
#     async with aiosqlite.connect(DB_PATH) as db:
#         async with db.execute(
#             "SELECT 1 FROM banned_users WHERE user_id=?", (user_id,)
#         ) as cur:
#             row = await cur.fetchone()
#             return bool(row)


# async def list_banned() -> list[tuple]:
#     async with aiosqlite.connect(DB_PATH) as db:
#         async with db.execute(
#             """
#             SELECT b.user_id, u.full_name, b.reason, b.banned_by, b.ts
#             FROM banned_users b
#             LEFT JOIN users u ON u.user_id = b.user_id
#             ORDER BY b.ts DESC
#             """
#         ) as cur:
#             return await cur.fetchall()


# class BanStates(StatesGroup):
#     waiting_for_ban_id = State()
#     waiting_for_unban_id = State()
#     waiting_for_ban_reason = State()


# # ==========================
# # 🚫 Бан
# # ==========================
# @router.message(F.text == "🚫 Забанити")
# async def cmd_start_ban(message: Message, state: FSMContext):
#     if message.from_user.id != ADMIN_ID:
#         await message.answer("⛔ Тільки адміністратор.")
#         return
#     await message.answer("Введи ID користувача для бану:")
#     await state.set_state(BanStates.waiting_for_ban_id)


# @router.message(BanStates.waiting_for_ban_id)
# async def handle_ban_id(message: Message, state: FSMContext):
#     if not message.text.isdigit():
#         await message.answer("Введи тільки числовий ID.")
#         return
#     uid = int(message.text)
#     if uid == ADMIN_ID:
#         await message.answer("⛔ Нельзя банити себе.")
#         await state.clear()
#         return
#     await state.update_data(ban_target=uid)
#     await message.answer("Введи причину бану (можеш залишити порожньою):")
#     await state.set_state(BanStates.waiting_for_ban_reason)


# @router.message(BanStates.waiting_for_ban_reason)
# async def handle_ban_reason(message: Message, state: FSMContext):
#     data = await state.get_data()
#     uid = data.get("ban_target")
#     reason = message.text.strip() or None
#     await ban_user(uid, banned_by=message.from_user.id, reason=reason)
#     await state.clear()
#     await message.answer(
#         f"✅ Користувач <code>{uid}</code> заблокований.\nПричина: {reason or '—'}",
#         parse_mode="HTML",
#         reply_markup=main_menu(is_admin=True),
#     )


# # ==========================
# # 🔓 Розбан
# # ==========================
# @router.message(F.text == "🔓 Розбанити")
# async def cmd_start_unban(message: Message, state: FSMContext):
#     if message.from_user.id != ADMIN_ID:
#         await message.answer("⛔ Тільки адміністратор.")
#         return
#     await message.answer("Введи ID користувача для розбану (тільки цифри):")
#     await state.set_state(BanStates.waiting_for_unban_id)


# @router.message(BanStates.waiting_for_unban_id)
# async def handle_unban_id(message: Message, state: FSMContext):
#     text = message.text.strip()
#     if not text.isdigit():
#         await message.answer("Невірний формат. Введи тільки числовий ID або /cancel.")
#         return
#     uid = int(text)
#     await unban_user(uid)
#     await state.clear()
#     await message.answer(
#         f"✅ Користувач <code>{uid}</code> розблокований.",
#         parse_mode="HTML",
#         reply_markup=main_menu(is_admin=True),
#     )


# # ==========================
# # 📋 Список банів
# # ==========================
# @router.message(F.text == "📋 Список банів")
# async def view_banned_list(message: Message):
#     if message.from_user.id != ADMIN_ID:
#         await message.answer("⛔ Тільки адміністратор.")
#         return

#     rows = await list_banned()
#     if not rows:
#         await message.answer(
#             "📭 Список банів пустий.", reply_markup=main_menu(is_admin=True)
#         )
#         return

#     lines = []
#     for uid, full_name, reason, banned_by, ts in rows:
#         name = full_name or "—"
#         by = str(banned_by) if banned_by else "—"
#         r = reason if reason else "—"
#         lines.append(
#             f"👤 <b>{name}</b>\n 🔮ID: <code>{uid}</code>\n 📄Причина: {r}\n🕒 {ts}\n"
#         )

#     text = "📋 <b>Заблоковані користувачі:</b>\n\n" + "\n".join(lines)
#     await message.answer(text, parse_mode="HTML", reply_markup=main_menu(is_admin=True))


# # ==========================
# # Скасування стану
# # ==========================
# @router.message(F.text.in_({"/cancel", "❌ Відмінити", "скасувати"}))
# async def cancel_state(message: Message, state: FSMContext):
#     await state.clear()
#     await message.answer(
#         "❌ Дія скасована.",
#         reply_markup=main_menu(is_admin=(message.from_user.id == ADMIN_ID)),
#     )

import aiosqlite
from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message
from db import ban_user, unban_user, DB_PATH, ensure_ban_table
from handlers.config import ADMIN_ID
from handlers.menu import main_menu

router = Router(name="admin_bans")


async def is_banned(user_id: int) -> bool:
    """Використовується в middleware та для перевірки доступу до Matic"""
    await ensure_ban_table()  # гарантуємо, що таблиця існує, перш ніж читати з неї
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT 1 FROM banned_users WHERE user_id=?", (user_id,)
        ) as cur:
            row = await cur.fetchone()
            return bool(row)


async def list_banned() -> list[tuple]:
    await ensure_ban_table()  # гарантуємо, що таблиця існує, перш ніж читати з неї
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            """
            SELECT b.user_id, u.full_name, b.reason, b.banned_by, b.ts
            FROM banned_users b
            LEFT JOIN users u ON u.user_id = b.user_id
            ORDER BY b.ts DESC
            """
        ) as cur:
            return await cur.fetchall()


class BanStates(StatesGroup):
    waiting_for_ban_id = State()
    waiting_for_unban_id = State()
    waiting_for_ban_reason = State()


# ==========================
# 🚫 Бан
# ==========================
@router.message(F.text == "🚫 Забанити")
async def cmd_start_ban(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ Тільки адміністратор.")
        return
    await message.answer("Введи ID користувача для бану:")
    await state.set_state(BanStates.waiting_for_ban_id)


@router.message(BanStates.waiting_for_ban_id)
async def handle_ban_id(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Введи тільки числовий ID.")
        return
    uid = int(message.text)
    if uid == ADMIN_ID:
        await message.answer("⛔ Нельзя банити себе.")
        await state.clear()
        return
    await state.update_data(ban_target=uid)
    await message.answer("Введи причину бану (можеш залишити порожньою):")
    await state.set_state(BanStates.waiting_for_ban_reason)


@router.message(BanStates.waiting_for_ban_reason)
async def handle_ban_reason(message: Message, state: FSMContext):
    data = await state.get_data()
    uid = data.get("ban_target")
    reason = message.text.strip() or None
    await ban_user(uid, banned_by=message.from_user.id, reason=reason)
    await state.clear()
    await message.answer(
        f"✅ Користувач <code>{uid}</code> заблокований.\nПричина: {reason or '—'}",
        parse_mode="HTML",
        reply_markup=main_menu(is_admin=True),
    )


# ==========================
# 🔓 Розбан
# ==========================
@router.message(F.text == "🔓 Розбанити")
async def cmd_start_unban(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ Тільки адміністратор.")
        return
    await message.answer("Введи ID користувача для розбану (тільки цифри):")
    await state.set_state(BanStates.waiting_for_unban_id)


@router.message(BanStates.waiting_for_unban_id)
async def handle_unban_id(message: Message, state: FSMContext):
    text = message.text.strip()
    if not text.isdigit():
        await message.answer("Невірний формат. Введи тільки числовий ID або /cancel.")
        return
    uid = int(text)
    await unban_user(uid)
    await state.clear()
    await message.answer(
        f"✅ Користувач <code>{uid}</code> розблокований.",
        parse_mode="HTML",
        reply_markup=main_menu(is_admin=True),
    )


# ==========================
# 📋 Список банів
# ==========================
@router.message(F.text == "📋 Список банів")
async def view_banned_list(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ Тільки адміністратор.")
        return

    rows = await list_banned()
    if not rows:
        await message.answer(
            "📭 Список банів пустий.", reply_markup=main_menu(is_admin=True)
        )
        return

    lines = []
    for uid, full_name, reason, banned_by, ts in rows:
        name = full_name or "—"
        by = str(banned_by) if banned_by else "—"
        r = reason if reason else "—"
        lines.append(
            f"👤 <b>{name}</b>\n 🔮ID: <code>{uid}</code>\n 📄Причина: {r}\n🕒 {ts}\n"
        )

    text = "📋 <b>Заблоковані користувачі:</b>\n\n" + "\n".join(lines)
    await message.answer(text, parse_mode="HTML", reply_markup=main_menu(is_admin=True))


# ==========================
# Скасування стану
# ==========================
@router.message(F.text.in_({"/cancel", "❌ Відмінити", "скасувати"}))
async def cancel_state(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "❌ Дія скасована.",
        reply_markup=main_menu(is_admin=(message.from_user.id == ADMIN_ID)),
    )