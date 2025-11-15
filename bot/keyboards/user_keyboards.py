from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.constants.stars import STARS_PACKAGES


def stars_packages_kb():
    builder = InlineKeyboardBuilder()
    for package in STARS_PACKAGES:
        builder.button(text=package.button_text, callback_data=f"stars_pack:{package.code}")
    builder.button(text="❌ Отмена", callback_data="pay_cancel")
    builder.adjust(1)
    return builder.as_markup()
