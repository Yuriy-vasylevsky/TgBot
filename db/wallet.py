
import aiosqlite
import time
import logging

from .core import DB_PATH
from datetime import datetime, timezone, timedelta

KYIV_TZ = timezone(timedelta(hours=3))

async def add_to_balance(user_id: int, amount_grn: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO users (user_id, balance)
            VALUES (?, ?)
            ON CONFLICT(user_id)
            DO UPDATE SET balance = balance + ?
        """, (user_id, amount_grn, amount_grn))

        await db.commit()


# Обнова витрат ща сьогодні і вчора


from datetime import datetime, date
import aiosqlite

KYIV_TZ = timezone(timedelta(hours=3))


from datetime import datetime, timezone, timedelta
import logging
import aiosqlite
 
KYIV_TZ = timezone(timedelta(hours=3))
 
CASHBACK_PERCENT = 0.10
CASHBACK_GOAL = 1000
 
 
# ==================== ОНОВЛЕНА ensure_daily_reset ====================
# async def ensure_daily_reset(user_id: int):
#     """Гарантує правильний перехід на новий день (тепер скидає й кешбек-базу)"""
#     today_str = datetime.now(KYIV_TZ).date().isoformat()
 
#     async with aiosqlite.connect(DB_PATH) as db:
#         cursor = await db.execute(
#             "SELECT daily_net, yesterday_net, last_net_date FROM users WHERE user_id = ?",
#             (user_id,)
#         )
#         row = await cursor.fetchone()
 
#         if not row:
#             await db.execute(
#                 "INSERT INTO users (user_id, daily_net, yesterday_net, last_net_date, cashback_claimed_base) "
#                 "VALUES (?, 0, 0, ?, 0)",
#                 (user_id, today_str)
#             )
#             await db.commit()
#             return
 
#         daily_net, yesterday_net, last_net_date = row
 
#         is_new_day = (
#             last_net_date is None or
#             last_net_date != today_str
#         )
 
#         if is_new_day:
#             await db.execute("""
#                 UPDATE users 
#                 SET 
#                     yesterday_net = COALESCE(?, 0),
#                     daily_net = 0,
#                     cashback_claimed_base = 0,
#                     last_net_date = ?
#                 WHERE user_id = ?
#             """, (daily_net, today_str, user_id))
#             await db.commit()
#             logging.info(f"✅ Reset daily_net + cashback для user {user_id} (новий день)")
 
 
# async def ensure_daily_reset(user_id: int):
#     today_str = datetime.now(KYIV_TZ).date().isoformat()
#     yesterday_str = (datetime.now(KYIV_TZ).date() - timedelta(days=1)).isoformat()

#     async with aiosqlite.connect(DB_PATH) as db:
#         cursor = await db.execute(
#             "SELECT daily_net, yesterday_net, last_net_date FROM users WHERE user_id = ?",
#             (user_id,)
#         )
#         row = await cursor.fetchone()

#         if not row:
#             await db.execute(
#                 "INSERT INTO users (user_id, daily_net, yesterday_net, last_net_date, cashback_claimed_base) "
#                 "VALUES (?, 0, 0, ?, 0)",
#                 (user_id, today_str)
#             )
#             await db.commit()
#             return

#         daily_net, yesterday_net, last_net_date = row

#         if last_net_date == today_str:
#             return  # вже актуально

#         if last_net_date == yesterday_str:
#             # Вчора була активність — коректно переносимо
#             new_yesterday = daily_net or 0
#         else:
#             # Пропущено більше одного дня — вчора не було активності
#             new_yesterday = 0

#         await db.execute("""
#             UPDATE users 
#             SET 
#                 yesterday_net = ?,
#                 daily_net = 0,
#                 cashback_claimed_base = 0,
#                 last_net_date = ?
#             WHERE user_id = ?
#         """, (new_yesterday, today_str, user_id))
#         await db.commit()
#         logging.info(f"✅ Reset daily_net + cashback для user {user_id} | yesterday_net={new_yesterday}")


# async def ensure_daily_reset(user_id: int):
#     today_str = datetime.now(KYIV_TZ).date().isoformat()
#     yesterday_str = (datetime.now(KYIV_TZ).date() - timedelta(days=1)).isoformat()

#     async with aiosqlite.connect(DB_PATH) as db:
#         cursor = await db.execute(
#             "SELECT daily_net, yesterday_net, last_net_date FROM users WHERE user_id = ?",
#             (user_id,)
#         )
#         row = await cursor.fetchone()

#         if not row:
#             await db.execute(
#                 "INSERT INTO users (user_id, daily_net, yesterday_net, last_net_date, "
#                 "cashback_claimed_base, promo_claimed_base) "
#                 "VALUES (?, 0, 0, ?, 0, 0)",
#                 (user_id, today_str)
#             )
#             await db.commit()
#             return

#         daily_net, yesterday_net, last_net_date = row

#         if last_net_date == today_str:
#             return  # вже актуально

#         if last_net_date == yesterday_str:
#             # Вчора була активність — коректно переносимо
#             new_yesterday = daily_net or 0
#         else:
#             # Пропущено більше одного дня — вчора не було активності
#             new_yesterday = 0

#         await db.execute("""
#             UPDATE users 
#             SET 
#                 yesterday_net = ?,
#                 daily_net = 0,
#                 cashback_claimed_base = 0,
#                 promo_claimed_base = 0,
#                 last_net_date = ?
#             WHERE user_id = ?
#         """, (new_yesterday, today_str, user_id))
#         await db.commit()
#         logging.info(f"✅ Reset daily_net + cashback + promo для user {user_id} | yesterday_net={new_yesterday}")








async def ensure_daily_reset(user_id: int):
    today_str = datetime.now(KYIV_TZ).date().isoformat()
    yesterday_str = (datetime.now(KYIV_TZ).date() - timedelta(days=1)).isoformat()

    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT daily_net, yesterday_net, last_net_date FROM users WHERE user_id = ?",
            (user_id,)
        )
        row = await cursor.fetchone()

        if not row:
            await db.execute(
                "INSERT INTO users (user_id, daily_net, yesterday_net, last_net_date, "
                "cashback_claimed_base, promo_claimed_base) "
                "VALUES (?, 0, 0, ?, 0, 0)",
                (user_id, today_str)
            )
            await db.commit()
            return

        daily_net, yesterday_net, last_net_date = row

        if last_net_date == today_str:
            return  # вже актуально

        if last_net_date == yesterday_str:
            # Вчора була активність — коректно переносимо
            new_yesterday = daily_net or 0
        else:
            # Пропущено більше одного дня — вчора не було активності
            new_yesterday = 0

        # Глобальний накопичувальний рахунок: додаємо daily_net дня, що завершився
        # (і плюсові, і мінусові значення — щодня, без перевірки знаку)
        closed_day_net = daily_net or 0

        await db.execute("""
            UPDATE users 
            SET 
                yesterday_net = ?,
                daily_net = 0,
                cashback_claimed_base = 0,
                promo_claimed_base = 0,
                last_net_date = ?,
                total_losses_all_time = COALESCE(total_losses_all_time, 0) + ?
            WHERE user_id = ?
        """, (new_yesterday, today_str, closed_day_net, user_id))
        await db.commit()
        logging.info(
            f"✅ Reset daily_net + cashback + promo для user {user_id} | "
            f"yesterday_net={new_yesterday} | +{closed_day_net} до total_losses_all_time"
        )








# ==================== КЕШБЕК: ДОПОМІЖНІ ФУНКЦІЇ ====================
 
async def get_cashback_claimed_base(user_id: int) -> int:
    """Скільки net вже 'витрачено' на попередні кешбеки сьогодні."""
    await ensure_daily_reset(user_id)
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT COALESCE(cashback_claimed_base, 0) FROM users WHERE user_id = ?",
            (user_id,)
        )
        row = await cursor.fetchone()
        return row[0] if row else 0
 
 
async def get_cashback_status(user_id: int) -> dict:
    """
    Повертає статус кешбеку.
    claim_amount показується завжди (потенційна сума), can_claim — тільки для видачі.
    """
    today_net = await get_daily_net(user_id)
    claimed_base = await get_cashback_claimed_base(user_id)
    balance = await get_balance(user_id)

    available_net = max(today_net - claimed_base, 0)
    
    # Потенційна сума кешбеку (показуємо завжди)
    potential_claim_amount = round(available_net * CASHBACK_PERCENT)
    
    # Можна отримати тільки якщо є достатньо net І баланс <= 50
    # can_claim = (available_net >= CASHBACK_GOAL) and (balance <= 50)
    can_claim = (available_net >= CASHBACK_GOAL) and (balance <= 0)
    return {
        "today_net": today_net,
        "claimed_base": claimed_base,
        "available_net": available_net,
        "balance": balance,
        "can_claim": can_claim,
        "claim_amount": potential_claim_amount,   # <-- Важливо: завжди потенційна сума
        "balance_too_high": balance > 50,
        "progress_in_tier": available_net,
    }
 
async def claim_cashback(user_id: int) -> dict:
    """Атомарно видає кешбек з перевіркою балансу ≤ 50 грн"""
    await ensure_daily_reset(user_id)

    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT daily_net, cashback_claimed_base, balance FROM users WHERE user_id = ?",
            (user_id,)
        )
        row = await cursor.fetchone()
        if not row:
            return {"success": False, "reason": "no_user"}

        daily_net, claimed_base, balance = row
        daily_net = daily_net or 0
        claimed_base = claimed_base or 0
        balance = balance or 0

        available_net = daily_net - claimed_base

        # === НОВІ ПЕРЕВІРКИ ===
        if available_net < CASHBACK_GOAL:
            return {
                "success": False,
                "reason": "not_enough",
                "available_net": max(available_net, 0),
                "needed": CASHBACK_GOAL - max(available_net, 0),
            }

        if balance > 0:
            return {
                "success": False,
                "reason": "balance_too_high",
                "current_balance": balance,
                "max_allowed": 0,
            }

        cashback_amount = round(available_net * CASHBACK_PERCENT)
        new_claimed_base = claimed_base + available_net
        new_balance = balance + cashback_amount

        await db.execute(
            """
            UPDATE users
            SET balance = ?,
                cashback_claimed_base = ?
            WHERE user_id = ?
            """,
            (new_balance, new_claimed_base, user_id)
        )
        await db.commit()

        return {
            "success": True,
            "cashback_amount": cashback_amount,
            "claimed_from_net": available_net,
            "new_balance": new_balance,
        }













async def update_daily_net(user_id: int, amount: int):
    """Оновлює daily_net з гарантованим reset'ом"""
    await ensure_daily_reset(user_id)   # ← Додаємо

    today_str = datetime.now(KYIV_TZ).date().isoformat()

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE users 
            SET 
                daily_net = daily_net + ?,
                last_net_date = ?
            WHERE user_id = ?
        """, (amount, today_str, user_id))
        await db.commit()


async def get_daily_net(user_id: int) -> int:
    await ensure_daily_reset(user_id)   # ← КРИТИЧНО

    today = datetime.now(KYIV_TZ).date().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT COALESCE(daily_net, 0) FROM users WHERE user_id = ?",
            (user_id,)
        )
        row = await cursor.fetchone()
        return row[0] if row else 0


async def get_yesterday_net(user_id: int) -> int:
    await ensure_daily_reset(user_id)   # ← КРИТИЧНО

    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT COALESCE(yesterday_net, 0) FROM users WHERE user_id = ?",
            (user_id,)
        )
        row = await cursor.fetchone()
        return row[0] if row else 0



async def get_balance(user_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT balance FROM users WHERE user_id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        return row[0] if row else 0


async def add_pending_payment(
    user_id: int, amount_kop: int, comment: str, mono_account: str = "0"
):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR REPLACE INTO pending_payments 
            (user_id, amount_kop, comment, created_at, mono_account)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, amount_kop, comment, time.time(), mono_account))
        await db.commit()


async def get_pending_payments() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT user_id, amount_kop, comment, mono_account 
            FROM pending_payments
        """)
        rows = await cursor.fetchall()
        return [
            {"user_id": r[0], "amount_kop": r[1], "comment": r[2], "mono_account": r[3]}
            for r in rows
        ]


async def remove_pending_payment(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM pending_payments WHERE user_id = ?", (user_id,))
        await db.commit()


# ═══════════════════════════════════════════════════════════════════════════════
# mark_tx_used — АТОМАРНА ВЕРСІЯ З EXCLUSIVE LOCK
# ═══════════════════════════════════════════════════════════════════════════════
async def mark_tx_used(
    tx_id: str, user_id: int, amount_kop: int, payment_id: str = None
) -> bool:
    """
    Атомарно зарезервує транзакцію Monobank під цього користувача.
    
    Повертає:
        True  — TX успішно зарезервована під цього user_id (новий INSERT)
        False — TX вже занята (неважливо кому)
    
    Використовує EXCLUSIVE транзакцію щоб запобігти race condition,
    коли двоє з однаковою сумою спробують зараховувати одну TX паралельно.
    
    ✅ Гарантія: Лише ОДИН користувач отримає True для кожної TX.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        # 🔒 EXCLUSIVE LOCK — блокує таблицю для всіх інших
        # Паралельні запити чекають, поки попередній завершиться
        try:
            await db.execute("BEGIN EXCLUSIVE")
        except Exception as e:
            logging.error(f"❌ Помилка BEGIN EXCLUSIVE: {e}")
            return False
        
        try:
            # ✅ КРОК 1: Перевіримо, чи ця TX вже існує (всередину lock!)
            cur = await db.execute(
                "SELECT user_id FROM used_monobank_txs WHERE tx_id = ?",
                (tx_id,)
            )
            existing_row = await cur.fetchone()
            
            if existing_row:
                # ❌ TX вже зарезервована для когось (можливо для цього user_id)
                existing_user_id = existing_row[0]
                
                if existing_user_id == user_id:
                    # Повторна спроба от одного користувача
                    logging.warning(
                        f"⚠️ TX уже зарезервована під вас раніше: "
                        f"tx_id='{tx_id}' user_id={user_id}"
                    )
                else:
                    # КРИТИЧНО: Два користувачі з однаковою сумою!
                    logging.warning(
                        f"🚫 TX ПЕРЕХОПЛЕНА ІНШИМ КОРИСТУВАЧЕМ! "
                        f"tx_id='{tx_id}' | вже під user_id={existing_user_id}, "
                        f"але спробував user_id={user_id}"
                    )
                
                # Откатываем транзакцию и отпускаем lock
                await db.execute("ROLLBACK")
                return False
            
            # ✅ КРОК 2: TX вільна — вставляємо під цього користувача
            # (lock ще утримується, тому ніхто інший не може ввійти)
            await db.execute(
                """
                INSERT INTO used_monobank_txs
                (tx_id, user_id, amount_kop, payment_id)
                VALUES (?, ?, ?, ?)
                """,
                (tx_id, user_id, amount_kop, payment_id)
            )
            
            # ✅ КРОК 3: Коммітим і відпускаємо lock
            await db.execute("COMMIT")
            
            logging.info(
                f"🔐 TX атомарно зарезервована: tx_id='{tx_id}' для user_id={user_id} "
                f"(EXCLUSIVE LOCK гарантує, що ніхто інший не вставить цю TX)"
            )
            return True
            
        except Exception as e:
            # На всяк випадок — відкатити трансакцію при помилці
            try:
                await db.execute("ROLLBACK")
            except:
                pass
            
            logging.error(f"❌ Помилка в mark_tx_used: {e}", exc_info=True)
            return False


async def is_tx_used(tx_id: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        result = await db.execute(
            "SELECT 1 FROM used_monobank_txs WHERE tx_id = ?", (tx_id,)
        )
        row = await result.fetchone()
        return row is not None


# ───────────────────────────────────────────────────────────────────────────────
# Історія поповнень через бот
# ───────────────────────────────────────────────────────────────────────────────

async def add_payment_log(
    user_id: int,
    username: str | None,
    amount: int,
    comment: str = ""
):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO payment_logs
            (user_id, username, amount, comment)
            VALUES (?, ?, ?, ?)
            """,
            (
                user_id,
                username,
                amount,
                comment
            )
        )
        await db.commit()

async def get_payment_logs(page=1, per_page=20):
    offset = (page - 1) * per_page

    async with aiosqlite.connect(DB_PATH) as db:

        cur = await db.execute(
            """
            SELECT
                user_id,
                username,
                amount,
                comment,
                created_at
            FROM payment_logs
            ORDER BY id DESC
            LIMIT ? OFFSET ?
            """,
            (per_page, offset)
        )

        rows = await cur.fetchall()

        cur = await db.execute(
            "SELECT COUNT(*) FROM payment_logs"
        )

        total = (await cur.fetchone())[0]

    total_pages = max(1, (total + per_page - 1) // per_page)

    return rows, total_pages


async def cleanup_old_payment_logs():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            DELETE FROM payment_logs
            WHERE created_at < DATETIME('now', '+3 hours', '-2 days')
        """)
        await db.commit()

async def get_payment_logs_by_date(date_offset=0, page=1, per_page=10):
    offset = (page - 1) * per_page

    from datetime import datetime, timedelta, timezone

    KYIV_OFFSET = timezone(timedelta(hours=3))
    kyiv_now = datetime.now(KYIV_OFFSET)
    target_date = (kyiv_now - timedelta(days=date_offset)).strftime("%Y-%m-%d")

    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """
            SELECT user_id, username, amount, comment, created_at
            FROM payment_logs
            WHERE DATE(created_at) = ?
            ORDER BY id ASC
            LIMIT ? OFFSET ?
            """,
            (target_date, per_page, offset)
        )
        rows = await cur.fetchall()

        cur = await db.execute(
            """
            SELECT COUNT(*), COALESCE(SUM(amount), 0)
            FROM payment_logs
            WHERE DATE(created_at) = ?
            """,
            (target_date,)
        )
        total, day_total = await cur.fetchone()

    total_pages = max(1, (total + per_page - 1) // per_page)
    return rows, total_pages, day_total




async def log_check_issued(user_id: int, check_type: str, code: str, price: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO issued_checks
            (user_id, check_type, code, price)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, check_type, code, price)
        )
        await db.commit()








async def get_issued_checks_for_user(user_id: int) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """
            SELECT check_type, code, price, issued_at
            FROM issued_checks
            WHERE user_id = ?
              AND issued_at >= DATETIME('now', '-2 days')
            ORDER BY issued_at DESC
            """,
            (user_id,)
        )
        rows = await cur.fetchall()
    return [
        {"check_type": r[0], "code": r[1], "price": r[2], "issued_at": r[3]}
        for r in rows
    ]

async def delete_issued_check(code: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM issued_checks WHERE code = ?",
            (code,)
        )
        await db.commit()

async def get_all_balances() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            SELECT u.user_id, u.balance, u.full_name, u.username
            FROM users u
            WHERE u.balance > 0
            ORDER BY u.balance DESC
            """
        )
        rows = await cursor.fetchall()
    return [
        {"user_id": r[0], "balance": r[1], "full_name": r[2], "username": r[3]}
        for r in rows
    ]



from handlers.casino_api import close_invoice, check_invoice


async def get_active_champion_checks(user_id: int) -> list[dict]:
    """Повертає тільки Champion чеки користувача + актуальний баланс з API"""
    checks = await get_issued_checks_for_user(user_id)
    
    active = []
    for check in checks:
        if "Champion" not in check["check_type"]:
            continue
            
        invoice = check["code"]
        status = await check_invoice(invoice)  # перевіряємо актуальний баланс
        
        if status and status.get("success"):
            remaining = float(status.get("sum", 0))
            if remaining > 0:  # тільки з грошима
                active.append({
                    **check,
                    "remaining": remaining
                })
    
    return active



# баланс виграних грошей користувачів


async def ensure_daily_game_win_reset(user_id: int):
    today_str = datetime.now(KYIV_TZ).date().isoformat()
    yesterday_str = (datetime.now(KYIV_TZ).date() - timedelta(days=1)).isoformat()

    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT daily_game_win, yesterday_game_win, last_game_win_date FROM users WHERE user_id = ?",
            (user_id,)
        )
        row = await cursor.fetchone()

        if not row:
            await db.execute(
                """INSERT INTO users (user_id, daily_game_win, yesterday_game_win, last_game_win_date) 
                   VALUES (?, 0, 0, ?)""",
                (user_id, today_str)
            )
            await db.commit()
            return

        daily_win, yesterday_win, last_date = row

        if last_date == today_str:
            return

        if last_date == yesterday_str:
            new_yesterday = daily_win or 0
        else:
            new_yesterday = 0

        await db.execute("""
            UPDATE users 
            SET 
                yesterday_game_win = ?,
                daily_game_win = 0,
                last_game_win_date = ?
            WHERE user_id = ?
        """, (new_yesterday, today_str, user_id))
        await db.commit()
        logging.info(f"🔄 GameWin Reset | user={user_id} | yesterday_game_win={new_yesterday}")

async def add_daily_game_win(user_id: int, amount: int):
    await ensure_daily_game_win_reset(user_id)   # ← додаємо

    today_str = datetime.now(KYIV_TZ).date().isoformat()

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE users 
            SET 
                daily_game_win = daily_game_win + ?,
                last_game_win_date = ?
            WHERE user_id = ?
        """, (amount, today_str, user_id))
        await db.commit()


async def get_daily_game_win(user_id: int) -> int:
    await ensure_daily_game_win_reset(user_id)   # ← додаємо

    today = datetime.now(KYIV_TZ).date().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT COALESCE(daily_game_win, 0) FROM users WHERE user_id = ?",
            (user_id,)
        )
        row = await cursor.fetchone()
        return row[0] if row else 0


async def get_yesterday_game_win(user_id: int) -> int:
    await ensure_daily_game_win_reset(user_id)

    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT COALESCE(yesterday_game_win, 0) FROM users WHERE user_id = ?",
            (user_id,)
        )
        row = await cursor.fetchone()
        return row[0] if row else 0




async def get_all_daily_game_wins() -> list[dict]:
    """Для адмінки: список усіх юзерів, хто виграв в іграх сьогодні."""
    today = datetime.now(KYIV_TZ).date().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            SELECT user_id, full_name, username, daily_game_win
            FROM users
            WHERE last_game_win_date = ? AND daily_game_win > 0
            ORDER BY daily_game_win DESC
            """,
            (today,)
        )
        rows = await cursor.fetchall()
    return [
        {"user_id": r[0], "full_name": r[1], "username": r[2], "daily_game_win": r[3]}
        for r in rows
    ]



from datetime import datetime, timezone, timedelta
import aiosqlite
from .core import DB_PATH
from .wallet import get_daily_net, get_yesterday_net, get_daily_game_win

KYIV_TZ = timezone(timedelta(hours=3))



def _positive_or_zero(value: int) -> int:
    """Якщо значення за день мінусове — ігноруємо його (повертаємо 0)"""
    return value if value > 0 else 0


async def can_receive_prize(user_id: int, prize_amount: int = 0) -> tuple[bool, str]:
    """
    Перевіряє можливість отримання призу з урахуванням:
    - Депозитів/програшу (сьогодні + вчора, мінусові дні ігноруються)
    - Виграшів у іграх (сьогодні + вчора, мінусові дні ігноруються)
    """
    today_net = await get_daily_net(user_id)
    yesterday_net = await get_yesterday_net(user_id)
    daily_game_win = await get_daily_game_win(user_id)
    yesterday_game_win = await get_yesterday_game_win(user_id)

    # === Сумарний внесок (мінусові дні не враховуються) ===
    total_net = _positive_or_zero(today_net) + _positive_or_zero(yesterday_net)

    if total_net < 200:
        return False, (
            "❌ Ви не можете отримати виграш.\n\n"
            "❗Потрібно мати мінімум 200 грн депозиту\n"
            "протягом останніх 48 годин (сьогодні або вчора)."
        )

    # === Сумарний виграш за сьогодні + вчора (мінусові дні не враховуються) ===
    total_won = (
        _positive_or_zero(daily_game_win)
        + _positive_or_zero(yesterday_game_win)
        + prize_amount
    )

    # Максимально дозволений виграш
    max_allowed_win = int(total_net * 80 / 200)

    if total_won > max_allowed_win:
        return False, (
            f"❌ Ліміт виграшів вичерпано.\n\n"
            # f"За останні 2 дні у вас {total_net} грн внеску.\n"
            f"❗Ви можете виграти всього {max_allowed_win}  грн.\n"
            f"❗Ви вже виграли: {total_won - prize_amount} грн."
        )

    return True, "OK"






import random
import string
import logging
import aiosqlite

from datetime import datetime, timezone, timedelta
from .core import DB_PATH
from .wallet import get_daily_net, get_balance, ensure_daily_reset

KYIV_TZ = timezone(timedelta(hours=3))

PROMO_GOAL = 500
PROMO_BALANCE_LIMIT = 0


# Примітка: колонка promo_claimed_base додається централізовано
# в core.py -> ensure_users_table_and_columns(), окрема міграція тут не потрібна.


# ==================== ДОПОМІЖНІ ====================

def _generate_promo_code() -> str:
    return "PROMO-" + "".join(
        random.choices(string.ascii_uppercase + string.digits, k=6)
    )


async def get_promo_claimed_base(user_id: int) -> int:
    """Скільки net вже 'витрачено' на попередні промокоди сьогодні."""
    await ensure_daily_reset(user_id)
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT COALESCE(promo_claimed_base, 0) FROM users WHERE user_id = ?",
            (user_id,)
        )
        row = await cursor.fetchone()
        return row[0] if row else 0


async def get_promo_status(user_id: int) -> dict:
    """
    Повертає статус видачі промокоду.
    available_net показує, скільки накопичено понад уже видані промокоди.
    can_claim — чи можна забрати промокод прямо зараз.
    """
    today_net = await get_daily_net(user_id)
    claimed_base = await get_promo_claimed_base(user_id)
    balance = await get_balance(user_id)

    available_net = max(today_net - claimed_base, 0)

    can_claim = (available_net >= PROMO_GOAL) and (balance <= PROMO_BALANCE_LIMIT)

    return {
        "today_net": today_net,
        "claimed_base": claimed_base,
        "available_net": available_net,
        "balance": balance,
        "can_claim": can_claim,
        "balance_too_high": balance > PROMO_BALANCE_LIMIT,
        "progress_in_tier": available_net % PROMO_GOAL,
        "available_count": available_net // PROMO_GOAL,
    }


async def claim_promo(user_id: int) -> dict:
    """
    Атомарно генерує та видає промокод користувачу
    з перевіркою балансу ≤ PROMO_BALANCE_LIMIT (аналогічно кешбеку).
    """
    await ensure_daily_reset(user_id)

    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT daily_net, promo_claimed_base, balance FROM users WHERE user_id = ?",
            (user_id,)
        )
        row = await cursor.fetchone()
        if not row:
            return {"success": False, "reason": "no_user"}

        daily_net, claimed_base, balance = row
        daily_net = daily_net or 0
        claimed_base = claimed_base or 0
        balance = balance or 0

        available_net = daily_net - claimed_base

        if available_net < PROMO_GOAL:
            return {
                "success": False,
                "reason": "not_enough",
                "available_net": max(available_net, 0),
                "needed": PROMO_GOAL - max(available_net, 0),
            }

        if balance > PROMO_BALANCE_LIMIT:
            return {
                "success": False,
                "reason": "balance_too_high",
                "current_balance": balance,
                "max_allowed": PROMO_BALANCE_LIMIT,
            }

        # Генеруємо унікальний код "на льоту"
        code = _generate_promo_code()
        # На випадок колізії (малоймовірно) — пробуємо ще раз
        for _ in range(5):
            cur = await db.execute(
                "SELECT 1 FROM promocodes WHERE code = ?", (code,)
            )
            if not await cur.fetchone():
                break
            code = _generate_promo_code()

        new_claimed_base = claimed_base + PROMO_GOAL

        await db.execute(
            "INSERT INTO promocodes (code) VALUES (?)",
            (code,)
        )
        await db.execute(
            "UPDATE users SET promo_claimed_base = ? WHERE user_id = ?",
            (new_claimed_base, user_id)
        )
        await db.commit()

        logging.info(f"🎟 Промокод видано: user_id={user_id} code={code}")

        return {
            "success": True,
            "code": code,
            "claimed_from_net": PROMO_GOAL,
            "remaining_net": available_net - PROMO_GOAL,
        }



async def get_total_losses_all_time(user_id: int) -> int:
    """
    Глобальний накопичувальний програш/виграш користувача.
    Кожного дня при переході на новий день до цього значення додається
    daily_net того дня, що завершився (плюсові й мінусові значення однаково).
    """
    await ensure_daily_reset(user_id)   # гарантує, що вчорашній день вже "закритий" і врахований

    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT COALESCE(total_losses_all_time, 0) FROM users WHERE user_id = ?",
            (user_id,)
        )
        row = await cursor.fetchone()
        return row[0] if row else 0