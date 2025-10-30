from aiogram.dispatcher.filters.state import State, StatesGroup

class VerifyState(StatesGroup):
    waiting_for_username = State()
    waiting_for_check = State()
