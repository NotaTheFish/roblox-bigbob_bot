from aiogram.fsm.state import State, StatesGroup

class ShopCreateState(StatesGroup):
    waiting_for_name = State()
    waiting_for_type = State()
    waiting_for_value = State()
    waiting_for_price = State()
    waiting_for_limit = State()
    waiting_for_referral_bonus = State()
