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

    loading = await message.answer("⏳ Завантажую статистику Champion…")
    report = await get_champion_yesterday_stats()
    start = report["start"].strftime("%d.%m.%Y %H:%M")
    end = report["end"].strftime("%d.%m.%Y %H:%M")

    if not report["success"]:
        await loading.edit_text(
            "❌ Не вдалося отримати статистику Champion.\n"
            f"<code>{report.get('message', 'Невідома помилка')}</code>",
            parse_mode="HTML",
        )
        return

    totals = report["totals"]
    lines = [
        "🏆 <b>Champion — звіт за вчора</b>",
        f"🕒 {start} — {end} (Київ)",
        "",
        f"👥 Субагентів у звіті: <b>{len(report['items'])}</b>",
        f"💳 Баланс: <b>{_money(totals['credit'])} грн</b>",
        f"📥 Депозити: <b>{_money(totals['deposit'])} грн</b>",
        f"📤 Виплати: <b>{_money(totals['close'])} грн</b>",
        f"📈 Результат: <b>{_money(totals['result'])} грн</b>",
        f"🧾 Сума на рахунках: <b>{_money(totals['invoice'])} грн</b>",
    ]
    if report["failed"]:
        lines.extend(["", "⚠️ Немає даних: " + ", ".join(report["failed"])])

    await loading.edit_text("\n".join(lines), parse_mode="HTML")
