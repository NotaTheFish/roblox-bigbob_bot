from aiogram.utils.keyboard import InlineKeyboardBuilder


def payment_methods_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="🇷🇺 RUB", callback_data="pay_rub")
    builder.button(text="🇺🇦 UAH", callback_data="pay_uah")
    builder.button(text="💳 Crypto", callback_data="pay_crypto")
    builder.button(text="🇪🇺 EUR", callback_data="pay_eur")
    builder.button(text="❌ Отмена", callback_data="pay_cancel")
    builder.adjust(2)
    return builder.as_markup()
