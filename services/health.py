import aiosqlite
from aiohttp import web
from db.core import DB_PATH


async def health(request):
    try:
        # mode=ro prevents a health probe from creating a missing database.
        async with aiosqlite.connect(DB_PATH.as_uri() + "?mode=ro", uri=True) as db:
            await db.execute("SELECT user_id FROM users LIMIT 1")
    except Exception:
        return web.json_response({"status": "unavailable"}, status=503)
    return web.json_response({"status": "ok"})
