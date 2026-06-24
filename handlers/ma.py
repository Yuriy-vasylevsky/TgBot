
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
        payload = {"login": self.subagent, "password": password_md5}

        async with session.post(url, json=payload) as resp:
            text = await resp.text()
            print(f"[AUTH] Status: {resp.status} | Body: {text[:300]}")

            if resp.status != 200:
                raise Exception(f"Auth error {resp.status}: {text[:400]}")

            data = self._parse_json(text)
            self.token = data.get("token")
            if not self.token:
                raise Exception(f"No token in auth response: {data}")
            return self.token

    async def get_my_id(self) -> int:
        """Отримує ID поточного Subagent"""
        token = await self._auth()
        session = await self._get_session()

        async with session.post(f"{BASE_URL}/getInfo", json={}, headers={"Token": token}) as resp:
            text = await resp.text()
            print(f"[GETINFO] Status: {resp.status} | Body: {text[:500]}")

            if resp.status != 200:
                raise Exception(f"getInfo error {resp.status}: {text[:400]}")

            data = self._parse_json(text)
            parent_id = data.get("id") or data.get("user_id") or data.get("parentId")
            if parent_id is None:
                raise Exception(f"Cannot find ID in getInfo response: {text[:400]}")
            return int(parent_id)

    async def add_codes(self, parent_id: int, count: int, amount: int) -> Dict:
        """Додає ігрові коди (Matic)"""
        token = await self._auth()
        session = await self._get_session()

        payload = {"parentId": parent_id, "count": count, "amount": amount * 100}

        async with session.post(f"{BASE_URL}/addCodes", json=payload, headers={"Token": token}) as resp:
            text = await resp.text()
            print(f"[ADDCODES] Status: {resp.status} | Body: {text[:400]}")

            if resp.status != 200:
                raise Exception(f"addCodes error {resp.status}: {text[:400]}")

            return self._parse_json(text)

    async def get_terminal_id(self, code: str) -> int:
        """Отримує ID терміналу за кодом"""
        token = await self._auth()
        session = await self._get_session()

        async with session.post(f"{BASE_URL}/getTerminalId", json={"code": code}, headers={"Token": token}) as resp:
            text = await resp.text()
            print(f"[GETTERMINALID] Status: {resp.status} | Body: {text[:400]}")

            if resp.status != 200:
                raise Exception(f"getTerminalId error {resp.status}: {text[:400]}")

            data = self._parse_json(text)
            terminal_id = data.get("id") or data.get("terminalId") or data.get("terminal_id")
            if terminal_id is None:
                raise Exception(f"Terminal ID not found for code {code}")
            return int(terminal_id)

    async def get_terminal_balance(self, terminal_id: int) -> float:
        """Баланс терміналу (в грн, як повертає сервер)"""
        token = await self._auth()
        session = await self._get_session()

        async with session.post(f"{BASE_URL}/getBalanceTerminal", json={"id": terminal_id}, headers={"Token": token}) as resp:
            text = await resp.text()
            print(f"[GETBALANCETERMINAL] Status: {resp.status} | Body: {text[:500]}")

            if resp.status != 200:
                raise Exception(f"getBalanceTerminal error {resp.status}: {text[:400]}")

            data = self._parse_json(text)
            return float(data.get("amount") or data.get("balance") or 0)

    async def collect_terminal(self, terminal_id: int) -> Dict:
        """Збирає баланс терміналу на субагента"""
        token = await self._auth()
        session = await self._get_session()

        payload = {"id": terminal_id, "force": True}

        async with session.post(f"{BASE_URL}/collectTerminal", json=payload, headers={"Token": token}) as resp:
            text = await resp.text()
            print(f"[COLLECTTERMINAL] Status: {resp.status} | Body: {text[:400]}")

            if resp.status != 200:
                raise Exception(f"collectTerminal error {resp.status}: {text[:400]}")

            return self._parse_json(text)

    async def delete_code(self, code: str) -> Dict:
        """Видалити Matic код після закриття"""
        token = await self._auth()
        session = await self._get_session()

        async with session.post(f"{BASE_URL}/deleteCode", json={"code": code}, headers={"Token": token}) as resp:
            text = await resp.text()
            print(f"[DELETECODE] Status: {resp.status} | Body: {text[:400]}")

            if resp.status != 200:
                raise Exception(f"deleteCode error: {resp.status} - {text[:300]}")

            return self._parse_json(text) if text.strip() else {"status": "ok"}

    async def get_currencies(self) -> Dict:
        """Список валют системи"""
        token = await self._auth()
        session = await self._get_session()

        async with session.post(f"{BASE_URL}/getCurrencies", json={}, headers={"Token": token}) as resp:
            text = await resp.text()
            print(f"[GETCURRENCIES] Status: {resp.status} | Body: {text[:400]}")

            if resp.status != 200:
                raise Exception(f"getCurrencies error {resp.status}: {text[:400]}")

            return self._parse_json(text)

    async def do_transaction_to_terminal(self, code: str, amount: int, currency_id: int = 0) -> Dict:
        """Поповнення терміналу через doTransaction (account -> terminal, deposit)"""
        token = await self._auth()
        session = await self._get_session()

        payload = {
            "terminalLogin": None,
            "terminalCode": code,
            "isTerminal": True,
            "isDeposit": True,
            "currencyId": currency_id,
            "amount": amount 
        }

        async with session.post(f"{BASE_URL}/doTransaction", json=payload, headers={"Token": token}) as resp:
            text = await resp.text()
            print(f"[DOTRANSACTION] Status: {resp.status} | Body: {text[:400]}")

            if resp.status != 200:
                raise Exception(f"doTransaction error {resp.status}: {text[:400]}")

            return self._parse_json(text)

    async def get_balance_by_code(self, code: str) -> float:
        """Баланс чека в грн через terminal_id"""
        terminal_id = await self.get_terminal_id(code)
        try:
            return await self.get_terminal_balance(terminal_id)
        except Exception as e:
            if "no such terminal" in str(e):
                return -1.0  # сигнал "чек вже неактуальний, треба видалити"
            raise

    async def close_check_by_code(self, code: str) -> Dict:
        """Закриває чек: збирає баланс терміналу на субагента і видаляє код"""
        terminal_id = await self.get_terminal_id(code)
        balance = await self.get_terminal_balance(terminal_id)

        print(f"[CLOSE_CHECK] code={code} terminal_id={terminal_id} balance_raw={balance}")

        collect_result = await self.collect_terminal(terminal_id)

        try:
            await self.delete_code(code)
        except Exception as e:
            print(f"[CLOSE_CHECK] delete_code не вдався для {code}: {e}")

        return {"success": True, "balance": balance, "collect_result": collect_result}

    async def add_to_check_by_code(self, code: str, amount: int) -> Dict:
        """Поповнює чек через doTransaction"""
        return await self.do_transaction_to_terminal(code, amount)

    @staticmethod
    def _parse_json(text: str) -> Dict:
        """Парсить JSON з тіла відповіді незалежно від Content-Type заголовка"""
        import json
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            import re
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except json.JSONDecodeError:
                    pass
            raise Exception(f"Cannot parse JSON response: {text[:400]}")