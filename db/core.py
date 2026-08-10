import os
from pathlib import Path
import logging
import aiosqlite
from datetime import datetime, timezone, timedelta
import json
import time

# DATA_DIR = os.environ.get("DATA_DIR", "/data")
# DB_PATH = Path(DATA_DIR) / "users.db"

# logging.basicConfig(level=logging.INFO)
# print(f"💾 Final DB path: {DB_PATH}")

# Визначення DATA_DIR з розумним fallback
if os.getenv("RAILWAY_ENVIRONMENT"):  # або RAILWAY_GIT_COMMIT_SHA, RAILWAY_VOLUME_NAME тощо — будь-яка Railway-специфічна змінна
    DATA_DIR = "/data"  # Volume на Railway монтується сюди
else:
    # Локально — використовуємо теку "data" в корені проєкту (створимо автоматично)
    DATA_DIR = "data"

# Повний шлях до бази
DB_PATH = Path(DATA_DIR) / "users.db"

# Створюємо теку автоматично (працює і локально, і на Railway)
Path(DATA_DIR).mkdir(parents=True, exist_ok=True)

# Додай це для дебагу (можна видалити після тестів)
print(f"Поточна робоча директорія: {Path.cwd()}")
print(f"DATA_DIR: {DATA_DIR}")
print(f"Final DB path (resolved): {DB_PATH.resolve()}")
print(f"Тека існує і доступна для запису? {Path(DATA_DIR).exists() and os.access(Path(DATA_DIR), os.W_OK)}")

logging.basicConfig(level=logging.INFO)
print(f"💾 Final DB path: {DB_PATH}")


# ===================== ІНІЦІАЛІЗАЦІЯ =====================
async def ensure_users_table_and_columns():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT, full_name TEXT,
            has_access INTEGER DEFAULT 0,
            last_active DATETIME DEFAULT (DATETIME('now', '+3 hours')),
            last_actions TEXT DEFAULT '',
            games_played INTEGER DEFAULT 0,
            games_won INTEGER DEFAULT 0,
            money_won INTEGER DEFAULT 0,
            has_claimed_gift INTEGER DEFAULT 0,
            balance INTEGER DEFAULT 0
            
        )""")

        async with db.execute("PRAGMA table_info(users)") as cur:
            cols = {r[1] for r in await cur.fetchall()}

        for col, sql in [
            # ("last_daily_bonus_date", "ALTER TABLE users ADD COLUMN last_daily_bonus_date TEXT"),
            # ("last_fortune_date", "ALTER TABLE users ADD COLUMN last_fortune_date TEXT"),
            ("balance", "ALTER TABLE users ADD COLUMN balance INTEGER DEFAULT 0"),
            ("frozen_balance", "ALTER TABLE users ADD COLUMN frozen_balance INTEGER DEFAULT 0"),
            ("freeze_until", "ALTER TABLE users ADD COLUMN freeze_until TEXT"),
      
            ("promo_claimed_base", "ALTER TABLE users ADD COLUMN promo_claimed_base INTEGER DEFAULT 0"),
            # ("project_net", "ALTER TABLE users ADD COLUMN project_net INTEGER DEFAULT 0"),
            # ("personal_net", "ALTER TABLE users ADD COLUMN personal_net INTEGER DEFAULT 0"),
            ("daily_net", "ALTER TABLE users ADD COLUMN daily_net INTEGER DEFAULT 0"),
            ("cashback_claimed_base", "ALTER TABLE users ADD COLUMN cashback_claimed_base INTEGER DEFAULT 0"),
            ("last_net_date", "ALTER TABLE users ADD COLUMN last_net_date TEXT"),
            ("yesterday_net", "ALTER TABLE users ADD COLUMN yesterday_net INTEGER DEFAULT 0"),
            ("daily_game_win", "ALTER TABLE users ADD COLUMN daily_game_win INTEGER DEFAULT 0"),
            ("yesterday_game_win", "ALTER TABLE users ADD COLUMN yesterday_game_win INTEGER DEFAULT 0"),
            ("last_game_win_date", "ALTER TABLE users ADD COLUMN last_game_win_date TEXT"),
            ("game_cooldown_until", "ALTER TABLE users ADD COLUMN game_cooldown_until TEXT"),
            ("promo_cooldown_until", "ALTER TABLE users ADD COLUMN promo_cooldown_until TEXT"),
            ("total_losses_all_time", "ALTER TABLE users ADD COLUMN total_losses_all_time INTEGER DEFAULT 0"),

            
        ]:
            if col not in cols:
                await db.execute(sql)
                print(f"✅ Додано колонку: {col}")

        await db.commit()


async def create_pending_payments_table():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS pending_payments (
                user_id INTEGER PRIMARY KEY,
                amount_kop INTEGER NOT NULL,
                comment TEXT UNIQUE NOT NULL,
                created_at REAL NOT NULL,
                mono_account TEXT DEFAULT '0'
            )
        """)
        await db.commit()


async def ensure_manual_payment_daily_numbering(db: aiosqlite.Connection) -> None:
    """Додає щоденну нумерацію лише для ручних заявок на поповнення."""
    cursor = await db.execute(
        "SELECT 1 FROM sqlite_master "
        "WHERE type = 'table' AND name = 'manual_payment_daily_sequences'"
    )
    sequence_already_existed = await cursor.fetchone() is not None
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS manual_payment_daily_sequences (
            payment_date TEXT PRIMARY KEY,
            last_number INTEGER NOT NULL DEFAULT 0
        )
        """
    )

    async with db.execute("PRAGMA table_info(manual_payments)") as cursor:
        columns = {row[1] for row in await cursor.fetchall()}
    if "payment_date" not in columns:
        await db.execute("ALTER TABLE manual_payments ADD COLUMN payment_date TEXT")
    if "daily_number" not in columns:
        await db.execute("ALTER TABLE manual_payments ADD COLUMN daily_number INTEGER")

    # Якщо раніше використовувалась спільна з Monobank послідовність,
    # одноразово перебудовуємо номери виключно за ручними заявками.
    if not sequence_already_existed:
        await db.execute("DROP INDEX IF EXISTS idx_manual_payment_daily_number")
        await db.execute(
            "UPDATE manual_payments SET payment_date = NULL, daily_number = NULL"
        )

    # Наявні номери зберігаємо, а старі заявки без номера дозаповнюємо.
    counters: dict[str, int] = {}
    async with db.execute(
        """
        SELECT payment_date, MAX(daily_number)
        FROM manual_payments
        WHERE payment_date IS NOT NULL AND daily_number IS NOT NULL
        GROUP BY payment_date
        """
    ) as cursor:
        for payment_date, last_number in await cursor.fetchall():
            counters[payment_date] = int(last_number or 0)

    async with db.execute(
        """
        SELECT id, created_at FROM manual_payments
        WHERE payment_date IS NULL OR daily_number IS NULL
        ORDER BY created_at, id
        """
    ) as cursor:
        unnumbered = await cursor.fetchall()
    for row_id, created_at in unnumbered:
        payment_date = str(created_at or "")[:10]
        if not payment_date:
            payment_date = datetime.now().date().isoformat()
        counters[payment_date] = counters.get(payment_date, 0) + 1
        await db.execute(
            "UPDATE manual_payments SET payment_date = ?, daily_number = ? WHERE id = ?",
            (payment_date, counters[payment_date], row_id),
        )

    for payment_date, last_number in counters.items():
        await db.execute(
            """
            INSERT INTO manual_payment_daily_sequences(payment_date, last_number)
            VALUES (?, ?)
            ON CONFLICT(payment_date) DO UPDATE SET last_number =
                MAX(last_number, excluded.last_number)
            """,
            (payment_date, last_number),
        )

    await db.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_manual_payment_daily_number "
        "ON manual_payments(payment_date, daily_number)"
    )


# async def create_used_monobank_txs_table():
#     async with aiosqlite.connect(DB_PATH) as db:
#         await db.execute("""
#             CREATE TABLE IF NOT EXISTS used_monobank_txs (
#                 tx_id TEXT PRIMARY KEY,
#                 user_id INTEGER NOT NULL,
#                 amount_kop INTEGER NOT NULL,
#                 payment_id TEXT,
#                 used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
#             )
#         """)
#         await db.execute("CREATE INDEX IF NOT EXISTS idx_tx_id ON used_monobank_txs(tx_id)")
#         await db.commit()





async def create_used_monobank_txs_table():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS used_monobank_txs (
                tx_id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                amount_kop INTEGER NOT NULL,
                payment_id TEXT,
                used_at DATETIME DEFAULT (DATETIME('now', '+3 hours'))
            )
        """)
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_tx_id ON used_monobank_txs(tx_id)"
        )
        await db.commit()


from db.winlog import ensure_win_log_table 

async def init_db():
    print("🔧 init_db() запущено...")
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await ensure_users_table_and_columns()
            await create_pending_payments_table()
            await create_used_monobank_txs_table()

            await ensure_win_log_table() 
            # Інші таблиці
            tables = [
                "promocodes (code TEXT PRIMARY KEY, active INTEGER DEFAULT 1)",
                "payment_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, username TEXT, amount INTEGER, comment TEXT, created_at DATETIME DEFAULT (DATETIME('now', '+3 hours')))",
                "manual_payments (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, username TEXT, full_name TEXT, amount INTEGER NOT NULL, receipt_file_id TEXT NOT NULL, receipt_type TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending', created_at DATETIME DEFAULT (DATETIME('now', '+3 hours')), reviewed_at DATETIME, reviewed_by INTEGER, review_source TEXT, route_reason TEXT, file_sha256 TEXT, perceptual_hash TEXT, gpt_result_json TEXT, gpt_decision TEXT, gpt_reason TEXT, gpt_confidence REAL, analysis_started_at DATETIME, analysis_completed_at DATETIME, receipt_retry_count INTEGER NOT NULL DEFAULT 0, payment_date TEXT, daily_number INTEGER)",
                "game_stats (game_name TEXT PRIMARY KEY, total_games INTEGER DEFAULT 0, wins INTEGER DEFAULT 0)",
                "slot_sessions (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, result TEXT, final_balance INTEGER, ts DATETIME DEFAULT (DATETIME('now', '+3 hours')))",
                "casino_codes (id INTEGER PRIMARY KEY AUTOINCREMENT, casino_type TEXT, code TEXT, used INTEGER DEFAULT 0, assigned_to INTEGER, assigned_at DATETIME)",
                "champion_checks_100 (id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT UNIQUE, used INTEGER DEFAULT 0, assigned_to INTEGER, assigned_at DATETIME)",
                "champion_checks_200 (id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT UNIQUE, used INTEGER DEFAULT 0, assigned_to INTEGER, assigned_at DATETIME)",
                "matic_checks_100 (id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT UNIQUE, used INTEGER DEFAULT 0, assigned_to INTEGER, assigned_at DATETIME)",
                "matic_checks_200 (id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT UNIQUE, used INTEGER DEFAULT 0, assigned_to INTEGER, assigned_at DATETIME)",
                "pending_rewards (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, code_id INTEGER, casino_type TEXT, status TEXT DEFAULT 'pending', ts DATETIME DEFAULT (DATETIME('now', '+3 hours')))",
                "banned_users (user_id INTEGER PRIMARY KEY, reason TEXT, banned_by INTEGER, ts DATETIME DEFAULT (DATETIME('now', '+3 hours')))",
                "banned_profile_users (user_id INTEGER PRIMARY KEY, reason TEXT, banned_by INTEGER, ts DATETIME DEFAULT (DATETIME('now', '+3 hours')))",
                "banned_receipt_autoapproval_users (user_id INTEGER PRIMARY KEY, reason TEXT, banned_by INTEGER, ts DATETIME DEFAULT (DATETIME('now', '+3 hours')))",
                "cards (id INTEGER PRIMARY KEY AUTOINCREMENT, bank_name TEXT, display_name TEXT, card_number TEXT)",
                "weekly_tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, description TEXT, reward TEXT, duration TEXT, is_active INTEGER DEFAULT 1, created_at DATETIME DEFAULT (DATETIME('now', '+3 hours')))",
                "user_tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, task_id INTEGER NOT NULL, is_completed INTEGER DEFAULT 0, completed_at DATETIME)",
                "safe_state (key TEXT PRIMARY KEY, value TEXT)",
                "notifications (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, username TEXT, full_name TEXT, type TEXT, message TEXT, created_at DATETIME DEFAULT (DATETIME('now', '+3 hours')))",
                "blackjack_sessions (id INTEGER PRIMARY KEY AUTOINCREMENT, is_win INTEGER)",
                "settings (key TEXT PRIMARY KEY, value REAL)",
                "issued_checks (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, check_type TEXT NOT NULL, code TEXT NOT NULL, price INTEGER NOT NULL, issued_at DATETIME DEFAULT (DATETIME('now', '+3 hours')))",
                "referrals (id INTEGER PRIMARY KEY AUTOINCREMENT, referrer_id INTEGER NOT NULL, referred_id INTEGER NOT NULL UNIQUE, was_existing_user INTEGER DEFAULT 0, paid INTEGER DEFAULT 0, bonus_given INTEGER DEFAULT 0, created_at DATETIME DEFAULT (DATETIME('now', '+3 hours')))",
                "piggy_bank_state (id INTEGER PRIMARY KEY CHECK (id = 1), balance INTEGER NOT NULL DEFAULT 0 CHECK (balance >= 0), limit_amount INTEGER NOT NULL DEFAULT 60 CHECK (limit_amount > 0), player_prize INTEGER NOT NULL DEFAULT 50 CHECK (player_prize >= 0), admin_prize INTEGER NOT NULL DEFAULT 10 CHECK (admin_prize >= 0), round_number INTEGER NOT NULL DEFAULT 1 CHECK (round_number > 0))",
                "piggy_bank_events (id INTEGER PRIMARY KEY AUTOINCREMENT, round_number INTEGER NOT NULL, user_id INTEGER NOT NULL, amount INTEGER NOT NULL, pot_before INTEGER NOT NULL, pot_after INTEGER NOT NULL, triggered INTEGER NOT NULL DEFAULT 0, player_prize INTEGER NOT NULL DEFAULT 0, admin_prize INTEGER NOT NULL DEFAULT 0, created_at DATETIME DEFAULT (DATETIME('now', '+3 hours')))",
                "piggy_bank_cooldowns (user_id INTEGER PRIMARY KEY, last_contribution_at REAL NOT NULL)",
            ]
            for t in tables:
                await db.execute(f"CREATE TABLE IF NOT EXISTS {t}")

            await db.execute(
                """
                INSERT OR IGNORE INTO piggy_bank_state
                    (id, balance, limit_amount, player_prize, admin_prize, round_number)
                VALUES (1, 0, 60, 50, 10, 1)
                """
            )

            async with db.execute("PRAGMA table_info(manual_payments)") as cur:
                manual_payment_columns = {row[1] for row in await cur.fetchall()}
            manual_payment_migrations = {
                "review_source": "ALTER TABLE manual_payments ADD COLUMN review_source TEXT",
                "route_reason": "ALTER TABLE manual_payments ADD COLUMN route_reason TEXT",
                "file_sha256": "ALTER TABLE manual_payments ADD COLUMN file_sha256 TEXT",
                "perceptual_hash": "ALTER TABLE manual_payments ADD COLUMN perceptual_hash TEXT",
                "gpt_result_json": "ALTER TABLE manual_payments ADD COLUMN gpt_result_json TEXT",
                "gpt_decision": "ALTER TABLE manual_payments ADD COLUMN gpt_decision TEXT",
                "gpt_reason": "ALTER TABLE manual_payments ADD COLUMN gpt_reason TEXT",
                "gpt_confidence": "ALTER TABLE manual_payments ADD COLUMN gpt_confidence REAL",
                "analysis_started_at": "ALTER TABLE manual_payments ADD COLUMN analysis_started_at DATETIME",
                "analysis_completed_at": "ALTER TABLE manual_payments ADD COLUMN analysis_completed_at DATETIME",
                "receipt_retry_count": "ALTER TABLE manual_payments ADD COLUMN receipt_retry_count INTEGER NOT NULL DEFAULT 0",
            }
            for column, sql in manual_payment_migrations.items():
                if column not in manual_payment_columns:
                    await db.execute(sql)

            await ensure_manual_payment_daily_numbering(db)

            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_manual_payments_status "
                "ON manual_payments(status)"
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_manual_payments_user_created "
                "ON manual_payments(user_id, created_at)"
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_manual_payments_sha256 "
                "ON manual_payments(file_sha256)"
            )

            # Назва слота (Карта 1/Карта 2) не змінюється, а назва банку
            # зберігається окремо й показується користувачам у реквізитах.
            async with db.execute("PRAGMA table_info(cards)") as cur:
                card_columns = {row[1] for row in await cur.fetchall()}
            if "display_name" not in card_columns:
                await db.execute("ALTER TABLE cards ADD COLUMN display_name TEXT")
                await db.execute(
                    """
                    UPDATE cards
                    SET display_name = CASE bank_name
                        WHEN 'Карта 1' THEN 'Абанк'
                        WHEN 'Карта 2' THEN 'Приват'
                        ELSE bank_name
                    END
                    WHERE display_name IS NULL OR TRIM(display_name) = ''
                    """
                )

            # Дефолтні картки
            cur = await db.execute("SELECT COUNT(*) FROM cards")
            if (await cur.fetchone())[0] == 0:
                await db.executemany(
                    "INSERT INTO cards (bank_name, display_name, card_number) VALUES (?, ?, ?)",
                    [("Карта 1", "Абанк", ""), ("Карта 2", "Приват", "")]
                )
                print("✅ Default cards added")

            await db.commit()
            print("🎉 База даних ініціалізована!")
    except Exception as e:
        logging.error(f"❌ CRITICAL ERROR in init_db: {e}", exc_info=True)




