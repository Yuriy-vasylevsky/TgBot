# # handlers/casino_api.py
# import hashlib
# from aiogram.dispatcher.router import Router
# import httpx
# import logging
# from datetime import datetime
# from urllib.parse import urlparse, urlencode

# from handlers.config import (
#     CASINO_API_BASE,
#     CASINO_PUBLIC_KEY,
#     CASINO_SECRET_KEY,
#     CASINO_TR_PREFIX,
# )
# router = Router()
# logger = logging.getLogger(__name__)


# def _generate_sign(api_uri: str) -> str:
#     """Генерує sign = MD5(api_uri:secret_key)"""
#     to_hash = f"{api_uri}:{CASINO_SECRET_KEY}"
#     return hashlib.md5(to_hash.encode('utf-8')).hexdigest()


# def _build_url(endpoint: str, params: dict) -> tuple[str, str]:
#     """Будує URL + sign. Працює для всіх запитів."""
#     params = params.copy()
    
#     # Генеруємо tr, якщо немає
#     if "tr" not in params:
#         params["tr"] = f"{CASINO_TR_PREFIX}{int(datetime.now().timestamp() * 1000)}"
    
#     params["key"] = CASINO_PUBLIC_KEY

#     # Обробка sum тільки якщо він є
#     if "sum" in params:
#         params["sum"] = str(int(float(params["sum"])))  # без .0

#     # Сортуємо параметри
#     sorted_params = sorted(params.items())
#     query_string = urlencode(sorted_params)
    
#     api_uri = f"{endpoint}?{query_string}"
#     sign = _generate_sign(api_uri)
    
#     params["sign"] = sign
    
#     full_url = f"{CASINO_API_BASE}{endpoint}?{urlencode(sorted_params)}&sign={sign}"
    
#     logger.info(f"API_URI for sign: {api_uri}")
#     logger.info(f"Generated sign: {sign}")
    
#     return full_url, params["tr"]


# async def create_invoice(sum_grn: float) -> dict | None:
#     """Створює новий рахунок в казино"""
#     endpoint = "/api/invoice/new"
#     params = {"sum": round(float(sum_grn), 2)}

#     url, tr = _build_url(endpoint, params)

#     logger.info(f"→ Запит до Casino API: {url}")

#     async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
#         try:
#             resp = await client.get(url)
#             logger.info(f"← Статус: {resp.status_code} | Content-Type: {resp.headers.get('content-type')}")

#             # Якщо відповідь не JSON — виводимо перші 300 символів
#             if "application/json" not in resp.headers.get("content-type", ""):
#                 logger.error(f"Отримано не JSON! Перші 300 символів:\n{resp.text[:300]}")
#                 return None

#             data = resp.json()
#             logger.info(f"Casino response: {data}")

#             if data.get("success"):
#                 invoice = data["invoice"]
#                 return {
#                     "success": True,
#                     "invoice": invoice,
#                     "code": invoice,
#                     "sum": data["sum"],
#                     "url": f"https://spinplanet.net/?login_code={invoice}"
#                 }
#             else:
#                 logger.error(f"Casino API Error: {data.get('message')} | Code: {data.get('code')}")
#                 return None

#         except Exception as e:
#             logger.exception(f"Casino API Exception: {e}")
#             return None


# async def check_invoice(invoice: str) -> dict | None:
#     """Перевіряє стан рахунку"""
#     endpoint = "/api/invoice/check"
#     params = {"invoice": invoice}

#     url, tr = _build_url(endpoint, params)

#     async with httpx.AsyncClient(timeout=10.0) as client:
#         resp = await client.get(url)
#         return resp.json()
    

# async def get_jp_bonus() -> dict | None:
#     """Отримує поточний джекпот і бонус"""
#     endpoint = "/api/jp-bonus"
#     params = {}  # без параметрів

#     url, tr = _build_url(endpoint, params)

#     logger.info(f"→ Запит джекпоту: {url}")

#     async with httpx.AsyncClient(timeout=10.0) as client:
#         try:
#             resp = await client.get(url)
#             data = resp.json()
#             logger.info(f"Джекпот відповідь: {data}")

#             if data.get("success"):
#                 return {
#                     "success": True,
#                     "jackpot": data.get("jackpot", 0),
#                     "bonus": data.get("bonus", 0)
#                 }
#             else:
#                 logger.error(f"Помилка джекпоту: {data.get('message')}")
#                 return None
#         except Exception as e:
#             logger.exception(f"Помилка при отриманні джекпоту: {e}")
#             return None
        

# async def close_invoice(invoice: str) -> dict | None:
#     """Закриває рахунок і повертає залишок"""
#     endpoint = "/api/invoice/close"
#     params = {"invoice": invoice}

#     url, tr = _build_url(endpoint, params)

#     logger.info(f"→ Закриття чека {invoice}: {url}")

#     async with httpx.AsyncClient(timeout=15.0) as client:
#         try:
#             resp = await client.get(url)
#             logger.info(f"← Статус: {resp.status_code}")

#             if "application/json" not in resp.headers.get("content-type", ""):
#                 logger.error(f"Не JSON! {resp.text[:300]}")
#                 return None

#             data = resp.json()
#             logger.info(f"Casino close response: {data}")

#             if data.get("success"):
#                 return {
#                     "success": True,
#                     "invoice": data.get("invoice"),
#                     "sum": float(data.get("sum", 0)),   # залишок
#                     "tr": data.get("tr")
#                 }
#             else:
#                 logger.error(f"Помилка закриття: {data.get('message')} | code: {data.get('code')}")
#                 return None

#         except Exception as e:
#             logger.exception(f"Exception при закритті чека {invoice}: {e}")
#             return None
        

# async def close_invoice(invoice: str) -> dict | None:
#     """Закриває рахунок Champion і повертає залишок на баланс"""
#     endpoint = "/api/invoice/close"
#     params = {"invoice": invoice}

#     url, tr = _build_url(endpoint, params)

#     logger.info(f"→ Закриття чека {invoice} | URL: {url}")

#     async with httpx.AsyncClient(timeout=15.0) as client:
#         try:
#             resp = await client.get(url)
#             logger.info(f"← Статус закриття: {resp.status_code} | Content-Type: {resp.headers.get('content-type')}")

#             if "application/json" not in resp.headers.get("content-type", ""):
#                 logger.error(f"Отримано не JSON при закритті: {resp.text[:400]}")
#                 return None

#             data = resp.json()
#             logger.info(f"Close invoice response: {data}")

#             if data.get("success"):
#                 remaining = float(data.get("sum", 0))
#                 return {
#                     "success": True,
#                     "invoice": data.get("invoice"),
#                     "sum": remaining,
#                     "tr": data.get("tr")
#                 }
#             else:
#                 logger.error(f"API помилка закриття: {data.get('message')} | code: {data.get('code')}")
#                 return None

#         except Exception as e:
#             logger.exception(f"Exception при закритті чека {invoice}: {e}")
#             return None
        

# async def add_to_invoice(invoice: str, sum_grn: float) -> dict | None:
#     """Поповнює вже існуючий чек"""
#     endpoint = "/api/invoice/add"
#     params = {
#         "invoice": invoice,
#         "sum": round(float(sum_grn), 2)
#     }

#     url, tr = _build_url(endpoint, params)

#     logger.info(f"→ Поповнення чека {invoice} на {sum_grn} грн")

#     async with httpx.AsyncClient(timeout=15.0) as client:
#         try:
#             resp = await client.get(url)
#             logger.info(f"← Статус: {resp.status_code}")

#             if "application/json" not in resp.headers.get("content-type", ""):
#                 logger.error(f"Не JSON: {resp.text[:300]}")
#                 return None

#             data = resp.json()
#             logger.info(f"Add to invoice response: {data}")

#             if data.get("success"):
#                 return {
#                     "success": True,
#                     "invoice": data.get("invoice"),
#                     "new_sum": float(data.get("sum", 0)),
#                 }
#             else:
#                 logger.error(f"Помилка поповнення: {data.get('message')}")
#                 return None

#         except Exception as e:
#             logger.exception(f"Exception add_to_invoice: {e}")
#             return None
        



# # handlers/casino_api.py
# from .ma import SuperplatMatic
# from typing import Optional

# # Ледача ініціалізація
# _matic_api: Optional[SuperplatMatic] = None

# def get_matic_api() -> SuperplatMatic:
#     global _matic_api
#     if _matic_api is None:
#         _matic_api = SuperplatMatic(subagent="alb2", password="21212121")
#     return _matic_api


# # === MATIC ===
# async def create_matic_checks(amount: int, count: int = 1):
#     """Створює задану кількість Matic чеків"""
#     matic_api = get_matic_api()
#     parent_id = await matic_api.get_my_id()
#     result = await matic_api.add_codes(parent_id=parent_id, count=count, amount=amount)
#     return result

# import atexit
# import asyncio

# @atexit.register
# def close_matic_api():
#     if _matic_api and _matic_api.session:
#         try:
#             loop = asyncio.get_event_loop()
#             if loop.is_running():
#                 loop.create_task(_matic_api.close())
#             else:
#                 loop.run_until_complete(_matic_api.close())
#         except:
#             pass

import hashlib
import logging
from datetime import datetime
from urllib.parse import urlencode
from typing import Optional

import httpx

from .ma import SuperplatMatic
from handlers.config import (
    CASINO_API_BASE,
    CASINO_PUBLIC_KEY,
    CASINO_SECRET_KEY,
    CASINO_TR_PREFIX,
)

logger = logging.getLogger(__name__)

# ==================== MATIC API (Superplat) ====================

_matic_api: Optional[SuperplatMatic] = None


def get_matic_api() -> SuperplatMatic:
    global _matic_api
    if _matic_api is None:
        _matic_api = SuperplatMatic(subagent="alb2", password="21212121")
    return _matic_api


async def create_matic_checks(amount: int, count: int = 1):
    """Створює Matic чеки через Superplat API"""
    try:
        matic_api = get_matic_api()
        parent_id = await matic_api.get_my_id()
        
        result = await matic_api.add_codes(
            parent_id=parent_id,
            count=count,
            amount=amount
        )
        return result
    except Exception as e:
        logger.exception(f"Error creating Matic checks: {e}")
        raise


# ==================== CHAMPION API (залишаємо як було) ====================

def _generate_sign(api_uri: str) -> str:
    to_hash = f"{api_uri}:{CASINO_SECRET_KEY}"
    return hashlib.md5(to_hash.encode('utf-8')).hexdigest()


def _build_url(endpoint: str, params: dict):
    params = params.copy()
    
    if "tr" not in params:
        params["tr"] = f"{CASINO_TR_PREFIX}{int(datetime.now().timestamp() * 1000)}"
    
    params["key"] = CASINO_PUBLIC_KEY

    if "sum" in params:
        params["sum"] = str(int(float(params["sum"])))

    sorted_params = sorted(params.items())
    query_string = urlencode(sorted_params)
    
    api_uri = f"{endpoint}?{query_string}"
    sign = _generate_sign(api_uri)
    
    params["sign"] = sign
    full_url = f"{CASINO_API_BASE}{endpoint}?{urlencode(sorted_params)}&sign={sign}"
    
    return full_url, params["tr"]


async def create_invoice(sum_grn: float):
    """Створює новий Champion чек"""
    endpoint = "/api/invoice/new"
    params = {"sum": round(float(sum_grn), 2)}

    url, tr = _build_url(endpoint, params)

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.get(url)
            if "application/json" not in resp.headers.get("content-type", ""):
                logger.error(f"Non-JSON response: {resp.text[:300]}")
                return None

            data = resp.json()
            if data.get("success"):
                invoice = data["invoice"]
                return {
                    "success": True,
                    "invoice": invoice,
                    "code": invoice,
                    "sum": data["sum"],
                    "url": f"https://spinplanet.net/?login_code={invoice}"
                }
            else:
                logger.error(f"Casino API Error: {data}")
                return None
        except Exception as e:
            logger.exception(f"create_invoice error: {e}")
            return None


async def check_invoice(invoice: str):
    endpoint = "/api/invoice/check"
    params = {"invoice": invoice}
    url, _ = _build_url(endpoint, params)

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url)
        return resp.json()


async def close_invoice(invoice: str):
    endpoint = "/api/invoice/close"
    params = {"invoice": invoice}
    url, _ = _build_url(endpoint, params)

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.get(url)
            if "application/json" not in resp.headers.get("content-type", ""):
                return None
            return resp.json()
        except Exception as e:
            logger.exception(f"close_invoice error: {e}")
            return None


async def add_to_invoice(invoice: str, sum_grn: float):
    endpoint = "/api/invoice/add"
    params = {"invoice": invoice, "sum": round(float(sum_grn), 2)}
    url, _ = _build_url(endpoint, params)

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.get(url)
            if "application/json" not in resp.headers.get("content-type", ""):
                return None
            return resp.json()
        except Exception as e:
            logger.exception(f"add_to_invoice error: {e}")
            return None
        

