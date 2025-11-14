from aiogram.fsm.state import State, StatesGroup

class PromoCreateState(StatesGroup):
    waiting_for_reward_type = State()
    waiting_for_reward_value = State()
    waiting_for_usage_limit = State()
    waiting_for_expire_days = State()
    waiting_for_code = State()
