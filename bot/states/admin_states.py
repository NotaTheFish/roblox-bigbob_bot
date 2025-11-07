from aiogram.fsm.state import State, StatesGroup


class GiveMoneyState(StatesGroup):
    waiting_for_amount = State()


class AdminUsersState(StatesGroup):
    searching = State()


class AchievementsState(StatesGroup):
    waiting_for_name = State()
    waiting_for_description = State()
    waiting_for_reward = State()


class SupportReplyState(StatesGroup):
    waiting_for_message = State()


class AdminLoginState(StatesGroup):
    waiting_for_code = State()