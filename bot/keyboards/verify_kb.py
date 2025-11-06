from aiogram.utils.keyboard import InlineKeyboardBuilder


def verify_button():
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Верифицироваться", callback_data="start_verify")
    builder.adjust(1)
    return builder.as_markup()

def verify_check_button():
    builder = InlineKeyboardBuilder()
    builder.button(text="🔍 Проверить", callback_data="check_verify")
    builder.button(text="❌ Отмена", callback_data="cancel_verify")
    builder.adjust(1)
    return builder.as_markup()
