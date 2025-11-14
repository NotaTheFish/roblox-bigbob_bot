"""Inline keyboard for leaderboard-related actions."""
from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


TOP_MENU_CALLBACK_PREFIX = "top_menu"


def top_players_keyboard() -> InlineKeyboardMarkup:
    """Return keyboard with leaderboard actions."""

    builder = InlineKeyboardBuilder()
    builder.button(text="🏅 Топ-15", callback_data=f"{TOP_MENU_CALLBACK_PREFIX}:top15")
    builder.button(
        text="🔍 Поиск игрока по нику",
        callback_data=f"{TOP_MENU_CALLBACK_PREFIX}:search",
    )
    builder.button(text="⬅️ Назад", callback_data=f"{TOP_MENU_CALLBACK_PREFIX}:back")
    builder.adjust(1)
    return builder.as_markup()


__all__ = ["TOP_MENU_CALLBACK_PREFIX", "top_players_keyboard"]