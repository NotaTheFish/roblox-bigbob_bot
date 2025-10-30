from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def payment_methods_kb():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("🇷🇺 RUB", callback_data="pay_rub"),
        InlineKeyboardButton("🇺🇦 UAH", callback_data="pay_uah"),
        InlineKeyboardButton("💳 Crypto", callback_data="pay_crypto"),
        InlineKeyboardButton("🇪🇺 EUR", callback_data="pay_eur"),
        InlineKeyboardButton("❌ Отмена", callback_data="pay_cancel"),
    )
    return kb
