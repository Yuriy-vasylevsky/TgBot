# states.py
from aiogram.fsm.state import StatesGroup, State


class WinrateFSM(StatesGroup):
    waiting_for_value = State()


class Broadcast(StatesGroup):
    waiting_for_text = State()


class PromoFSM(StatesGroup):
    waiting_for_code = State()


class EnterPromoFSM(StatesGroup):
    waiting_for_code = State()


class CodeLinkFSM(StatesGroup):
    waiting_for_code = State()


# БАН ________________________________
class BanStates(StatesGroup):
    waiting_for_id = State()
    waiting_for_unban_id = State()
