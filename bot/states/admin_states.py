from aiogram.fsm.state import State, StatesGroup


class GiveMoneyState(StatesGroup):
    waiting_for_amount = State()


class RemoveMoneyState(StatesGroup):
    waiting_for_amount = State()
    waiting_for_reason = State()


class GiveTitleState(StatesGroup):
    waiting_for_title = State()


class RemoveTitleState(StatesGroup):
    choosing_title = State()
    confirming = State()


class AdminUsersState(StatesGroup):
    searching = State()
    banlist = State()
    banlist_search = State()
    viewing_user = State()
    broadcasting = State()


class AdminLogsState(StatesGroup):
    browsing = State()
    waiting_for_query = State()
    waiting_for_admin = State()


class AchievementsState(StatesGroup):
    waiting_for_name = State()
    waiting_for_description = State()
    waiting_for_reward = State()
    waiting_for_condition_type = State()
    waiting_for_condition_value = State()
    waiting_for_condition_threshold = State()
    waiting_for_visibility = State()
    manual_grant_user = State()
    manual_grant_achievement = State()
    manual_grant_comment = State()


class SupportReplyState(StatesGroup):
    waiting_for_message = State()


class AdminLoginState(StatesGroup):
    waiting_for_code = State()