from aiogram import F, Router, types

from handlers.casino_api import get_champion_yesterday_stats
from handlers.config import ADMIN_ID


router = Router(name="admin_champion_stats")


def _money(value: float) -> str:
    return f"{value:,.2f}".replace(",", " ")


@router.message(F.text == "🏆 Champion: вчора")
async def show_champion_yesterday_stats(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return

    report = await get_champion_yesterday_stats()
    start = report["start"].strftime("%d.%m.%Y %H:%M")
    end = report["end"].strftime("%d.%m.%Y %H:%M")

    if not report["success"]:
        await message.answer(
            "❌ Не вдалося отримати статистику Champion.\n"
            f"<code>{report.get('message', 'Невідома помилка')}</code>",
            parse_mode="HTML",
        )
        return

    lines = [
        "🏆 <b>Champion — звіт за вчора</b>",
        f"👤 Касир: <b>{report['login']}</b>",
        f"🕒 {start} — {end} (Київ)",
        "",
        f"📥 Депозит: <b>{_money(report['deposit'])} грн</b>",
        f"📤 Виплата: <b>{_money(report['close'])} грн</b>",
        f"📈 Результат: <b>{_money(report['result'])} грн</b>",
    ]

    await message.answer("\n".join(lines), parse_mode="HTML")
