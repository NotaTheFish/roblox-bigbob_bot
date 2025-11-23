from aiogram.fsm.state import State, StatesGroup


class TopUpState(StatesGroup):
    choosing_method = State()
    waiting_for_package = State()
    waiting_for_ton_package = State()


class SupportRequestState(StatesGroup):
    waiting_for_message = State()


class BanAppealState(StatesGroup):
    waiting_for_message = State()


class PromoInputState(StatesGroup):
    waiting_for_code = State()


class ProfileEditState(StatesGroup):
    choosing_action = State()
    editing_about = State()
    editing_nickname = State()
    choosing_title = State()
    choosing_achievement = State()


class UserSearchState(StatesGroup):
    waiting_for_query = State()