from aiogram import Router, F, types
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime, timezone, timedelta
from db import get_all_users_info, search_users, get_issued_checks_for_user, get_all_balances
from handlers.config import ADMIN_ID
from group_games.football_router import is_promo_on_cooldown, get_promo_cooldown_remaining
import aiosqlite
from db import DB_PATH, get_balance, add_to_balance, get_daily_net, get_yesterday_net, update_daily_net, get_daily_game_win, get_yesterday_game_win,get_cashback_status
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State


router = Router(name="admin_users")

USERS_PER_PAGE = 7
MAX_ACTIONS_TO_SHOW = 7
MAX_ACTIONS_EXPANDED = 20


class BalanceFSM(StatesGroup):
    add_amount = State()
    remove_amount = State()


class AdminSearch(StatesGroup):
    waiting_for_query = State()


KYIV = timezone(timedelta(hours=3))


def parse_dt_safe(dt_str: str | None) -> datetime:
    if not dt_str:
        return datetime.min.replace(tzinfo=timezone.utc)
    try:
        dt = datetime.fromisoformat(dt_str)
        if dt.tzinfo is None:
            # Наївні рядки в цій БД (з SQLite DATETIME('now', '+3 hours'))
            # вже зміщені на київський час, а не UTC — тож і тег ставимо київський,
            # інакше порівняння з tz-aware рядками (з save_user) буде хибним.
            dt = dt.replace(tzinfo=KYIV)
        return dt.astimezone(timezone.utc)
    except Exception:
        return datetime.min.replace(tzinfo=timezone.utc)


def format_time_kyiv(dt_str: str | None) -> str:
    if not dt_str:
        return "немає даних"
    try:
        dt = datetime.fromisoformat(dt_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=KYIV)

        now = datetime.now(KYIV)

        if dt.date() == now.date():
            return f"сьогодні о {dt:%H:%M}"
        if dt.date() == (now - timedelta(days=1)).date():
            return f"вчора о {dt:%H:%M}"
        
        return dt.strftime("%d.%m.%Y о %H:%M")
    except Exception as e:
        print(f"Помилка форматування часу: {e}")
        return "—"


async def build_users_keyboard(users: list[dict], page: int, is_search: bool = False, search_query: str | None = None) -> InlineKeyboardBuilder:
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

    # Навігація
    nav_row = []
    if page > 1:
        nav_row.append(
            types.InlineKeyboardButton(
                text="⬅️ Назад", 
                callback_data=f"users_list:{page-1}:{search_query or ''}"
            )
        )
    if end < len(users_sorted):
        nav_row.append(
            types.InlineKeyboardButton(
                text="Далі ➡️", 
                callback_data=f"users_list:{page+1}:{search_query or ''}"
            )
        )

    if nav_row:
        kb.row(*nav_row)

    # Кнопки дій
    kb.row(
        types.InlineKeyboardButton(
            text="🔍 Пошук гравця", 
            callback_data="start_user_search"
        )
    )

    if is_search:
        kb.row(
            types.InlineKeyboardButton(
                text="← До всіх користувачів", 
                callback_data="users_list:1"
            )
        )

    return kb



async def show_users_list(message_or_query, page: int = 1, search_query: str | None = None):
    """Універсальна функція для показу списку або результатів пошуку"""
    
    if search_query:
        users = await search_users(search_query)
        title = f"🔍 Результати пошуку: «{search_query}»"
        is_search = True
    else:
        users = await get_all_users_info()
        title = "👥 Список користувачів"
        is_search = False

    if not users:
        text = f"{title}\n\n🫥 Нічого не знайдено" if search_query else "🫥 Користувачів ще немає"
        kb = InlineKeyboardBuilder()
        if search_query:
            kb.button(text="← До всіх користувачів", callback_data="users_list:1")
        kb_markup = kb.as_markup()
    else:
        kb_builder = await build_users_keyboard(users, page, is_search=is_search, search_query=search_query)
        kb_markup = kb_builder.as_markup()          # ← Головне виправлення
        total_pages = (len(users) + USERS_PER_PAGE - 1) // USERS_PER_PAGE
        text = f"{title} (стор. {page}/{total_pages})\n\n"
        if search_query:
            text += f"Знайдено: <b>{len(users)}</b> користувачів\n\n"

    if isinstance(message_or_query, types.CallbackQuery):
        try:
            await message_or_query.message.edit_text(
                text, 
                reply_markup=kb_markup, 
                parse_mode="HTML", 
                disable_web_page_preview=True
            )
        except Exception:
            await message_or_query.message.answer(
                text, 
                reply_markup=kb_markup, 
                parse_mode="HTML", 
                disable_web_page_preview=True
            )
        await message_or_query.answer()
    else:
        await message_or_query.answer(
            text, 
            reply_markup=kb_markup,          # ← Було помилка тут
            parse_mode="HTML", 
            disable_web_page_preview=True
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
        parts = callback.data.split(":")
        page = int(parts[1])
        search_query = parts[2] if len(parts) > 2 and parts[2] else None
    except:
        page = 1
        search_query = None

    await show_users_list(callback, page=page, search_query=search_query)


# ==================== ПОШУК ====================

@router.callback_query(F.data == "start_user_search")
async def start_user_search(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Доступно лише адміністратору", show_alert=True)
        return

    await state.set_state(AdminSearch.waiting_for_query)
    await callback.message.edit_text(
        "🔍 Введіть ім'я, @username або ID користувача для пошуку:",
        reply_markup=None
    )
    await callback.answer()


@router.message(AdminSearch.waiting_for_query)
async def process_search_query(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return

    query = message.text.strip()
    if len(query) < 1:
        await message.answer("❌ Запит має містити мінімум 2 символи.")
        return

    await state.clear()
    await show_users_list(message, page=1, search_query=query)


# ==================== ДЕТАЛЬНА ІНФОРМАЦІЯ КОРИСТУВАЧА ====================

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
        show_checks = len(parts) > 4 and parts[4] == "1"
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
    daily_net = await get_daily_net(user_id)
    yesterday_net = await get_yesterday_net(user_id)
    daily_game_win = await get_daily_game_win(user_id) 
    yesterday_game_win = await get_yesterday_game_win(user_id)

    cashback_status = await get_cashback_status(user_id)


    cb = cashback_status
    cashback_text = (
        f"💸 <b>Кешбек : <b>{cb['claimed_base']/10}</b></b>\n"
        # f"   Використано: <b>{cb['claimed_base']}</b> грн\n"
        # f"   Доступно: <b>{cb['available_net']}</b> грн\n"
    )

    if cb['can_claim']:
        cashback_text += f"   🎁 Можна забрати: <b>{cb['claim_amount']}</b> грн ✅"
    else:
        cashback_text += f"   📊 Прогрес: <b>{cb['progress_in_tier']}</b> / {1000} грн"


    # ==================== ДІЇ ====================
    actions = user.get("last_actions", "")
    actions_list = [a.strip() for a in actions.split("|") if a.strip()]

    if show_all_actions:
        actions_show = actions_list[-MAX_ACTIONS_EXPANDED:]
        actions_text = "\n".join([f"• {act}" for act in actions_show]) or "немає записів"
        actions_block = f"<b>Останні дії (до {MAX_ACTIONS_EXPANDED}):</b>\n{actions_text}\n"
    else:
        actions_block = ""

    # ==================== КУЛДАУН ====================
    cooldown_text = "❌ Немає кулдауну"
    if await is_promo_on_cooldown(user_id):
        remaining = await get_promo_cooldown_remaining(user_id)
        if remaining:
            h, m = remaining
            cooldown_text = f"⏳ Кулдаун: {h} год {m} хв"

    # ==================== ЧЕКИ ====================
    issued = await get_issued_checks_for_user(user_id)

    kyiv_tz = timezone(timedelta(hours=3))
    now_kyiv = datetime.now(kyiv_tz)
    today = now_kyiv.date()
    yesterday = (now_kyiv - timedelta(days=1)).date()

    def get_check_date(ch):
        try:
            dt = datetime.fromisoformat(ch["issued_at"])
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(kyiv_tz).date()
        except:
            return None

    today_checks = [ch for ch in issued if get_check_date(ch) == today]
    yesterday_checks = [ch for ch in issued if get_check_date(ch) == yesterday]

    def format_checks(checks):
        if not checks:
            return "немає"
        lines = []
        for ch in checks:
            dt = format_time_kyiv(ch["issued_at"])
            lines.append(f"• {ch['check_type']} | <code>{ch['code']}</code> | {dt}")
        return "\n".join(lines)

    today_sum = sum(ch["price"] for ch in today_checks)
    yesterday_sum = sum(ch["price"] for ch in yesterday_checks)
   
    if show_checks:
        checks_block = (
            f"🎁 <b>Чеки сьогодні ({today_sum} грн):</b>\n{format_checks(today_checks)}\n\n"
            f"🗓 <b>Чеки вчора ({yesterday_sum} грн):</b>\n{format_checks(yesterday_checks)}\n"
        )
    else:
        checks_block = ""

    # ==================== ТЕКСТ ====================
    text = (
        f"👤 <b>{full_name}</b>\n"
        f"{'@' + username if username != '—' else f'<a href=\"tg://user?id={user_id}\">{user_id}</a>'}\n\n"
        f"🆔 <code>{user_id}</code>\n"
        f"🕒 Активність: {last_active}\n\n"
        f"🎮 Зібрано промо: <b>{games_played}</b>\n"
        f"💰 Баланс: <b>{balance}</b> грн\n"
        f"📊 Програш сьогодні: <b>{daily_net} грн</b>\n"
        f"📊 Програш <b>вчора</b>: <b>{yesterday_net} грн</b>\n"
        f"🎉 Виграш сьогодні: <b>{daily_game_win} грн</b>\n" 
        f"🎉 Виграш <b>вчора</b>: <b>{yesterday_game_win} грн</b>\n"   
        # f"💸 Кеш {cashback_status} грн\n"  
        f"{cashback_text}\n\n" 
        f"{cooldown_text}\n\n"
        f"{checks_block}\n"
        f"{actions_block}"
    )
    # ==================== КНОПКИ ====================
    kb = InlineKeyboardBuilder()

    kb.button(text="💰 Поповнити баланс", callback_data=f"balance_add:{user_id}:{from_page}")
    kb.button(text="💸 Зняти баланс", callback_data=f"balance_remove:{user_id}:{from_page}")
    kb.button(text="➖1 промо", callback_data=f"ask_remove_promo:{user_id}:{from_page}") 
    kb.button(text="➕1 промо", callback_data=f"ask_add_promo:{user_id}:{from_page}")

    if show_checks:
        kb.button(text="▲ Сховати чеки", callback_data=f"user_detail:{user_id}:{from_page}:{1 if show_all_actions else 0}:0")
    else:
        kb.button(text="🧾 Чеки", callback_data=f"user_detail:{user_id}:{from_page}:{1 if show_all_actions else 0}:1")

    if show_all_actions:
        kb.button(text="▲ Сховати дії", callback_data=f"user_detail:{user_id}:{from_page}:0:{1 if show_checks else 0}")
    else:
        kb.button(text="▼ Останні дії", callback_data=f"user_detail:{user_id}:{from_page}:1:{1 if show_checks else 0}")

    kb.button(text="← Назад до списку", callback_data=f"users_list:{from_page}")

    kb.adjust(2, 2, 2, 1)

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


async def reset_promo_cooldown(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET promo_cooldown_until = NULL WHERE user_id = ?",
            (user_id,)
        )
        await db.commit()


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
    await update_daily_net(user_id, amount)
    balance = await get_balance(user_id)

    await message.answer(
        f"✅ Баланс поповнено на {amount} грн\n\n"
        f"💰 Новий баланс: {balance} грн"
    )

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
    await update_daily_net(user_id, -amount)
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
        f"┌──────────────\n"
        f"  │  💰 <b>БАЛАНСИ ГРАВЦІВ</b>\n"
        f"└──────────────\n\n"
        + "\n\n".join(lines)
        + f"\n\n{'─' * 25}\n"
        f"👥 Гравців з балансом: <b>{len(users)}</b>\n"
        f"💵 Загальна сума: <b>{total} грн</b>\n"
        f"{'─' * 25}"
    )

    if len(text) > 4000:
        # розбиття на частини (як було в оригіналі)
        chunks, chunk = [], ""
        for line in lines:
            if len(chunk) + len(line) > 3900:
                chunks.append(chunk)
                chunk = ""
            chunk += line + "\n\n"
        header = f"┌──────────────\n  │  💰 <b>БАЛАНСИ ГРАВЦІВ</b>\n└──────────────\n\n"
        footer = f"\n{'─' * 10}\n👥 Гравців: <b>{len(users)}</b>\n💵 Загальна сума: <b>{total} грн</b>\n{'─' * 10}"
        chunks[-1] += footer
        for idx, ch in enumerate(chunks):
            await message.answer((header if idx == 0 else "") + ch, parse_mode="HTML")
    else:
        await message.answer(text, parse_mode="HTML")


@router.callback_query(F.data.startswith("ask_add_promo:"))
async def ask_add_promo(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Тільки для адміна", show_alert=True)
        return

    try:
        _, user_id_str, from_page_str = callback.data.split(":")
        user_id = int(user_id_str)
        from_page = int(from_page_str)
    except Exception:
        await callback.answer("Помилка обробки", show_alert=True)
        return

    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Так, додати", callback_data=f"do_add_promo:{user_id}:{from_page}")
    kb.button(text="❌ Ні", callback_data=f"user_detail:{user_id}:{from_page}:0")
    kb.adjust(2)

    try:
        await callback.message.edit_text(
            "Додати 1 промо цьому користувачу?",
            reply_markup=kb.as_markup(),
            disable_web_page_preview=True,
        )
    except Exception:
        await callback.message.answer("Додати 1 промо цьому користувачу?")

    await callback.answer()


@router.callback_query(F.data.startswith("do_add_promo:"))
async def do_add_promo(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Тільки для адміна", show_alert=True)
        return

    try:
        _, user_id_str, from_page_str = callback.data.split(":")
        user_id = int(user_id_str)
        from_page = int(from_page_str)
    except Exception:
        await callback.answer("Помилка обробки", show_alert=True)
        return

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET games_played = games_played + 1 WHERE user_id = ?",
            (user_id,)
        )
        await db.commit()

    await callback.answer("✅ Додано 1 промо!", show_alert=True)
    await show_user_detail(callback.model_copy(update={"data": f"user_detail:{user_id}:{from_page}:0"}))


@router.callback_query(F.data.startswith("ask_remove_promo:"))
async def ask_remove_promo(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Тільки для адміна", show_alert=True)
        return

    try:
        _, user_id_str, from_page_str = callback.data.split(":")
        user_id = int(user_id_str)
        from_page = int(from_page_str)
    except Exception:
        await callback.answer("Помилка обробки", show_alert=True)
        return

    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Так, відняти", callback_data=f"do_remove_promo:{user_id}:{from_page}")
    kb.button(text="❌ Ні", callback_data=f"user_detail:{user_id}:{from_page}:0")
    kb.adjust(2)

    try:
        await callback.message.edit_text(
            "Відняти 1 промо у цього користувача?",
            reply_markup=kb.as_markup(),
            disable_web_page_preview=True,
        )
    except Exception:
        await callback.message.answer("Відняти 1 промо у цього користувача?")

    await callback.answer()


@router.callback_query(F.data.startswith("do_remove_promo:"))
async def do_remove_promo(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Тільки для адміна", show_alert=True)
        return

    try:
        _, user_id_str, from_page_str = callback.data.split(":")
        user_id = int(user_id_str)
        from_page = int(from_page_str)
    except Exception:
        await callback.answer("Помилка обробки", show_alert=True)
        return

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET games_played = MAX(0, games_played - 1) WHERE user_id = ?",
            (user_id,)
        )
        await db.commit()

    await callback.answer("✅ Знято 1 промо!", show_alert=True)
    await show_user_detail(callback.model_copy(update={"data": f"user_detail:{user_id}:{from_page}:0"}))