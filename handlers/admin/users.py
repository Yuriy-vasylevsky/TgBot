

from aiogram import Router, F, types
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime, timezone, timedelta
from db import get_all_users_info
from handlers.config import ADMIN_ID
from handlers.menu import main_menu
from group_games.football_router import is_promo_on_cooldown, get_promo_cooldown_remaining
import aiosqlite
from db import DB_PATH, get_balance, add_to_balance
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from db import get_issued_checks_for_user, get_all_balances


router = Router(name="admin_users")

USERS_PER_PAGE = 7
MAX_ACTIONS_TO_SHOW = 7
MAX_ACTIONS_EXPANDED = 20


class BalanceFSM(StatesGroup):
    add_amount = State()
    remove_amount = State()


def parse_dt_safe(dt_str: str | None) -> datetime:
    if not dt_str:
        return datetime.min.replace(tzinfo=timezone.utc)
    try:
        dt = datetime.fromisoformat(dt_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return datetime.min.replace(tzinfo=timezone.utc)


def format_time_kyiv(dt_str: str | None) -> str:
    if not dt_str:
        return "немає даних"
    try:
        dt = datetime.fromisoformat(dt_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        local = dt.astimezone(timezone(timedelta(hours=3)))
        now = datetime.now(timezone(timedelta(hours=3)))

        if local.date() == now.date():
            return f"сьогодні о {local:%H:%M}"
        if local.date() == (now - timedelta(days=1)).date():
            return f"вчора о {local:%H:%M}"
        return local.strftime("%d.%m.%Y о %H:%M")
    except Exception:
        return "—"


async def build_users_keyboard(users: list[dict], page: int) -> InlineKeyboardBuilder:
    users_sorted = sorted(
        users, key=lambda x: parse_dt_safe(x.get("last_active")), reverse=True
    )

    total_pages = (len(users_sorted) + USERS_PER_PAGE - 1) // USERS_PER_PAGE
    start = (page - 1) * USERS_PER_PAGE
    end = start + USERS_PER_PAGE
    page_users = users_sorted[start:end]

    kb = InlineKeyboardBuilder()

    for idx, user in enumerate(page_users, start=1):
        user_id = user["user_id"]
        full_name = user.get("full_name") or "Без імені"
        name_short = full_name.strip()[:30] or "Без імені"

        kb.row(
            types.InlineKeyboardButton(
                text=f"{idx}. {name_short}",
                callback_data=f"user_detail:{user_id}:{page}:0"
            )
        )

    nav_row = []
    if page > 1:
        nav_row.append(
            types.InlineKeyboardButton(
                text="⬅️ Назад", callback_data=f"users_list:{page-1}"
            )
        )
    if end < len(users_sorted):
        nav_row.append(
            types.InlineKeyboardButton(
                text="Далі ➡️", callback_data=f"users_list:{page+1}"
            )
        )

    if nav_row:
        kb.row(*nav_row)

    # kb.row(
    #     types.InlineKeyboardButton(
    #         text="⟲ Оновити список", callback_data=f"users_list:{page}"
    #     )
    # )

    return kb


async def show_users_list(message_or_query, page: int = 1):
    users = await get_all_users_info()
    if not users:
        text = "🫥 Користувачів ще немає"
        kb = None
    else:
        kb_builder = await build_users_keyboard(users, page)
        text = f"👥 Користувачі (стор. {page})\n\n"
        kb = kb_builder.as_markup()

    if isinstance(message_or_query, types.CallbackQuery):
        try:
            await message_or_query.message.edit_text(
                text, reply_markup=kb, parse_mode="HTML", disable_web_page_preview=True
            )
        except Exception:
            await message_or_query.message.answer(text, reply_markup=kb, parse_mode="HTML")
        await message_or_query.answer()
    else:
        await message_or_query.answer(
            text, reply_markup=kb, parse_mode="HTML", disable_web_page_preview=True
        )


@router.message(F.text == "👥 Список користувачів")
async def cmd_list_users(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    await show_users_list(message, page=1)


@router.callback_query(F.data.startswith("users_list:"))
async def paginate_users_list(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Доступно лише адміністратору", show_alert=True)
        return

    try:
        page = int(callback.data.split(":", 1)[1])
    except:
        page = 1

    await show_users_list(callback, page=page)


async def reset_promo_cooldown(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET promo_cooldown_until = NULL WHERE user_id = ?",
            (user_id,)
        )
        await db.commit()


@router.callback_query(F.data.startswith("user_detail:"))
async def show_user_detail(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Тільки для адміна", show_alert=True)
        return

    try:
        parts = callback.data.split(":")
        user_id = int(parts[1])
        from_page = int(parts[2])
        show_all_actions = len(parts) > 3 and parts[3] == "1"
    except:
        await callback.answer("Помилка обробки", show_alert=True)
        return

    users = await get_all_users_info()
    user = next((u for u in users if u["user_id"] == user_id), None)

    if not user:
        await callback.message.answer("Користувача вже немає в базі.")
        return

    full_name = user.get("full_name") or "—"
    username = user.get("username") or "—"
    last_active = format_time_kyiv(user.get("last_active"))

    games_played = user.get("games_played", 0)
    balance = await get_balance(user_id)

    actions = user.get("last_actions", "")
    actions_list = [a.strip() for a in actions.split("|") if a.strip()]

    limit = MAX_ACTIONS_EXPANDED if show_all_actions else MAX_ACTIONS_TO_SHOW
    actions_show = actions_list[-limit:]
    actions_text = "\n".join([f"• {act}" for act in actions_show]) or "немає записів"

    # Статус кулдауну
    cooldown_text = "❌ Немає кулдауну"
    if await is_promo_on_cooldown(user_id):
        remaining = await get_promo_cooldown_remaining(user_id)
        if remaining:
            h, m = remaining
            cooldown_text = f"⏳ Кулдаун: {h} год {m} хв"

    # Видані чеки за 2 дні
    issued = await get_issued_checks_for_user(user_id)

    if issued:
        total_checks_sum = sum(ch["price"] for ch in issued)
        checks_lines = []
        for ch in issued:
            dt = format_time_kyiv(ch["issued_at"])
            checks_lines.append(f"• {ch['check_type']} | <code>{ch['code']}</code> | {dt}")
        checks_block = "\n".join(checks_lines)
    else:
        total_checks_sum = 0
        checks_block = "ще німа"

    actions_limit_label = MAX_ACTIONS_EXPANDED if show_all_actions else MAX_ACTIONS_TO_SHOW

    text = (
        f"👤 <b>{full_name}</b>\n"
        f"{'@' if username != '—' else ''}{username}\n\n"
        f"🆔 <code>{user_id}</code>\n"
        f"🕒 Активність: {last_active}\n\n"
        f"🎮 Зібрано промо: <b>{games_played}</b>\n"
        f"💰 Баланс: <b>{balance}</b> грн\n"
        f"{cooldown_text}\n\n"
        f"🎁 <b>Видані чеки ({total_checks_sum} грн):</b>\n"
        f"{checks_block}\n\n"
        f"<b>Останні дії (до {actions_limit_label}):</b>\n"
        f"{actions_text}\n"
    )

    kb = InlineKeyboardBuilder()

    kb.button(text="💰 Поповнити баланс", callback_data=f"balance_add:{user_id}:{from_page}")
    kb.button(text="💸 Зняти баланс", callback_data=f"balance_remove:{user_id}:{from_page}")
    kb.button(text="🔄 Скинути кулдаун", callback_data=f"ask_reset:{user_id}:{from_page}")

    if show_all_actions:
        kb.button(text="▲ Сховати дії", callback_data=f"user_detail:{user_id}:{from_page}:0")
    else:
        kb.button(text="▼ Більше дій", callback_data=f"user_detail:{user_id}:{from_page}:1")

    kb.button(text="← Назад до списку", callback_data=f"users_list:{from_page}")

    kb.adjust(2, 2, 1)

    try:
        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=kb.as_markup(),
            disable_web_page_preview=True,
        )
    except Exception:
        await callback.message.answer(text, parse_mode="HTML")

    await callback.answer()


@router.callback_query(F.data.startswith("ask_reset:"))
async def ask_reset_cooldown(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Тільки для адміна", show_alert=True)
        return

    try:
        _, user_id_str, from_page_str = callback.data.split(":")
        user_id = int(user_id_str)
        from_page = int(from_page_str)
    except:
        await callback.answer("Помилка обробки", show_alert=True)
        return

    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Так, скинути", callback_data=f"do_reset:{user_id}:{from_page}")
    kb.button(text="❌ Ні", callback_data=f"user_detail:{user_id}:{from_page}:0")
    kb.adjust(2)

    try:
        await callback.message.edit_text(
            "Ви впевнені, що хочете скинути кулдаун для цього користувача?",
            reply_markup=kb.as_markup(),
            disable_web_page_preview=True,
        )
    except Exception:
        await callback.message.answer("Ви впевнені, що хочете скинути кулдаун?")

    await callback.answer()


@router.callback_query(F.data.startswith("do_reset:"))
async def do_reset_cooldown(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Тільки для адміна", show_alert=True)
        return

    try:
        _, user_id_str, from_page_str = callback.data.split(":")
        user_id = int(user_id_str)
        from_page = int(from_page_str)
    except:
        await callback.answer("Помилка обробки", show_alert=True)
        return

    await reset_promo_cooldown(user_id)
    await callback.answer("✅ Кулдаун скинуто!", show_alert=True)

    # підміняємо callback.data щоб show_user_detail коректно розпарсив
    callback.data = f"user_detail:{user_id}:{from_page}:0"
    await show_user_detail(callback)


@router.callback_query(F.data.startswith("balance_add:"))
async def balance_add_start(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return

    _, user_id, page = callback.data.split(":")

    await state.update_data(user_id=int(user_id), page=int(page))
    await state.set_state(BalanceFSM.add_amount)

    await callback.message.answer("💰 Введіть суму для поповнення балансу:")
    await callback.answer()



@router.message(BalanceFSM.add_amount)
async def balance_add_finish(message: types.Message, state: FSMContext):
    try:
        amount = int(message.text)
    except:
        await message.answer("❌ Введіть число")
        return

    data = await state.get_data()
    user_id = data["user_id"]

    await add_to_balance(user_id, amount)
    balance = await get_balance(user_id)

    await message.answer(
        f"✅ Баланс поповнено на {amount} грн\n\n"
        f"💰 Новий баланс: {balance} грн"
    )

    # сповіщення юзеру
    try:
        await message.bot.send_message(
            user_id,
            f"💰 Вам нараховано <b>{amount} грн</b>\n\n"
            f"💳 Ваш баланс: <b>{balance} грн</b>",
            parse_mode="HTML"
        )
    except Exception:
        await message.answer("⚠️ Не вдалось надіслати сповіщення користувачу")

    await state.clear()

@router.callback_query(F.data.startswith("balance_remove:"))
async def balance_remove_start(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return

    _, user_id, page = callback.data.split(":")

    await state.update_data(user_id=int(user_id), page=int(page))
    await state.set_state(BalanceFSM.remove_amount)

    await callback.message.answer("💸 Введіть суму для списання:")
    await callback.answer()


@router.message(BalanceFSM.remove_amount)
async def balance_remove_finish(message: types.Message, state: FSMContext):
    try:
        amount = int(message.text)
    except:
        await message.answer("❌ Введіть число")
        return

    data = await state.get_data()
    user_id = data["user_id"]

    await add_to_balance(user_id, -amount)
    balance = await get_balance(user_id)

    await message.answer(
        f"✅ Списано {amount} грн\n\n"
        f"💰 Новий баланс: {balance} грн"
    )

    await state.clear()


@router.message(F.text == "💰 Баланси гравців")
async def show_all_balances(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return

    users = await get_all_balances()

    if not users:
        await message.answer("💸 У всіх гравців баланс 0 грн")
        return

    total = sum(u["balance"] for u in users)
    lines = []

    medals = {1: "🥇", 2: "🥈", 3: "🥉"}

    for i, u in enumerate(users, start=1):
        name = (u.get("full_name") or "Без імені")[:20]
        username = f"@{u['username']}" if u.get("username") else f"<code>{u['user_id']}</code>"
        medal = medals.get(i, f"{i}.")
        balance = u["balance"]

        if balance >= 1000:
            bal_str = f"<b>{balance} грн</b> 🔥"
        elif balance >= 500:
            bal_str = f"<b>{balance} грн</b> ⚡️"
        else:
            bal_str = f"<b>{balance} грн</b>"

        lines.append(f"{medal} {name} · {username}\n    └ {bal_str}")

    text = (
        f"┌─────────────────────────\n"
        f"│  💰 <b>БАЛАНСИ ГРАВЦІВ</b>\n"
        f"└─────────────────────────\n\n"
        + "\n\n".join(lines)
        + f"\n\n{'─' * 25}\n"
        f"👥 Гравців з балансом: <b>{len(users)}</b>\n"
        f"💵 Загальна сума: <b>{total} грн</b>\n"
        f"{'─' * 25}"
    )

    if len(text) > 4000:
        chunks, chunk = [], ""
        for line in lines:
            if len(chunk) + len(line) > 3900:
                chunks.append(chunk)
                chunk = ""
            chunk += line + "\n\n"
        header = (
            f"┌─────────────────────────\n"
            f"│  💰 <b>БАЛАНСИ ГРАВЦІВ</b>\n"
            f"└─────────────────────────\n\n"
        )
        footer = (
            f"\n{'─' * 25}\n"
            f"👥 Гравців: <b>{len(users)}</b>\n"
            f"💵 Загальна сума: <b>{total} грн</b>\n"
            f"{'─' * 25}"
        )
        chunks[-1] += footer
        for idx, ch in enumerate(chunks):
            await message.answer((header if idx == 0 else "") + ch, parse_mode="HTML")
    else:
        await message.answer(text, parse_mode="HTML")