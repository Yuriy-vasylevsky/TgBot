


import aiosqlite
import time
import logging

from .core import DB_PATH


# async def add_to_balance(user_id: int, amount_grn: int):
#     async with aiosqlite.connect(DB_PATH) as db:
#         await db.execute("""
#             INSERT INTO users (user_id, balance)
#             VALUES (?, ?)
#             ON CONFLICT(user_id) DO UPDATE SET balance = balance + ?
#         """, (user_id, amount_grn, amount_grn))
#         await db.commit()

from datetime import date

async def add_to_balance(user_id: int, amount_grn: int):
    today_str = date.today().isoformat()

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO users (user_id, balance)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET balance = balance + ?
        """, (user_id, amount_grn, amount_grn))

        await db.execute("""
            INSERT INTO users (user_id, daily_net, last_net_date)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                yesterday_net = CASE 
                    WHEN last_net_date != ? THEN daily_net
                    ELSE yesterday_net
                END,
                daily_net = CASE 
                    WHEN last_net_date = ? THEN daily_net + ?
                    ELSE ?
                END,
                last_net_date = ?
        """, (
            user_id, amount_grn, today_str,
            today_str,          # yesterday_net: якщо новий день — берем старий daily_net
            today_str, amount_grn, amount_grn,  # daily_net
            today_str
        ))

        await db.commit()


from datetime import date

async def get_daily_net(user_id: int) -> int:
    today = date.today().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT COALESCE(daily_net, 0) FROM users WHERE user_id = ? AND last_net_date = ?",
            (user_id, today)
        )
        row = await cursor.fetchone()
        return row[0] if row else 0


async def get_yesterday_net(user_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT COALESCE(yesterday_net, 0) FROM users WHERE user_id = ?",
            (user_id,)
        )
        row = await cursor.fetchone()
        return row[0] if row else 0


# async def get_personal_net(user_id: int) -> int:
#     async with aiosqlite.connect(DB_PATH) as db:
#         cursor = await db.execute(
#             "SELECT COALESCE(personal_net, 0) FROM users WHERE user_id = ?",
#             (user_id,)
#         )
#         row = await cursor.fetchone()
#         return row[0] if row else 0


# async def get_project_net() -> int:
#     """Повертає чистий результат проєкту"""
#     async with aiosqlite.connect(DB_PATH) as db:
#         cursor = await db.execute(
#             "SELECT COALESCE(project_net, 0) FROM users WHERE user_id = 0"
#         )
#         row = await cursor.fetchone()
#         return row[0] if row else 0


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
            INSERT INTO issued_checks (user_id, check_type, code, price, issued_at)
            VALUES (?, ?, ?, ?, DATETIME('now'))
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