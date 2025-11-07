from aiogram.fsm.state import State, StatesGroup


class ServerCreateState(StatesGroup):
    waiting_for_name = State()
    waiting_for_slug = State()
    waiting_for_link = State()
    waiting_for_chat_id = State()