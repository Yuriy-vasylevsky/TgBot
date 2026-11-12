"""One deposit dice bonus per Kyiv calendar day, credited atomically."""
from datetime import datetime, timedelta
import time
from zoneinfo import ZoneInfo

import aiosqlite
from db.core import DB_PATH

KYIV = ZoneInfo("Europe/Kyiv")
MAX_DEPOSIT_BASE = 500


async def get_fortune_winnings(user_id, *, now=None):
    """Return settled bonuses for today and yesterday in Kyiv."""
    today = datetime.fromtimestamp(time.time() if now is None else now, KYIV).date()
    days = (today.isoformat(), (today - timedelta(days=1)).isoformat())
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT day, COALESCE(SUM(bonus),0) FROM daily_fortune "
            "WHERE user_id=? AND day IN (?,?) AND dice_value IS NOT NULL GROUP BY day",
            (user_id, *days),
        )
        totals = dict(await cur.fetchall())
    return totals.get(days[0], 0), totals.get(days[1], 0)


async def init_daily_fortune():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""CREATE TABLE IF NOT EXISTS daily_fortune (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL, day TEXT NOT NULL,
            deposit_id INTEGER NOT NULL, deposit_amount INTEGER NOT NULL,
            dice_value INTEGER, bonus INTEGER, dice_message_id INTEGER,
            UNIQUE(user_id, day))""")
        cur = await db.execute("PRAGMA table_info(daily_fortune)")
        if 'game' not in {r[1] for r in await cur.fetchall()}:
            await db.execute("ALTER TABLE daily_fortune ADD COLUMN game TEXT NOT NULL DEFAULT 'fortune'")
        await db.commit()


async def _status(db, user_id, now):
    cur = await db.execute(
        "SELECT is_regular_player FROM users WHERE user_id=?", (user_id,)
    )
    player = await cur.fetchone()
    if not player or not player['is_regular_player']:
        return {"success": False, "reason": "not_regular"}
    local = datetime.fromtimestamp(now, KYIV)
    day = local.date().isoformat()
    cur = await db.execute("SELECT * FROM daily_fortune WHERE user_id=? AND day=?", (user_id, day))
    attempt = await cur.fetchone()
    if attempt:
        return {"success": False, "reason": "used" if attempt['dice_value'] else "pending", "attempt": dict(attempt)}
    start = local.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
    # payment_logs timestamps are stored as UTC+3, including in winter.
    # Safe awards are also logged there, but are not real deposits.
    cur = await db.execute("""SELECT id, amount FROM payment_logs
        WHERE user_id=? AND amount>0 AND COALESCE(comment, '') != 'SAFE_TOP_5'
        AND CAST(strftime('%s', created_at, '-3 hours') AS REAL) >= ?
        AND CAST(strftime('%s', created_at, '-3 hours') AS REAL) <= ?
        ORDER BY created_at DESC, id DESC LIMIT 1""", (user_id, start, now))
    deposit = await cur.fetchone()
    if not deposit:
        return {"success": False, "reason": "no_deposit"}
    return {"success": True, "day": day, "deposit_id": deposit['id'], "deposit_amount": deposit['amount']}


async def fortune_status(user_id, *, now=None):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        return await _status(db, user_id, time.time() if now is None else now)


async def reserve_fortune(user_id, *, now=None, game='fortune'):
    if game not in {'fortune', 'darts'}:
        raise ValueError('Invalid daily bonus game')
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute('BEGIN IMMEDIATE')
        result = await _status(db, user_id, time.time() if now is None else now)
        if not result['success']:
            return result
        cur = await db.execute("""INSERT INTO daily_fortune(user_id, day, deposit_id, deposit_amount, game)
            VALUES (?,?,?,?,?)""", (user_id, result['day'], result['deposit_id'], result['deposit_amount'], game))
        result['attempt_id'] = cur.lastrowid
        await db.commit()
        return result


async def release_fortune(attempt_id):
    """Only release when Telegram explicitly rejected the dice request."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM daily_fortune WHERE id=? AND dice_value IS NULL", (attempt_id,))
        await db.commit()


async def settle_fortune(attempt_id, value, message_id, *, username=None, full_name=None):
    if type(value) is not int or not 1 <= value <= 6:
        raise ValueError('Invalid dice value')
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute('BEGIN IMMEDIATE')
        cur = await db.execute('SELECT * FROM daily_fortune WHERE id=?', (attempt_id,))
        row = await cur.fetchone()
        if not row:
            raise ValueError('Attempt not found')
        if row['dice_value'] is None:
            multiplier = value - 1 if row['game'] == 'darts' else value
            bonus = min(row['deposit_amount'], MAX_DEPOSIT_BASE) * multiplier // 10
            credited = await db.execute("UPDATE users SET balance=COALESCE(balance,0)+? WHERE user_id=?", (bonus, row['user_id']))
            if credited.rowcount != 1:
                raise ValueError('Player not found')
            await db.execute("UPDATE daily_fortune SET dice_value=?,bonus=?,dice_message_id=? WHERE id=?", (value, bonus, message_id, attempt_id))
            if bonus > 0:
                await db.execute(
                    "INSERT INTO win_log(user_id,username,full_name,win_type,source,amount) "
                    "VALUES (?,?,?,?,?,?)",
                    (row['user_id'], username or '—', full_name or '—',
                     'daily_darts' if row['game'] == 'darts' else 'daily_fortune',
                     'Дартс — бонус за депозит' if row['game'] == 'darts' else 'Фортуна — бонус за депозит', bonus),
                )
        else:
            value, bonus = row['dice_value'], row['bonus']
        cur = await db.execute('SELECT balance FROM users WHERE user_id=?', (row['user_id'],))
        balance = (await cur.fetchone())[0]
        await db.commit()
        return {'value': value, 'bonus': bonus, 'deposit_amount': row['deposit_amount'],
                'bonus_base': min(row['deposit_amount'], MAX_DEPOSIT_BASE), 'balance': balance}
