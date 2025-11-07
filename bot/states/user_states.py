from aiogram.fsm.state import State, StatesGroup


class TopUpState(StatesGroup):
    waiting_for_method = State()
    waiting_for_amount = State()


class SupportRequestState(StatesGroup):
    waiting_for_message = State()


class PromoInputState(StatesGroup):
    waiting_for_code = State()