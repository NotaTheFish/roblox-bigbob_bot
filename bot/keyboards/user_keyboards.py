from typing import Mapping

from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.constants.stars import STARS_PACKAGES


def stars_packages_kb():
    builder = InlineKeyboardBuilder()
    for package in STARS_PACKAGES:
        builder.button(text=package.button_text, callback_data=f"stars_pack:{package.code}")
    builder.button(text="❌ Отмена", callback_data="pay_cancel")
    builder.adjust(1)
    return builder.as_markup()


def ton_packages_kb(display_amounts: Mapping[str, str]):
    builder = InlineKeyboardBuilder()
    for package in STARS_PACKAGES:
        suffix = display_amounts.get(package.code)
        title = f"{package.title} — {suffix}" if suffix else package.title
        builder.button(text=title, callback_data=f"ton_pack:{package.code}")
    builder.button(text="❌ Отмена", callback_data="pay_cancel")
    builder.adjust(1)
    return builder.as_markup()


def topup_method_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="💫 Telegram Stars", callback_data="topup:stars")
    builder.button(text="⚡ TON через @wallet", callback_data="topup:ton")
    builder.button(text="❌ Отмена", callback_data="pay_cancel")
    builder.adjust(1)
    return builder.as_markup()
