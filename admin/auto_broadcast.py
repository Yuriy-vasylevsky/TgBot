import asyncio
from datetime import datetime

from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.utils.keyboard import InlineKeyboardBuilder

from db.auto_broadcast import KYIV, next_daily, list_broadcasts, save_broadcast, change_broadcast
from handlers.config import ADMIN_ID
from services.auto_broadcast import play_button

router = Router(name="auto_broadcast_admin")
router.message.filter(F.from_user.id == ADMIN_ID)
router.callback_query.filter(F.from_user.id == ADMIN_ID)
_save_lock = asyncio.Lock()
WEEKDAYS = ("Понеділок", "Вівторок", "Середа", "Четвер", "П’ятниця", "Субота", "Неділя")


class AutoBroadcastFSM(StatesGroup):
    title = State()
    photo = State()
    caption = State()
    clock = State()
    days = State()
    confirm = State()


def days_text(mask):
    return "Всі дні" if mask == 127 else ", ".join(day for i, day in enumerate(WEEKDAYS) if mask & (1 << i))


def days_keyboard(mask):
    kb = InlineKeyboardBuilder()
    for i, day in enumerate(WEEKDAYS):
        kb.button(text=f"{'✅' if mask & (1 << i) else '⬜'} {day}", callback_data=f"ab:day:{i}")
    kb.button(text="✅ Всі дні", callback_data="ab:day:all")
    kb.button(text="💾 Зберегти дні", callback_data="ab:days_done")
    kb.button(text="❌ Скасувати", callback_data="ab:list:0")
    kb.adjust(1)
    return kb.as_markup()


async def ask_days(message, state, mask=127):
    await state.update_data(days_mask=mask)
    await state.set_state(AutoBroadcastFSM.days)
    await message.answer("📅 Оберіть дні розсилки. Натискання на день вмикає або вимикає його.", reply_markup=days_keyboard(mask))


def cancel_keyboard(skip=False):
    kb = InlineKeyboardBuilder()
    if skip:
        kb.button(text="⏭ Без підпису", callback_data="ab:skip")
    kb.button(text="❌ Скасувати", callback_data="ab:list:0")
    kb.adjust(1)
    return kb.as_markup()


async def show_list(message, page=0):
    rows = await list_broadcasts()
    page = max(0, min(page, (len(rows) - 1) // 8))
    kb = InlineKeyboardBuilder()
    for row in rows[page * 8:page * 8 + 8]:
        bid = row['id']
        title = row.get('title') or f"Авторозсилка #{bid}"
        kb.button(text=f"{title} · {row['clock']} · {'✅' if row['enabled'] else '⏸'}", callback_data=f"ab:view:{bid}")
    if page:
        kb.button(text="← Попередні", callback_data=f"ab:list:{page - 1}")
    if (page + 1) * 8 < len(rows):
        kb.button(text="Наступні →", callback_data=f"ab:list:{page + 1}")
    kb.button(text="➕ Додати авторозсилку", callback_data="ab:new")
    kb.adjust(1)
    await message.answer(
        "🔁 Авторозсилки\n\nУ вибрані дні за київським часом. Оберіть розсилку для перегляду та налаштування."
        if rows else "🔁 Авторозсилок ще немає. Додайте фото, підпис за бажанням, час і дні надсилання.",
        reply_markup=kb.as_markup(),
    )


@router.callback_query(F.data.startswith("ab:list:"))
async def open_list(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await cb.answer()
    await show_list(cb.message, int(cb.data.rsplit(":", 1)[1]))


@router.callback_query(F.data == "ab:new")
async def new_broadcast(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await state.set_state(AutoBroadcastFSM.title)
    await cb.answer()
    await cb.message.answer("🏷 Введіть назву розсилки (до 80 символів). Вона показуватиметься у списку для адміністратора.", reply_markup=cancel_keyboard())


@router.message(AutoBroadcastFSM.title)
async def receive_title(message: types.Message, state: FSMContext):
    title = ' '.join((message.text or '').split())
    if not 1 <= len(title) <= 80:
        await message.answer("Введіть назву від 1 до 80 символів.", reply_markup=cancel_keyboard())
        return
    data = await state.get_data()
    if data.get('edit_title_id'):
        await change_broadcast(data['edit_title_id'], 'title', title=title)
        await state.clear()
        await message.answer("✅ Назву змінено.")
        await show_list(message)
        return
    await state.update_data(title=title)
    await state.set_state(AutoBroadcastFSM.photo)
    await message.answer("🖼 Надішліть картинку як фото.", reply_markup=cancel_keyboard())


@router.callback_query(F.data.startswith("ab:title:"))
async def edit_title(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await state.update_data(edit_title_id=int(cb.data.rsplit(':', 1)[1]))
    await state.set_state(AutoBroadcastFSM.title)
    await cb.answer()
    await cb.message.answer("🏷 Введіть нову назву розсилки (до 80 символів).", reply_markup=cancel_keyboard())


@router.message(AutoBroadcastFSM.photo)
async def receive_photo(message: types.Message, state: FSMContext):
    if not message.photo:
        await message.answer("Надішліть саме фото, не файл.", reply_markup=cancel_keyboard())
        return
    await state.update_data(photo=message.photo[-1].file_id)
    await state.set_state(AutoBroadcastFSM.caption)
    await message.answer("✍️ Введіть підпис до картинки або натисніть «Без підпису».", reply_markup=cancel_keyboard(skip=True))


async def ask_clock(message, state):
    await state.set_state(AutoBroadcastFSM.clock)
    await message.answer("🕒 Введіть час розсилки за Києвом у форматі ГГ:ХХ, наприклад 18:30.", reply_markup=cancel_keyboard())


@router.callback_query(AutoBroadcastFSM.caption, F.data == "ab:skip")
async def skip_caption(cb: types.CallbackQuery, state: FSMContext):
    await state.update_data(caption=None)
    await cb.answer()
    await ask_clock(cb.message, state)


@router.message(AutoBroadcastFSM.caption)
async def receive_caption(message: types.Message, state: FSMContext):
    if not message.text or len(message.text.encode('utf-16-le')) // 2 > 1024:
        await message.answer("Потрібен текст підпису до 1024 символів або натисніть «Без підпису».", reply_markup=cancel_keyboard(skip=True))
        return
    await state.update_data(caption=message.text)
    await ask_clock(message, state)


@router.message(AutoBroadcastFSM.clock)
async def receive_clock(message: types.Message, state: FSMContext):
    clock = (message.text or "").strip()
    try:
        when = next_daily(clock)
    except (ValueError, TypeError):
        await message.answer("Некоректний час. Введіть, наприклад, 09:00 або 18:30.")
        return
    data = await state.get_data()
    if data.get('edit_id'):
        await change_broadcast(data['edit_id'], 'time', clock)
        await state.clear()
        await message.answer("✅ Час змінено.")
        await show_list(message)
        return
    await state.update_data(clock=clock)
    await ask_days(message, state)


@router.callback_query(AutoBroadcastFSM.days, F.data.startswith("ab:day:"))
async def choose_day(cb: types.CallbackQuery, state: FSMContext):
    async with _save_lock:
        data = await state.get_data()
        mask = data.get('days_mask', 127)
        value = cb.data.rsplit(':', 1)[1]
        if value == 'all':
            new_mask = 127
        elif value in {str(i) for i in range(7)}:
            new_mask = mask ^ (1 << int(value))
        else:
            await cb.answer()
            return
        await state.update_data(days_mask=new_mask)
        await cb.answer()
        if new_mask != mask:
            await cb.message.edit_reply_markup(reply_markup=days_keyboard(new_mask))


@router.callback_query(AutoBroadcastFSM.days, F.data == "ab:days_done")
async def save_days(cb: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    mask = data.get('days_mask', 0)
    if not mask:
        await cb.answer("Оберіть хоча б один день.", show_alert=True)
        return
    await cb.answer()
    await cb.message.edit_reply_markup(reply_markup=None)
    if data.get('edit_days_id'):
        await change_broadcast(data['edit_days_id'], 'days', days_mask=mask)
        await state.clear()
        await cb.message.answer("✅ Дні розсилки збережено.")
        await show_list(cb.message)
        return
    await show_preview(cb.message, state, data)


async def show_preview(message, state, data):
    clock = data['clock']
    mask = data['days_mask']
    when = next_daily(clock, days_mask=mask)
    await state.set_state(AutoBroadcastFSM.confirm)
    await message.answer_photo(data['photo'], caption=data.get('caption'), parse_mode=None, reply_markup=play_button())
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Зберегти й увімкнути", callback_data="ab:save")
    kb.button(text="❌ Скасувати", callback_data="ab:list:0")
    kb.adjust(1)
    first = datetime.fromtimestamp(when, KYIV).strftime('%d.%m.%Y %H:%M')
    await message.answer(f"Попередній перегляд 👆\nО {clock} за Києвом.\nДні: {days_text(mask)}.\nПерша розсилка: {first}.", reply_markup=kb.as_markup())


@router.callback_query(AutoBroadcastFSM.confirm, F.data == "ab:save")
async def confirm_broadcast(cb: types.CallbackQuery, state: FSMContext):
    async with _save_lock:
        data = await state.get_data()
        if await state.get_state() != AutoBroadcastFSM.confirm.state or not data.get('photo'):
            await cb.answer("Цю розсилку вже збережено або скасовано.")
            return
        bid = await save_broadcast(data['photo'], data.get('caption'), data['clock'], data['days_mask'], title=data.get('title', ''))
        await state.clear()
    await cb.answer("Збережено")
    await cb.message.edit_reply_markup(reply_markup=None)
    await cb.message.answer(f"✅ Авторозсилку #{bid} увімкнено.")
    await show_list(cb.message)


@router.callback_query(F.data.startswith("ab:view:"))
async def view_broadcast(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    bid = int(cb.data.rsplit(":", 1)[1])
    rows = await list_broadcasts()
    row = next((row for row in rows if row['id'] == bid), None)
    if not row:
        await cb.answer("Розсилку вже видалено.", show_alert=True)
        return
    await cb.answer()
    await cb.message.answer_photo(row['photo'], caption=row['caption'], parse_mode=None, reply_markup=play_button())
    kb = InlineKeyboardBuilder()
    kb.button(text="⏸ Призупинити" if row['enabled'] else "▶️ Увімкнути", callback_data=f"ab:toggle:{bid}")
    kb.button(text="🏷 Змінити назву", callback_data=f"ab:title:{bid}")
    kb.button(text="🕒 Змінити час", callback_data=f"ab:time:{bid}")
    kb.button(text="📅 Дні тижня", callback_data=f"ab:days:{bid}")
    kb.button(text="🗑 Видалити", callback_data=f"ab:delete:{bid}")
    kb.button(text="← До списку", callback_data="ab:list:0")
    kb.adjust(1)
    await cb.message.answer(f"Авторозсилка #{bid}\nНазва: {row.get('title') or 'Без назви'}\nО {row['clock']} за Києвом.\nДні: {days_text(row['days_mask'])}.\nСтан: {'увімкнено' if row['enabled'] else 'призупинено'}.", parse_mode=None, reply_markup=kb.as_markup())


@router.callback_query(F.data.startswith("ab:days:"))
async def edit_days(cb: types.CallbackQuery, state: FSMContext):
    bid = int(cb.data.rsplit(':', 1)[1])
    row = next((r for r in await list_broadcasts() if r['id'] == bid), None)
    if not row:
        await cb.answer("Розсилку вже видалено.", show_alert=True)
        return
    await state.clear()
    await state.update_data(edit_days_id=bid)
    await cb.answer()
    await ask_days(cb.message, state, row['days_mask'])


@router.callback_query(F.data.startswith("ab:time:"))
async def edit_clock(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await state.update_data(edit_id=int(cb.data.rsplit(":", 1)[1]))
    await cb.answer()
    await ask_clock(cb.message, state)


@router.callback_query(F.data.startswith("ab:toggle:"))
async def toggle_broadcast(cb: types.CallbackQuery, state: FSMContext):
    await change_broadcast(int(cb.data.rsplit(":", 1)[1]), 'toggle')
    await state.clear()
    await cb.answer("Стан змінено")
    await cb.message.edit_reply_markup(reply_markup=None)
    await show_list(cb.message)


@router.callback_query(F.data.startswith("ab:delete:"))
async def ask_delete(cb: types.CallbackQuery):
    bid = int(cb.data.rsplit(":", 1)[1])
    kb = InlineKeyboardBuilder()
    kb.button(text="🗑 Так, видалити", callback_data=f"ab:remove:{bid}")
    kb.button(text="Скасувати", callback_data="ab:list:0")
    await cb.answer()
    await cb.message.answer(f"Видалити авторозсилку #{bid}?", reply_markup=kb.as_markup())


@router.callback_query(F.data.startswith("ab:remove:"))
async def delete_broadcast(cb: types.CallbackQuery, state: FSMContext):
    await change_broadcast(int(cb.data.rsplit(":", 1)[1]), 'delete')
    await state.clear()
    await cb.answer("Видалено")
    await cb.message.edit_reply_markup(reply_markup=None)
    await show_list(cb.message)
