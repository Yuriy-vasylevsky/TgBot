from aiogram import Router, F, types
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime, timezone, timedelta
from db import get_all_users_info
from handlers.config import ADMIN_ID
from handlers.menu import main_menu

router = Router(name="admin_users")

USERS_PER_PAGE = 8
MAX_ACTIONS_TO_SHOW = 20


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
        local = dt.astimezone(timezone(timedelta(hours=2)))  # Київ UTC+2
        now = datetime.now(timezone(timedelta(hours=2)))

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
                callback_data=f"user_detail:{user_id}:{page}"
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

    kb.row(
        types.InlineKeyboardButton(
            text="⟲ Оновити список", callback_data=f"users_list:{page}"
        )
    )

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


@router.callback_query(F.data.startswith("user_detail:"))
async def show_user_detail(callback: types.CallbackQuery):
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

    users = await get_all_users_info()
    user = next((u for u in users if u["user_id"] == user_id), None)

    if not user:
        await callback.message.edit_text("Користувача вже немає в базі.")
        return

    full_name = user.get("full_name") or "—"
    username = user.get("username") or "—"
    reg_date = format_time_kyiv(user.get("registered_at"))
    last_active = format_time_kyiv(user.get("last_active"))

    games_played = user.get("games_played", 0)
    games_won = user.get("games_won", 0)
    winrate = round(games_won / games_played * 100) if games_played > 0 else 0

    actions = user.get("last_actions", "")
    actions_list = [a.strip() for a in actions.split("|") if a.strip()]
    actions_show = actions_list[-MAX_ACTIONS_TO_SHOW:]
    actions_text = "\n".join([f"• {act}" for act in actions_show]) or "немає записів"

    text = (
        f"👤 <b>{full_name}</b>\n"
        f"{'@' if username != '—' else ''}{username}\n\n"
        f"🆔 <code>{user_id}</code>\n"
        f"📅 Реєстрація: {reg_date}\n"
        f"🕒 Остання активність: {last_active}\n\n"
        f"🎮 Зіграно: <b>{games_played}</b>\n"
        f"🏆 Виграно: <b>{games_won}</b>  ({winrate}%)\n\n"
        f"<b>Останні дії (до {MAX_ACTIONS_TO_SHOW}):</b>\n"
        f"{actions_text}\n"
    )

    kb = InlineKeyboardBuilder()
    kb.button(text="← Назад до списку", callback_data=f"users_list:{from_page}")

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