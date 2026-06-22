# import aiohttp
# import hashlib
# from typing import Optional, Dict

# BASE_URL = "https://api.superplat.pw/api/v1"


# class SuperplatMatic:
#     def __init__(self, subagent: str = "alb2", password: str = "21212121"):
#         self.subagent = subagent
#         self.password = password
#         self.token: Optional[str] = None
#         self.session: Optional[aiohttp.ClientSession] = None

#     async def _get_session(self) -> aiohttp.ClientSession:
#         if self.session is None or self.session.closed:
#             self.session = aiohttp.ClientSession(
#                 headers={
#                     "User-Agent": "SuperplatBot/1.0",
#                     "Accept": "application/json, text/plain, */*"
#                 }
#             )
#         return self.session

#     async def close(self):
#         if self.session and not self.session.closed:
#             await self.session.close()

#     async def _auth(self) -> str:
#         if self.token:
#             return self.token

#         session = await self._get_session()
#         url = f"{BASE_URL}/auth"

#         password_md5 = hashlib.md5(self.password.encode('utf-8')).hexdigest()

#         payload = {
#             "login": self.subagent,
#             "password": password_md5
#         }

#         async with session.post(url, json=payload) as resp:
#             text = await resp.text()
#             print(f"[AUTH] Status: {resp.status} | Content-Type: {resp.headers.get('content-type')}")
#             print(f"[AUTH] Body: {text[:300]}")

#             if resp.status != 200:
#                 raise Exception(f"Auth error {resp.status}: {text[:400]}")

#             try:
#                 data = await resp.json()
#             except:
#                 import re
#                 token_match = re.search(r'"token"\s*:\s*"([^"]+)"', text)
#                 if token_match:
#                     self.token = token_match.group(1)
#                     return self.token
#                 raise Exception(f"Cannot parse auth response: {text[:200]}")

#             self.token = data.get("token")
#             if not self.token:
#                 raise Exception(f"No token in auth response: {data}")
#             return self.token

#     async def get_my_id(self) -> int:
#         """Отримує ID поточного Subagent"""
#         token = await self._auth()
#         session = await self._get_session()

#         url = f"{BASE_URL}/getInfo"
#         headers = {"Token": token}

#         async with session.post(url, json={}, headers=headers) as resp:
#             text = await resp.text()
#             print(f"[GETINFO] Status: {resp.status} | Content-Type: {resp.headers.get('content-type')}")
#             print(f"[GETINFO] Body: {text[:500]}")

#             if resp.status != 200:
#                 raise Exception(f"getInfo error {resp.status}: {text[:400]}")

#             # Пробуємо JSON, якщо не виходить — шукаємо id у тексті
#             try:
#                 data = await resp.json()
#                 parent_id = data.get("id") or data.get("user_id") or data.get("parentId")
#                 if parent_id:
#                     return int(parent_id)
#             except:
#                 pass

#             # Якщо не JSON — шукаємо число id
#             import re
#             id_match = re.search(r'"?id"?\s*[:=]\s*(\d+)', text)
#             if id_match:
#                 return int(id_match.group(1))

#             raise Exception(f"Cannot find ID in getInfo response: {text[:400]}")

#     async def add_codes(self, parent_id: int, count: int, amount: int) -> Dict:
#         """Додає ігрові коди (Matic)"""
#         token = await self._auth()
#         session = await self._get_session()

#         url = f"{BASE_URL}/addCodes"
#         headers = {"Token": token}

#         payload = {
#             "parentId": parent_id,
#             "count": count,
#             "amount": amount * 100
#         }

#         async with session.post(url, json=payload, headers=headers) as resp:
#             text = await resp.text()
#             print(f"[ADDCODES] Status: {resp.status} | Body: {text[:400]}")

#             if resp.status != 200:
#                 raise Exception(f"addCodes error {resp.status}: {text[:400]}")

#             try:
#                 return await resp.json()
#             except:
#                 import json
#                 try:
#                     return json.loads(text)
#                 except:
#                     return {"status": "ok", "raw": text}
                

#     async def check_code(self, code: str) -> Dict:
#         """Перевірити баланс та статус Matic чека"""
#         token = await self._auth()
#         session = await self._get_session()

#         url = f"{BASE_URL}/checkCode"
#         headers = {"Token": token}

#         payload = {"code": code}

#         async with session.post(url, json=payload, headers=headers) as resp:
#             text = await resp.text()
#             print(f"[CHECKCODE] Status: {resp.status} | Body: {text[:400]}")

#             if resp.status != 200:
#                 raise Exception(f"checkCode error: {resp.status}")

#             try:
#                 return await resp.json()
#             except:
#                 import json
#                 return json.loads(text)


#     async def close_code(self, code: str) -> Dict:
#         """Закрити Matic чек і вивести гроші на баланс"""
#         token = await self._auth()
#         session = await self._get_session()

#         url = f"{BASE_URL}/closeCode"
#         headers = {"Token": token}

#         payload = {"code": code}

#         async with session.post(url, json=payload, headers=headers) as resp:
#             text = await resp.text()
#             print(f"[CLOSECODE] Status: {resp.status} | Body: {text[:400]}")

#             if resp.status != 200:
#                 raise Exception(f"closeCode error: {resp.status}")

#             try:
#                 return await resp.json()
#             except:
#                 import json
#                 return json.loads(text)


#     async def add_to_code(self, code: str, amount: int) -> Dict:
#         """Поповнити Matic чек"""
#         token = await self._auth()
#         session = await self._get_session()

#         url = f"{BASE_URL}/addToCode"
#         headers = {"Token": token}

#         payload = {
#             "code": code,
#             "amount": amount * 100  # в копійках
#         }

#         async with session.post(url, json=payload, headers=headers) as resp:
#             text = await resp.text()
#             print(f"[ADDTOCODE] Status: {resp.status} | Body: {text[:400]}")

#             if resp.status != 200:
#                 raise Exception(f"addToCode error: {resp.status}")

#             try:
#                 return await resp.json()
#             except:
#                 import json
#                 return json.loads(text)
            

# # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

# async def get_terminal_id(self, code: str) -> int:
#     token = await self._auth()
#     session = await self._get_session()

#     async with session.post(
#         f"{BASE_URL}/getTerminalId",
#         json={"code": code},
#         headers={"Token": token}
#     ) as resp:

#         text = await resp.text()

#         if resp.status != 200:
#             raise Exception(f"getTerminalId error: {text}")

#         data = await resp.json()
#         return int(data["id"])


# async def get_terminal_balance(self, terminal_id: int) -> int:
#     token = await self._auth()
#     session = await self._get_session()

#     async with session.post(
#         f"{BASE_URL}/getBalance",
#         json={"id": terminal_id},
#         headers={"Token": token}
#     ) as resp:

#         text = await resp.text()

#         if resp.status != 200:
#             raise Exception(f"getBalance error: {text}")

#         data = await resp.json()
#         return int(data["amount"])


# async def collect_terminal(self, terminal_id: int):
#     token = await self._auth()
#     session = await self._get_session()

#     async with session.post(
#         f"{BASE_URL}/collectTerminal",
#         json={
#             "id": terminal_id,
#             "force": True
#         },
#         headers={"Token": token}
#     ) as resp:

#         text = await resp.text()

#         if resp.status != 200:
#             raise Exception(f"collectTerminal error: {text}")

#         return await resp.json()


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

    async def check_code(self, code: str) -> Dict:
        """Перевірити баланс та статус Matic чека"""
        token = await self._auth()
        session = await self._get_session()

        url = f"{BASE_URL}/checkCode"
        headers = {"Token": token}

        payload = {"code": code}

        async with session.post(url, json=payload, headers=headers) as resp:
            text = await resp.text()
            print(f"[CHECKCODE] Status: {resp.status} | Body: {text[:400]}")

            if resp.status != 200:
                raise Exception(f"checkCode error: {resp.status}")

            try:
                return await resp.json()
            except:
                import json
                return json.loads(text)

    async def close_code(self, code: str) -> Dict:
        """Закрити Matic чек і вивести гроші на баланс"""
        token = await self._auth()
        session = await self._get_session()

        url = f"{BASE_URL}/closeCode"
        headers = {"Token": token}

        payload = {"code": code}

        async with session.post(url, json=payload, headers=headers) as resp:
            text = await resp.text()
            print(f"[CLOSECODE] Status: {resp.status} | Body: {text[:400]}")

            if resp.status != 200:
                raise Exception(f"closeCode error: {resp.status}")

            try:
                return await resp.json()
            except:
                import json
                return json.loads(text)

    async def add_to_code(self, code: str, amount: int) -> Dict:
        """Поповнити Matic чек"""
        token = await self._auth()
        session = await self._get_session()

        url = f"{BASE_URL}/addToCode"
        headers = {"Token": token}

        payload = {
            "code": code,
            "amount": amount * 100  # в копійках
        }

        async with session.post(url, json=payload, headers=headers) as resp:
            text = await resp.text()
            print(f"[ADDTOCODE] Status: {resp.status} | Body: {text[:400]}")

            if resp.status != 200:
                raise Exception(f"addToCode error: {resp.status}")

            try:
                return await resp.json()
            except:
                import json
                return json.loads(text)

    # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    async def get_terminal_id(self, code: str) -> int:
        """Отримує ID терміналу за кодом (працює добре, як бачимо в логах)"""
        token = await self._auth()
        session = await self._get_session()

        async with session.post(
            f"{BASE_URL}/getTerminalId",
            json={"code": code},
            headers={"Token": token}
        ) as resp:
            text = await resp.text()
            print(f"[GETTERMINALID] Status: {resp.status} | Body: {text[:400]}")

            if resp.status != 200:
                raise Exception(f"getTerminalId error {resp.status}: {text[:400]}")

            data = self._parse_json(text)
            terminal_id = data.get("id") or data.get("terminalId") or data.get("terminal_id")
            if terminal_id is None:
                raise Exception(f"Terminal ID not found for code {code}")
            return int(terminal_id)

    async def get_terminal_balance(self, terminal_id: int) -> int:
        """Новий правильний спосіб отримання балансу терміналу"""
        token = await self._auth()
        session = await self._get_session()

        # Спроба 1: Через getTerminalLog або інший ендпоінт, але краще — checkCode
        # Багато хто використовує checkCode для балансу терміналів/кодів

        try:
            # Кращий варіант для Matic кодів — checkCode
            result = await self.check_code(str(terminal_id) if isinstance(terminal_id, int) else terminal_id)
            balance = result.get("balance") or result.get("amount") or 0
            return int(balance)
        except:
            pass

        # Фолбек — спроба через getBalance (якщо terminal_id можна використовувати як account)
        async with session.post(
            f"{BASE_URL}/getBalance",
            json={"id": terminal_id},
            headers={"Token": token}
        ) as resp:
            text = await resp.text()
            print(f"[GETBALANCE] Status: {resp.status} | Body: {text[:400]}")

            if resp.status == 200:
                data = self._parse_json(text)
                return int(data.get("amount") or data.get("balance") or 0)

            raise Exception(f"getBalance error {resp.status}: {text[:400]}")

    async def collect_terminal(self, terminal_id: int):
        token = await self._auth()
        session = await self._get_session()

        async with session.post(
            f"{BASE_URL}/collectTerminal",
            json={
                "id": terminal_id,
                "force": True
            },
            headers={"Token": token}
        ) as resp:

            text = await resp.text()
            print(f"[COLLECTTERMINAL] Status: {resp.status} | Content-Type: {resp.headers.get('content-type')}")
            print(f"[COLLECTTERMINAL] Body: {text[:400]}")

            if resp.status != 200:
                raise Exception(f"collectTerminal error {resp.status}: {text[:400]}")

            return self._parse_json(text)

    @staticmethod
    def _parse_json(text: str) -> Dict:
        """Парсить JSON з тіла відповіді незалежно від Content-Type заголовка.

        aiohttp's resp.json() кидає ContentTypeError, якщо сервер повертає
        тіло у форматі JSON, але з невідповідним Content-Type (text/plain,
        порожній заголовок тощо). Тому парсимо текст напряму.
        """
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
        

    async def delete_code(self, code: str) -> Dict:
        """Видалити Matic код після закриття"""
        token = await self._auth()
        session = await self._get_session()

        url = f"{BASE_URL}/deleteCode"
        headers = {"Token": token}

        payload = {"code": code}   # або "id", якщо API вимагає id

        async with session.post(url, json=payload, headers=headers) as resp:
            text = await resp.text()
            print(f"[DELETECODE] Status: {resp.status} | Body: {text[:400]}")

            if resp.status != 200:
                raise Exception(f"deleteCode error: {resp.status} - {text[:300]}")

            try:
                return await resp.json()
            except:
                import json
                return json.loads(text) if text.strip() else {"status": "ok"}

    async def collect_to_bot_balance(self, terminal_id: int = None, code: str = None):
        """Збирає гроші з терміналу на баланс субагента (бота)"""
        if code:
            try:
                terminal_id = await self.get_terminal_id(code)
            except:
                pass

        if not terminal_id:
            return {"success": False, "error": "No terminal_id"}

        return await self.collect_terminal(terminal_id)
    
    async def get_terminal_balance(self, terminal_id: int) -> int:
        """Правильне отримання балансу терміналу"""
        token = await self._auth()
        session = await self._get_session()

        async with session.post(
            f"{BASE_URL}/getBalanceTerminal",
            json={"id": terminal_id},
            headers={"Token": token}
        ) as resp:
            text = await resp.text()
            print(f"[GETBALANCETERMINAL] Status: {resp.status} | Body: {text[:500]}")

            if resp.status != 200:
                raise Exception(f"getBalanceTerminal error {resp.status}: {text[:400]}")

            data = self._parse_json(text)
            amount = data.get("amount") or data.get("balance") or 0
            return int(amount)   # повертаємо в копійках!