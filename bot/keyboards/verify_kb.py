from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def verify_button():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("✅ Верифицироваться", callback_data="start_verify"))
    return kb

def verify_check_button():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🔍 Проверить", callback_data="check_verify"))
    kb.add(InlineKeyboardButton("❌ Отмена", callback_data="cancel_verify"))
    return kb
