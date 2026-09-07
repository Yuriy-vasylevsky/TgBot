

import hashlib
import logging
from datetime import datetime, time, timedelta
from urllib.parse import urlencode
from typing import Optional
from uuid import uuid4
from zoneinfo import ZoneInfo

import httpx

from .ma import SuperplatMatic
from handlers.config import (
    CASINO_API_BASE,
    CASINO_PUBLIC_KEY,
    CASINO_REPORT_LOGIN,
    CASINO_SECRET_KEY,
    CASINO_TIMEZONE,
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
        # Кожен запит має власний tr, інакше Champion повертає кешовану відповідь.
        params["tr"] = f"{CASINO_TR_PREFIX}{uuid4().hex}"
    
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


def champion_yesterday_period(now: datetime | None = None) -> tuple[datetime, datetime]:
    """Операційна доба Champion: учора 07:00 — сьогодні 07:00, час Києва."""
    timezone = ZoneInfo(CASINO_TIMEZONE)
    if now is None:
        now = datetime.now(timezone)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=timezone)
    else:
        now = now.astimezone(timezone)

    end = datetime.combine(now.date(), time(7), tzinfo=timezone)
    start = end - timedelta(days=1)
    return start, end


def _api_date(value: datetime) -> str:
    return value.strftime("%Y%m%d%H%M%S")


async def _casino_get(endpoint: str, params: dict) -> dict | None:
    """Виконує підписаний GET-запит та повертає лише коректну JSON-відповідь."""
    if not CASINO_PUBLIC_KEY or not CASINO_SECRET_KEY:
        logger.error("Champion API keys are not configured")
        return None

    url, _ = _build_url(endpoint, params)
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            if "application/json" not in response.headers.get("content-type", ""):
                logger.error("Champion returned a non-JSON response")
                return None
            data = response.json()
            logger.info(
                "Champion response for %s: success=%r, fields=%s",
                endpoint,
                data.get("success"),
                ", ".join(sorted(data.keys())),
            )
            return data
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("Champion request to %s failed: %s", endpoint, exc)
        return None


async def get_champion_yesterday_stats() -> dict:
    """Повертає report-user касира за попередню операційну добу."""
    start, end = champion_yesterday_period()
    start_value, end_value = _api_date(start), _api_date(end)
    if not CASINO_REPORT_LOGIN:
        return {
            "success": False,
            "start": start,
            "end": end,
            "message": "Не задано CASINO_REPORT_LOGIN.",
        }

    data = await _casino_get(
        "/api/report-user",
        {"login": CASINO_REPORT_LOGIN, "start": start_value, "end": end_value},
    )
    if not data or not data.get("success"):
        return {
            "success": False,
            "start": start,
            "end": end,
            "message": (data or {}).get("message", "Не вдалося отримати звіт касира."),
        }

    return {
        "success": True,
        "start": start,
        "end": end,
        "login": CASINO_REPORT_LOGIN,
        "deposit": float(data.get("deposit", 0) or 0),
        "close": float(data.get("close", 0) or 0),
        "result": float(data.get("result", 0) or 0),
    }


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
        

