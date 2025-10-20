import logging
from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from db import (
    get_free_code,
    create_pending_reward,
    get_pending_by_id,
    set_pending_status,
    mark_code_used_by_id,
    mark_code_unused,
    has_claimed_gift,
)
from menu import main_menu
from config import ADMIN_ID

router = Router()


@router.callback_query(F.data.startswith("choose_reward:"))
async def on_choose_reward(cb: CallbackQuery):
    parts = cb.data.split(":")
    if len(parts) < 3:
        await cb.answer("Невірні дані.", show_alert=True)
        return

    _, casino_type, user_id_s = parts
    try:
        user_id = int(user_id_s)
    except ValueError:
        user_id = cb.from_user.id

    user_name = cb.from_user.full_name
    username = cb.from_user.username

    try:
        await cb.message.edit_text(
            f"🎰 Ви обрали платформу <b>{casino_type.capitalize()}</b>!\nОчікуйте підтвердження адміністратора.",
            parse_mode="HTML",
        )
    except Exception:
        pass

    free = await get_free_code(casino_type)
    gift_claimed = await has_claimed_gift(user_id)
    if not free:
        await cb.bot.send_message(
            user_id,
            "⚠️ Вибачте — кодів цього типу наразі немає.\nЗверніться до касира.",
            reply_markup=main_menu(
                is_admin=(user_id == ADMIN_ID), user_has_gift=gift_claimed
            ),
        )
        await cb.answer("Немає вільних кодів цього типу.", show_alert=True)
        return

    code_id, code_text = free
    pending_id = await create_pending_reward(user_id, code_id, casino_type)

    kb_admin = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Підтвердити",
                    callback_data=f"reward_confirm:{pending_id}:confirm",
                ),
                InlineKeyboardButton(
                    text="❌ Відхилити",
                    callback_data=f"reward_confirm:{pending_id}:reject",
                ),
            ]
        ]
    )
    await cb.bot.send_message(
        ADMIN_ID,
        f"🔔 <b>Гравець просить код для {casino_type}</b>\n\n"
        f"👤 Ім’я: <b>{user_name}</b>\n"
        f"🆔 ID: <code>{user_id}</code>\n"
        f"🔑 Код (зарезервовано): <code>{code_text}</code>",
        parse_mode="HTML",
        reply_markup=kb_admin,
    )

    gift_claimed = await has_claimed_gift(user_id)
    await cb.bot.send_message(
        user_id,
        "✅ Ваш виграш зафіксовано.\nЗачекайте підтвердження адміністратора.",
        reply_markup=main_menu(
            is_admin=(user_id == ADMIN_ID), user_has_gift=gift_claimed
        ),
    )
    await cb.answer()


@router.callback_query(F.data.startswith("reward_confirm:"))
async def handle_reward_confirm(cb: CallbackQuery):
    if cb.from_user.id != ADMIN_ID:
        await cb.answer("⛔ Тільки адміністратор.", show_alert=True)
        return

    parts = cb.data.split(":")
    if len(parts) != 3:
        await cb.answer("Невірні дані.", show_alert=True)
        return

    _, pending_id_s, action = parts
    try:
        pending_id = int(pending_id_s)
    except ValueError:
        await cb.answer("Невірний ID.", show_alert=True)
        return

    pending = await get_pending_by_id(pending_id)
    if not pending:
        await cb.answer("Невідомий запит.", show_alert=True)
        return

    user_id = pending["user_id"]
    code_text = (pending.get("code") or "").replace("-", "")
    casino_type = pending.get("casino_type")

    if action == "confirm":
        if not code_text:
            free_code = await get_free_code(casino_type)
            if not free_code:
                await cb.answer(
                    "❌ Немає вільних кодів для цього казино.", show_alert=True
                )
                return
            code_text = free_code["code"].replace("-", "")
            await mark_code_used_by_id(free_code["id"], user_id)
        else:
            code_text = code_text.replace("-", "")

        await set_pending_status(pending_id, "confirmed")

        if casino_type == "champion":
            url = f"https://spinplanet.net/?login_code={code_text}"
        else:
            url = f"https://code.greenhost.pw/?c={code_text}"

        await cb.message.edit_text(
            f"✅ Виграш підтверджено.\nКод: {casino_type} - {code_text}"
        )

        try:
            await cb.bot.send_message(
                user_id,
                f"🎉 Ваш виграш підтверджено!\n\n🎁 Бажаю удачі в грі\n\n 🔗 {url}",
            )
        except Exception as e:
            logging.warning(f"Не вдалося надіслати код користувачу {user_id}: {e}")

    else:
        if pending.get("code_id"):
            await mark_code_unused(pending["code_id"])

        await set_pending_status(pending_id, "rejected")
        await cb.message.edit_text(
            "❌ Виграш відхилено. Код повернуто у пул (якщо був)."
        )

        try:
            await cb.bot.send_message(
                user_id,
                "❌ Ваш запит на отримання коду відхилено. Адмін зв'яжеться з вами.",
            )
        except Exception:
            pass

    await cb.answer()
