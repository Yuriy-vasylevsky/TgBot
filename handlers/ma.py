import aiohttp
import hashlib
from typing import Optional, Dict

BASE_URL = "https://api.superplat.pw/api/v1"


class SuperplatMatic:
    def __init__(self, subagent: str = "alb2", password: str = "21212121"):
        self.subagent = subagent
        self.password = password
        self.token: Optional[str] = None
        self.session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                headers={
                    "User-Agent": "SuperplatBot/1.0",
                    "Accept": "application/json, text/plain, */*"
                }
            )
        return self.session

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()

    async def _auth(self) -> str:
        if self.token:
            return self.token

        session = await self._get_session()
        url = f"{BASE_URL}/auth"

        password_md5 = hashlib.md5(self.password.encode('utf-8')).hexdigest()

        payload = {
            "login": self.subagent,
            "password": password_md5
        }

        async with session.post(url, json=payload) as resp:
            text = await resp.text()
            print(f"[AUTH] Status: {resp.status} | Content-Type: {resp.headers.get('content-type')}")
            print(f"[AUTH] Body: {text[:300]}")

            if resp.status != 200:
                raise Exception(f"Auth error {resp.status}: {text[:400]}")

            try:
                data = await resp.json()
            except:
                import re
                token_match = re.search(r'"token"\s*:\s*"([^"]+)"', text)
                if token_match:
                    self.token = token_match.group(1)
                    return self.token
                raise Exception(f"Cannot parse auth response: {text[:200]}")

            self.token = data.get("token")
            if not self.token:
                raise Exception(f"No token in auth response: {data}")
            return self.token

    async def get_my_id(self) -> int:
        """Отримує ID поточного Subagent"""
        token = await self._auth()
        session = await self._get_session()

        url = f"{BASE_URL}/getInfo"
        headers = {"Token": token}

        async with session.post(url, json={}, headers=headers) as resp:
            text = await resp.text()
            print(f"[GETINFO] Status: {resp.status} | Content-Type: {resp.headers.get('content-type')}")
            print(f"[GETINFO] Body: {text[:500]}")

            if resp.status != 200:
                raise Exception(f"getInfo error {resp.status}: {text[:400]}")

            # Пробуємо JSON, якщо не виходить — шукаємо id у тексті
            try:
                data = await resp.json()
                parent_id = data.get("id") or data.get("user_id") or data.get("parentId")
                if parent_id:
                    return int(parent_id)
            except:
                pass

            # Якщо не JSON — шукаємо число id
            import re
            id_match = re.search(r'"?id"?\s*[:=]\s*(\d+)', text)
            if id_match:
                return int(id_match.group(1))

            raise Exception(f"Cannot find ID in getInfo response: {text[:400]}")

    async def add_codes(self, parent_id: int, count: int, amount: int) -> Dict:
        """Додає ігрові коди (Matic)"""
        token = await self._auth()
        session = await self._get_session()

        url = f"{BASE_URL}/addCodes"
        headers = {"Token": token}

        payload = {
            "parentId": parent_id,
            "count": count,
            "amount": amount * 100
        }

        async with session.post(url, json=payload, headers=headers) as resp:
            text = await resp.text()
            print(f"[ADDCODES] Status: {resp.status} | Body: {text[:400]}")

            if resp.status != 200:
                raise Exception(f"addCodes error {resp.status}: {text[:400]}")

            try:
                return await resp.json()
            except:
                import json
                try:
                    return json.loads(text)
                except:
                    return {"status": "ok", "raw": text}