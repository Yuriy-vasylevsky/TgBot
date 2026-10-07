"""Small async client for the official Crypto Pay API."""

from __future__ import annotations

from typing import Any

import httpx


class CryptoPayError(RuntimeError):
    """Raised when Crypto Pay rejects a request or returns invalid data."""


class CryptoPayClient:
    def __init__(self, token: str, *, testnet: bool = False, timeout: float = 15.0):
        if not token:
            raise ValueError("CRYPTO_PAY_TOKEN is required")
        self.token = token
        self.base_url = (
            "https://testnet-pay.crypt.bot/api"
            if testnet
            else "https://pay.crypt.bot/api"
        )
        self.timeout = timeout

    async def _request(self, method: str, payload: dict[str, Any] | None = None) -> Any:
        headers = {"Crypto-Pay-API-Token": self.token}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/{method}",
                headers=headers,
                json=payload or {},
            )
        response.raise_for_status()
        data = response.json()
        if not data.get("ok"):
            error = data.get("error") or data.get("error_code") or "unknown error"
            raise CryptoPayError(f"Crypto Pay {method} failed: {error}")
        return data.get("result")

    async def get_me(self) -> dict[str, Any]:
        return await self._request("getMe")

    async def create_uah_invoice(
        self,
        amount_grn: int,
        *,
        user_id: int,
        expires_in: int = 3600,
    ) -> dict[str, Any]:
        return await self._request(
            "createInvoice",
            {
                "currency_type": "fiat",
                "fiat": "UAH",
                "accepted_assets": "USDT",
                "amount": str(amount_grn),
                "description": f"Поповнення балансу на {amount_grn} грн",
                "payload": f"wallet:{user_id}:{amount_grn}",
                "allow_comments": False,
                "allow_anonymous": False,
                "expires_in": expires_in,
            },
        )

    async def create_usdt_invoice(
        self,
        amount_usdt: str,
        *,
        user_id: int,
        amount_grn: int,
        expires_in: int = 3600,
    ) -> dict[str, Any]:
        return await self._request(
            "createInvoice",
            {
                "currency_type": "crypto",
                "asset": "USDT",
                "amount": amount_usdt,
                "description": f"Поповнення балансу на {amount_grn} грн",
                "payload": f"wallet:{user_id}:{amount_grn}:{amount_usdt}",
                "allow_comments": False,
                "allow_anonymous": False,
                "expires_in": expires_in,
            },
        )

    async def get_exchange_rate(self, source: str, target: str) -> str:
        rates = await self._request("getExchangeRates")
        for rate in rates if isinstance(rates, list) else []:
            if (
                rate.get("source") == source
                and rate.get("target") == target
                and rate.get("is_valid") is not False
            ):
                return str(rate["rate"])
        raise CryptoPayError(f"Exchange rate {source}/{target} is unavailable")

    async def get_invoice(self, invoice_id: int) -> dict[str, Any] | None:
        result = await self._request(
            "getInvoices",
            {"invoice_ids": str(invoice_id), "count": 1},
        )
        items = result.get("items", []) if isinstance(result, dict) else []
        return items[0] if items else None

    async def delete_invoice(self, invoice_id: int) -> bool:
        return bool(
            await self._request("deleteInvoice", {"invoice_id": invoice_id})
        )
