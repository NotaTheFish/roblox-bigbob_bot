from aiogram.fsm.state import State, StatesGroup

class TopUpState(StatesGroup):
    waiting_for_method = State()
    waiting_for_amount = State()
