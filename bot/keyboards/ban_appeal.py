"""Inline keyboard helpers for ban appeals."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

BAN_APPEAL_CALLBACK = "appeal_ban"


def ban_appeal_keyboard() -> InlineKeyboardMarkup:
    """Return a keyboard with a single "Обжаловать бан" button."""

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Обжаловать бан", callback_data=BAN_APPEAL_CALLBACK)]
        ]
    )


__all__ = ["BAN_APPEAL_CALLBACK", "ban_appeal_keyboard"]