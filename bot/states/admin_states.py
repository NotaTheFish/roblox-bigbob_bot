from aiogram.dispatcher.filters.state import State, StatesGroup

class GiveMoneyState(StatesGroup):
    waiting_for_amount = State()
