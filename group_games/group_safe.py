

import asyncio
import time

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
import random
import re
import string
from html import escape
from handlers.config import ADMIN_ID
from db import close_safe_round_and_credit, get_safe_state, save_safe_state

router = Router(name="group_safe")

WIN_CELL = 198
TOTAL_CELLS = 250
BREAK_SAFE_CELLS = 125
BREAK_VOTE_SECONDS = 7 * 60
BREAK_REQUIRED_YES = 4
break_vote_lock = asyncio.Lock()
_UNSET = object()


def parse_cells(text: str) -> list[int]:
    """Extract cells from text, including dot-separated numbers and ranges."""
    cells = []
    pattern = r"(?<!\d)(\d+)\s*-\s*(\d+)(?!\d)|(?<!\d)(\d+)(?!\d)"

    for match in re.finditer(pattern, text):
        if match.group(3) is not None:
            cells.append(int(match.group(3)))
            continue

        start, end = int(match.group(1)), int(match.group(2))
        if start > end:
            start, end = end, start
        cells.extend(range(start, end + 1))

    return sorted(set(cells))


async def load_state() -> dict:
    state = await get_safe_state()
    if not state or not isinstance(state, dict):
        state = {}
    
    state.setdefault("opened", [])
    state.setdefault("win_cell", WIN_CELL)
    state.setdefault("users", {})          # ← вже було
    state.setdefault("break_vote", None)
    return state


async def save_state(opened=None, win_cell=None, users=None, break_vote=_UNSET):
    """Оновлена версія — автоматично очищає лідерборд при повному скиданні сейфа"""
    current = await load_state()
    
    new_opened = list(opened) if opened is not None else current["opened"]
    new_win_cell = win_cell if win_cell is not None else current["win_cell"]
    
    # 🔥 ОСНОВНА ФІШКА: якщо сейф повністю очищається — скидаємо і users
    if opened is not None and len(new_opened) == 0:
        new_users = {}
    else:
        new_users = users if users is not None else current.get("users", {})

    new_break_vote = (
        current.get("break_vote") if break_vote is _UNSET else break_vote
    )
    if opened is not None and len(new_opened) == 0:
        new_break_vote = None

    updated = {
        "opened": new_opened,
        "win_cell": new_win_cell,
        "users": new_users,
        "break_vote": new_break_vote,
    }
    await save_safe_state(updated)

async def get_win_cell() -> int:
    state = await get_safe_state()
    return state.get("win_cell", WIN_CELL)


def generate_promocode(length: int = 8) -> str:
    chars = string.ascii_uppercase + string.digits
    return "".join(random.choices(chars, k=length))


def get_safe_top_five(users: dict) -> list[dict]:
    return sorted(
        [
            {
                "user_id": int(user_id),
                "display_name": user.get("display_name") or str(user_id),
                "count": int(user.get("count", 0)),
            }
            for user_id, user in users.items()
            if int(user.get("count", 0)) > 0
        ],
        key=lambda user: user["count"],
        reverse=True,
    )[:5]


def break_safe_button(state: dict) -> InlineKeyboardMarkup | None:
    if len(state.get("opened", [])) < BREAK_SAFE_CELLS:
        return None
    if state.get("break_vote"):
        return InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(
                text="🗳 Голосування вже триває", callback_data="safe:break_active"
            )
        ]])
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="🔨 Розбити сейф і поділити 1000 грн",
            callback_data="safe:break_start",
        )
    ]])


def safe_status_text(state: dict) -> str:
    return (
        "🔒 <b>СЕЙФ 250</b> 🔒\n\n"
        f"🔓 Відкрито: <b>{len(state.get('opened', []))}</b> / {TOTAL_CELLS}\n"
        "🏆 Виграшний номер: <b>❓❓❓</b>\n\n"
        "🔗 <a href='http://77.42.71.244:8080/'>Переглянути Сейф</a>"
    )


def break_vote_keyboard(vote: dict) -> InlineKeyboardMarkup:
    votes = vote.get("votes", {})
    yes_count = sum(choice == "yes" for choice in votes.values())
    no_count = sum(choice == "no" for choice in votes.values())
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text=f"✅ За ({yes_count})", callback_data="safe:break_vote:yes"
        ),
        InlineKeyboardButton(
            text=f"❌ Проти ({no_count})", callback_data="safe:break_vote:no"
        ),
    ]])


def break_vote_text(vote: dict) -> str:
    votes = vote.get("votes", {})
    yes_count = sum(choice == "yes" for choice in votes.values())
    no_count = sum(choice == "no" for choice in votes.values())
    waiting = max(0, len(vote.get("members", {})) - len(votes))
    return (
        "🔨 <b>ГОЛОСУВАННЯ ЗА РОЗБИТТЯ СЕЙФА</b>\n\n"
        f"Якщо щонайменше {BREAK_REQUIRED_YES} гравці з топ-5 проголосують «За», "
        "сейф буде розбито без вгадування номера, а 1000 грн — поділено "
        "між топ-5 пропорційно клітинкам.\n\n"
        f"✅ За: <b>{yes_count}</b> / {BREAK_REQUIRED_YES}\n"
        f"❌ Проти: <b>{no_count}</b>\n"
        f"⏳ Ще не проголосували: <b>{waiting}</b>\n\n"
        "Час голосування: <b>7 хвилин</b>. Відсутній голос зараховується як «Проти»."
    )


def telegram_message_url(message: Message) -> str | None:
    if message.chat.username:
        return f"https://t.me/{message.chat.username}/{message.message_id}"
    chat_id = str(message.chat.id)
    if chat_id.startswith("-100"):
        return f"https://t.me/c/{chat_id[4:]}/{message.message_id}"
    return None


async def finish_break_vote(bot, state: dict, vote: dict, success: bool) -> None:
    members = vote.get("members", {})
    votes = vote.get("votes", {})
    yes_count = sum(choice == "yes" for choice in votes.values())
    missing_count = max(0, len(members) - len(votes))
    explicit_no = sum(choice == "no" for choice in votes.values())
    no_count = explicit_no + missing_count

    if success:
        awards = await close_safe_round_and_credit(
            state.get("win_cell", WIN_CELL), prize_users=members
        )
        awards_lines = "\n".join(
            f"{place}. {escape(award['display_name'])} — <b>{award['amount']} грн</b>"
            for place, award in enumerate(awards, 1)
        )
        result_text = (
            "🔨 <b>СЕЙФ РОЗБИТО!</b> 🎉\n\n"
            f"✅ За: <b>{yes_count}</b>\n❌ Проти: <b>{no_count}</b>\n\n"
            "💰 <b>1000 грн автоматично нараховано як депозит:</b>\n"
            f"{awards_lines}"
        )
        for award in awards:
            try:
                await bot.send_message(
                    award["user_id"],
                    f"🔨 Сейф розбито голосуванням!\n"
                    f"💰 Вам автоматично нараховано {award['amount']} грн на депозит.",
                )
            except Exception:
                pass
    else:
        await save_state(
            opened=state.get("opened", []),
            win_cell=state.get("win_cell", WIN_CELL),
            users=state.get("users", {}),
            break_vote=None,
        )
        result_text = (
            "🔒 <b>СЕЙФ НЕ РОЗБИТО</b>\n\n"
            f"✅ За: <b>{yes_count}</b>\n❌ Проти: <b>{no_count}</b>\n\n"
            f"Потрібно щонайменше {BREAK_REQUIRED_YES} голоси «За». "
            "Гру можна продовжувати."
        )

    try:
        await bot.edit_message_text(
            result_text,
            chat_id=vote["chat_id"],
            message_id=vote["message_id"],
            parse_mode="HTML",
        )
    except Exception:
        pass


async def break_vote_timeout(bot, ends_at: float) -> None:
    await asyncio.sleep(max(0, ends_at - time.time()))
    async with break_vote_lock:
        state = await load_state()
        vote = state.get("break_vote")
        if not vote or float(vote.get("ends_at", 0)) != ends_at:
            return
        yes_count = sum(choice == "yes" for choice in vote.get("votes", {}).values())
        await finish_break_vote(bot, state, vote, yes_count >= BREAK_REQUIRED_YES)


@router.startup()
async def resume_break_vote(bot: Bot) -> None:
    state = await load_state()
    vote = state.get("break_vote")
    if vote:
        asyncio.create_task(
            break_vote_timeout(bot, float(vote.get("ends_at", time.time())))
        )


# ==========================
# ПОКАЗАТИ СЕЙФ (група)
# ==========================
@router.message(Command("safe"))
async def show_safe(message: Message):
    state = await load_state()
    await message.answer(
        safe_status_text(state),
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=break_safe_button(state),
    )


@router.callback_query(F.data == "safe:break_active")
async def safe_break_active(callback: CallbackQuery):
    await callback.answer("🗳 Голосування вже триває в групі.", show_alert=True)


@router.callback_query(F.data == "safe:break_start")
async def safe_break_start(callback: CallbackQuery):
    async with break_vote_lock:
        state = await load_state()
        if len(state.get("opened", [])) < BREAK_SAFE_CELLS:
            await callback.answer(
                f"Потрібно відкрити щонайменше {BREAK_SAFE_CELLS} клітинок.",
                show_alert=True,
            )
            return
        if state.get("break_vote"):
            await callback.answer("Голосування вже триває.", show_alert=True)
            return

        top_five = get_safe_top_five(state.get("users", {}))
        if callback.from_user.id not in {user["user_id"] for user in top_five}:
            await callback.answer(
                "Запустити голосування можуть лише гравці з топ-5.",
                show_alert=True,
            )
            return

        members = {
            str(user["user_id"]): {
                "display_name": user["display_name"],
                "count": user["count"],
            }
            for user in top_five
        }
        ends_at = time.time() + BREAK_VOTE_SECONDS
        vote = {
            "chat_id": callback.message.chat.id,
            "message_id": 0,
            "started_by": callback.from_user.id,
            "ends_at": ends_at,
            "members": members,
            "votes": {},
        }
        voting_message = await callback.message.answer(
            break_vote_text(vote),
            parse_mode="HTML",
            reply_markup=break_vote_keyboard(vote),
        )
        vote["message_id"] = voting_message.message_id
        await save_state(
            opened=state.get("opened", []),
            win_cell=state.get("win_cell", WIN_CELL),
            users=state.get("users", {}),
            break_vote=vote,
        )
        asyncio.create_task(break_vote_timeout(callback.bot, ends_at))

    vote_url = telegram_message_url(voting_message)
    notification_markup = None
    if vote_url:
        notification_markup = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🗳 Перейти до голосування", url=vote_url)
        ]])
    for user in top_five:
        try:
            await callback.bot.send_message(
                user["user_id"],
                "🔨 У групі почалося голосування за розбиття сейфа.\n"
                "Ви входите до топ-5 — проголосуйте протягом 7 хвилин.\n"
                "Якщо не проголосувати, голос буде зараховано як «Проти».",
                reply_markup=notification_markup,
            )
        except Exception:
            pass
    await callback.answer("🗳 Голосування запущено!")


@router.callback_query(F.data.startswith("safe:break_vote:"))
async def safe_break_vote(callback: CallbackQuery):
    choice = callback.data.rsplit(":", 1)[-1]
    if choice not in {"yes", "no"}:
        return

    async with break_vote_lock:
        state = await load_state()
        vote = state.get("break_vote")
        if not vote:
            await callback.answer("Це голосування вже завершено.", show_alert=True)
            return
        if (
            callback.message.chat.id != vote.get("chat_id")
            or callback.message.message_id != vote.get("message_id")
        ):
            await callback.answer("Це голосування вже неактивне.", show_alert=True)
            return

        user_id = str(callback.from_user.id)
        if user_id not in vote.get("members", {}):
            await callback.answer(
                "Голосувати можуть лише гравці з топ-5.", show_alert=True
            )
            return
        if time.time() >= float(vote.get("ends_at", 0)):
            yes_count = sum(
                item == "yes" for item in vote.get("votes", {}).values()
            )
            await finish_break_vote(
                callback.bot, state, vote, yes_count >= BREAK_REQUIRED_YES
            )
            await callback.answer("Час голосування завершився.", show_alert=True)
            return

        vote.setdefault("votes", {})[user_id] = choice
        await save_state(
            opened=state.get("opened", []),
            win_cell=state.get("win_cell", WIN_CELL),
            users=state.get("users", {}),
            break_vote=vote,
        )
        yes_count = sum(item == "yes" for item in vote["votes"].values())
        if yes_count >= BREAK_REQUIRED_YES:
            await finish_break_vote(callback.bot, state, vote, True)
            await callback.answer("✅ Ваш голос зараховано. Сейф розбито!")
            return

        await callback.message.edit_text(
            break_vote_text(vote),
            parse_mode="HTML",
            reply_markup=break_vote_keyboard(vote),
        )
        await callback.answer("✅ Голос зараховано")


# ==========================
# АДМІН ВІДКРИВАЄ КЛІТИНКУ
# ==========================




# @router.message(Command("open"))
# async def admin_open_cell(message: Message):
#     if message.from_user.id != ADMIN_ID:
#         return

#     # ==========================
#     # ОТРИМУЄМО ГРАВЦЯ + МЕНШЕН
#     # ==========================
#     target_user = None
#     mention = ""
#     if message.reply_to_message and message.reply_to_message.from_user:
#         target_user = message.reply_to_message.from_user
#         if target_user.username:
#             mention = f"@{target_user.username}"
#         else:
#             mention = f"<a href='tg://user?id={target_user.id}'>{target_user.full_name}</a>"
#         mention = f"<b>{mention}</b> "

#     # ==========================
#     # ПАРСИНГ + ВСІ ПЕРЕВІРКИ (без змін)
#     # ==========================
#     if len(message.text.split()) < 2:
#         await message.answer(f"{mention}❌ Формат:\n<code>/open 123</code> ...", parse_mode="HTML")
#         return

#     raw_arg = message.text.split(maxsplit=1)[1].strip()
#     cleaned = raw_arg.replace(", ", ",").replace(" ,", ",")
#     parts = cleaned.replace(",", " ").split()

#     cells_to_open = []
#     for part in parts:
#         part = part.strip()
#         if not part: continue
#         if "-" in part:
#             try:
#                 start, end = map(int, part.split("-"))
#                 if start > end: start, end = end, start
#                 cells_to_open.extend(range(start, end + 1))
#             except:
#                 await message.answer(f"{mention}❌ Некоректний діапазон: {part}", parse_mode="HTML")
#                 return
#         else:
#             try:
#                 cells_to_open.append(int(part))
#             except:
#                 await message.answer(f"{mention}❌ Не число: {part}", parse_mode="HTML")
#                 return

#     if not cells_to_open:
#         await message.answer(f"{mention}❌ Не вдалося розпізнати жодного числа", parse_mode="HTML")
#         return

#     cells_to_open = sorted(set(cells_to_open))

#     if any(c < 1 or c > TOTAL_CELLS for c in cells_to_open):
#         await message.answer(f"{mention}❌ Клітинки повинні бути від 1 до {TOTAL_CELLS}", parse_mode="HTML")
#         return
#     if len(cells_to_open) > 50:
#         await message.answer(f"{mention}❌ Максимум 50 клітинок за раз", parse_mode="HTML")
#         return

#     # ==========================
#     # РОБОТА З БАЗОЮ + ЗАПИС ГРАВЦЯ
#     # ==========================
#     state = await load_state()
#     opened = set(state["opened"])
#     win_cell = state.get("win_cell", WIN_CELL)
#     users = state["users"].copy()                     # <-- копія для оновлення

#     already_opened = [c for c in cells_to_open if c in opened]
#     new_cells = [c for c in cells_to_open if c not in opened]

#     if not new_cells:
#         await message.answer(f"{mention}⚠️ <b>Всі вказані клітинки вже відкриті!</b>", parse_mode="HTML")
#         return

#     # === ЗАПИСУЄМО ГРАВЦЯ (якщо є reply) ===
#     if target_user and new_cells:
#         user_id = str(target_user.id)
#         display_name = f"@{target_user.username}" if target_user.username else target_user.full_name
        
#         current_count = users.get(user_id, {}).get("count", 0)
#         users[user_id] = {
#             "display_name": display_name,           # оновлюється при кожному відкритті
#             "count": current_count + len(new_cells)
#         }

#     opened.update(new_cells)
#     await save_state(opened=opened, win_cell=win_cell, users=users)   # зберігаємо все

#     # ==========================
#     # ВИГРАШ
#     # ==========================
#     if win_cell in new_cells:
#         await message.answer(
#             f"{mention}🎉 <b>СЕЙФ ЗЛОМАНО!</b> 🏆\n\n"
#             f"🔓 Клітинка <b>{win_cell}</b> — ВИГРАШНА!\n"
#             f"💰 Виграш: <b>2000 грн</b>",
#             parse_mode="HTML"
#         )
#         await message.bot.send_message(
#             ADMIN_ID,
#             f"🎉 СЕЙФ ЗЛОМАНО!\nГравець: {mention.strip()}\nКлітинка: {win_cell}",
#             parse_mode="HTML"
#         )
#         return

#     # ==========================
#     # НЕ ВГАДАЛИ
#     # ==========================
#     skipped = f"\n⚠️ Вже були відкриті: {', '.join(map(str, already_opened))}" if already_opened else ""
#     opened_str = ', '.join(map(str, new_cells))

#     await message.answer(
#         f"{mention}❌ <b>Не вгадали!</b> ❌\n\n"
#         f"✅ Перевірено: <b>{len(new_cells)}</b> клітинок\n"
#         f"Номери: <b>{opened_str}</b>{skipped}",
#         parse_mode="HTML"
#     )



@router.message(Command("open"))
async def admin_open_cell(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    # ==========================
    # ОБОВ'ЯЗКОВО ПОВИНЕН БУТИ REPLY НА ГРАВЦЯ
    # ==========================
    if not message.reply_to_message or not message.reply_to_message.from_user:
        await message.answer(
            "⚠️ Щоб відкрити клітинки, потрібно відповісти командою "
            "<code>/open ...</code> на повідомлення гравця.\n\n"
            "Приклад:\n"
            "1. Гравець пише: <code>15 25 37</code>\n"
            "2. Адмін робить Reply на це повідомлення\n"
            "3. Пише: <code>/open</code>",
            parse_mode="HTML"
        )
        return

    # Не дозволяємо відкривати клітинки у відповідь на повідомлення бота
    if message.reply_to_message.from_user.is_bot:
        await message.answer(
            "⚠️ Команда повинна бути відповіддю на повідомлення гравця, а не бота.",
            parse_mode="HTML"
        )
        return

    # ==========================
    # ОТРИМУЄМО ГРАВЦЯ + МЕНШЕН
    # ==========================
    target_user = message.reply_to_message.from_user

    if target_user.username:
        mention = f"@{target_user.username}"
    else:
        mention = (
            f"<a href='tg://user?id={target_user.id}'>"
            f"{target_user.full_name}</a>"
        )

    mention = f"<b>{mention}</b> "

    # ==========================
    # ПАРСИНГ + ВСІ ПЕРЕВІРКИ
    # ==========================
    replied_text = (
        message.reply_to_message.text
        or message.reply_to_message.caption
        or ""
    )
    cells_to_open = parse_cells(replied_text)

    if not cells_to_open:
        await message.answer(
            f"{mention}❌ У повідомленні гравця не вдалося розпізнати жодного числа",
            parse_mode="HTML"
        )
        return

    if any(c < 1 or c > TOTAL_CELLS for c in cells_to_open):
        await message.answer(
            f"{mention}❌ Клітинки повинні бути від 1 до {TOTAL_CELLS}",
            parse_mode="HTML"
        )
        return

    # ==========================
    # РОБОТА З БАЗОЮ + ЗАПИС ГРАВЦЯ
    # ==========================
    state = await load_state()
    opened = set(state["opened"])
    win_cell = state.get("win_cell", WIN_CELL)
    users = state["users"].copy()

    already_opened = [c for c in cells_to_open if c in opened]
    new_cells = [c for c in cells_to_open if c not in opened]

    if not new_cells:
        await message.answer(
            f"{mention}⚠️ <b>Всі вказані клітинки вже відкриті!</b>",
            parse_mode="HTML"
        )
        return

    # ==========================
    # ЗАПИСУЄМО ГРАВЦЯ
    # ==========================
    user_id = str(target_user.id)

    display_name = (
        f"@{target_user.username}"
        if target_user.username
        else target_user.full_name
    )

    current_count = users.get(user_id, {}).get("count", 0)

    users[user_id] = {
        "display_name": display_name,
        "count": current_count + len(new_cells)
    }

    opened.update(new_cells)

    await save_state(
        opened=opened,
        win_cell=win_cell,
        users=users
    )

    # ==========================
    # ВИГРАШ
    # ==========================
    if win_cell in new_cells:
        await message.answer(
            f"{mention}🎉 <b>СЕЙФ ЗЛОМАНО!</b> 🏆\n\n"
            f"🔓 Клітинка <b>{win_cell}</b> — ВИГРАШНА!\n"
            f"💰 Виграш: <b>2000 грн</b>",
            parse_mode="HTML"
        )

        await message.bot.send_message(
            ADMIN_ID,
            f"🎉 СЕЙФ ЗЛОМАНО!\n"
            f"Гравець: {display_name}\n"
            f"Клітинка: {win_cell}",
            parse_mode="HTML"
        )

        return

    # ==========================
    # НЕ ВГАДАЛИ
    # ==========================
    skipped = (
        f"\n⚠️ Вже були відкриті: {', '.join(map(str, already_opened))}"
        if already_opened
        else ""
    )

    opened_str = ", ".join(map(str, new_cells))

    await message.answer(
        f"{mention}❌ <b>Не вгадали!</b> ❌\n\n"
        f"✅ Перевірено: <b>{len(new_cells)}</b> клітинок\n"
        f"Номери: <b>{opened_str}</b>{skipped}",
        parse_mode="HTML"
    )

    if len(state.get("opened", [])) < BREAK_SAFE_CELLS <= len(opened):
        updated_state = {
            "opened": list(opened),
            "win_cell": win_cell,
            "users": users,
            "break_vote": state.get("break_vote"),
        }
        await message.answer(
            safe_status_text(updated_state),
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=break_safe_button(updated_state),
        )





# git config --global user.name "Yuriy-vasylevsky"
# git config --global user.email "yuriy.vasylevsky@gmail.com"
