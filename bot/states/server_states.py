from aiogram.fsm.state import State, StatesGroup


class ServerManageState(StatesGroup):
    menu = State()
    navigation = State()
    waiting_for_server = State()
    waiting_for_link = State()
    waiting_for_closed_message = State()