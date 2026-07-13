

import aiosqlite
from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from db import ban_user, unban_user, DB_PATH, ensure_ban_table
from handlers.config import ADMIN_ID
from handlers.menu import main_menu, admin_menu2

router = Router(name="admin_bans")


async def is_banned(user_id: int) -> bool:
    """Використовується в middleware та для перевірки доступу до Matic"""
    await ensure_ban_table()
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT 1 FROM banned_users WHERE user_id=?", (user_id,)
        ) as cur:
            row = await cur.fetchone()
            return bool(row)


async def list_banned() -> list[tuple]:
    await ensure_ban_table()
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


def bans_inline_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🚫 Забанити", callback_data="bans_start_ban")],
            [InlineKeyboardButton(text="🔓 Розбанити", callback_data="bans_start_unban")],
            [InlineKeyboardButton(text="📋 Список банів", callback_data="bans_list")],
        ]
    )


def bans_cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❌ Скасувати", callback_data="bans_cancel")]
        ]
    )


# ==========================
# Вхід у меню банів
# ==========================
@router.message(F.text == "🚫 Бани")
async def bans_menu(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ Тільки адміністратор.")
        return
    await message.answer("🚫 <b>Керування банами</b>", parse_mode="HTML", reply_markup=bans_inline_kb())


# ==========================
# 🚫 Бан
# ==========================
@router.callback_query(F.data == "bans_start_ban")
async def cmd_start_ban(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Тільки адміністратор.", show_alert=True)
        return
    await callback.message.edit_text(
        "Введи ID користувача для бану:", reply_markup=bans_cancel_kb()
    )
    await state.set_state(BanStates.waiting_for_ban_id)
    await callback.answer()


@router.message(BanStates.waiting_for_ban_id)
async def handle_ban_id(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Введи тільки числовий ID.", reply_markup=bans_cancel_kb())
        return
    uid = int(message.text)
    if uid == ADMIN_ID:
        await message.answer("⛔ Нельзя банити себе.")
        await state.clear()
        return
    await state.update_data(ban_target=uid)
    await message.answer(
        "Введи причину бану (можеш залишити порожньою):", reply_markup=bans_cancel_kb()
    )
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
        reply_markup=admin_menu2(),
    )


# ==========================
# 🔓 Розбан
# ==========================
@router.callback_query(F.data == "bans_start_unban")
async def cmd_start_unban(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Тільки адміністратор.", show_alert=True)
        return
    await callback.message.edit_text(
        "Введи ID користувача для розбану (тільки цифри):", reply_markup=bans_cancel_kb()
    )
    await state.set_state(BanStates.waiting_for_unban_id)
    await callback.answer()


@router.message(BanStates.waiting_for_unban_id)
async def handle_unban_id(message: Message, state: FSMContext):
    text = message.text.strip()
    if not text.isdigit():
        await message.answer(
            "Невірний формат. Введи тільки числовий ID.", reply_markup=bans_cancel_kb()
        )
        return
    uid = int(text)
    await unban_user(uid)
    await state.clear()
    await message.answer(
        f"✅ Користувач <code>{uid}</code> розблокований.",
        parse_mode="HTML",
        reply_markup=admin_menu2(),
    )


# ==========================
# 📋 Список банів
# ==========================
@router.callback_query(F.data == "bans_list")
async def view_banned_list(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Тільки адміністратор.", show_alert=True)
        return

    await callback.answer()

    rows = await list_banned()
    if not rows:
        await callback.message.answer(
            "📭 Список банів пустий.", reply_markup=admin_menu2()
        )
        return

    lines = []
    for uid, full_name, reason, banned_by, ts in rows:
        name = full_name or "—"
        r = reason if reason else "—"
        lines.append(
            f"👤 <b>{name}</b>\n 🔮ID: <code>{uid}</code>\n 📄Причина: {r}\n🕒 {ts}\n"
        )

    text = "📋 <b>Заблоковані користувачі:</b>\n\n" + "\n".join(lines)
    await callback.message.answer(text, parse_mode="HTML", reply_markup=admin_menu2())


# ==========================
# ❌ Скасування (інлайн-кнопка під час FSM)
# ==========================
@router.callback_query(F.data == "bans_cancel")
async def bans_cancel_inline(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Тільки адміністратор.", show_alert=True)
        return
    await state.clear()
    await callback.message.edit_text("❌ Дію скасовано.")
    await callback.message.answer("🚫 Меню банів:", reply_markup=admin_menu2())
    await callback.answer()


# ==========================
# Скасування стану (текстова команда/кнопка — запасний варіант)
# ==========================
@router.message(F.text.in_({"/cancel", "❌ Відмінити", "скасувати"}))
async def cancel_state(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "❌ Дія скасована.",
        reply_markup=admin_menu2() if message.from_user.id == ADMIN_ID else main_menu(is_admin=False),
    )