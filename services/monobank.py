"""Read-only Monobank statements and unambiguous payment matching."""
import time
import httpx


class TooManyRequests(Exception):
    pass


async def get_statements(token: str, account: str, created_at: float) -> list[dict]:
    if not token:
        raise ValueError("MONO_TOKEN is required")
    now = int(time.time())
    start = max(int(created_at) - 60, now - 7 * 86400)
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(
            f"https://api.monobank.ua/personal/statement/{account}/{start}/{now}",
            headers={"X-Token": token},
        )
        if response.status_code == 429:
            raise TooManyRequests()
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, list):
            raise ValueError("Invalid Monobank statement response")
        return data


def match_payment(transactions: list[dict], pending: dict) -> dict | None:
    # Amount/time alone cannot prove who sent a transfer. Require the reference
    # supplied to the payer; transfers without it must be reviewed by a human.
    matches = [tx for tx in transactions if
        tx.get("id") and tx.get("amount") == pending["amount_kop"]
        and tx.get("currencyCode") == 980
        and not tx.get("hold", False)
        and tx.get("time", 0) >= pending["created_at"] - 60
        and (tx.get("comment") or "").strip() == pending["comment"]
    ]
    return matches[0] if len(matches) == 1 else None
