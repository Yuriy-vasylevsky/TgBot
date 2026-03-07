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


# ======================
# СТАНИ
# ======================
class AddCodeFSM(StatesGroup):
    waiting_for_code = State()


class CodeLinkFSM(StatesGroup):
    waiting_for_code = State()


# FSM для додавання коду
class AddCodeFSM(StatesGroup):
    waiting_for_type = State()
    waiting_for_code = State()