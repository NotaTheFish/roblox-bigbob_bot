"""Helpers for building reusable profile text blocks."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from html import escape
from typing import Sequence


@dataclass(frozen=True)
class ProfileView:
    """Structured data for rendering a profile card."""

    heading: str
    tg_username: str | None = None
    tg_id: int | None = None
    roblox_username: str | None = None
    roblox_id: str | None = None
    balance: int | None = None
    titles: Sequence[str] = ()
    selected_title: str | None = None
    selected_achievement: str | None = None
    about_text: str | None = None
    created_at: datetime | None = None


def render_profile(view: ProfileView) -> str:
    """Return an HTML-formatted profile card."""

    def _format(value: str | None) -> str:
        return escape(value) if value else "—"

    lines: list[str] = [view.heading]

    if view.tg_username is not None:
        lines.append(f"TG: {_format(view.tg_username)}")
    if view.tg_id is not None:
        lines.append(f"TG ID: <code>{view.tg_id}</code>")
    if view.roblox_username is not None:
        lines.append(f"Roblox: <code>{_format(view.roblox_username)}</code>")
    if view.roblox_id is not None:
        lines.append(f"Roblox ID: <code>{_format(view.roblox_id)}</code>")
    if view.balance is not None:
        lines.append(f"Баланс: 💰 {view.balance}")

    titles_line = ", ".join(escape(title) for title in view.titles if title) or "—"
    lines.append(f"Титулы: {titles_line}")
    selected_title = escape(view.selected_title) if view.selected_title else "—"
    lines.append(f"Активный титул: {selected_title}")

    achievement = (
        escape(view.selected_achievement)
        if view.selected_achievement
        else "—"
    )
    lines.append(f"Выбранное достижение: {achievement}")

    about_value = (
        escape(view.about_text).replace("\n", "<br>")
        if view.about_text
        else "—"
    )
    lines.append(f"О себе: {about_value}")

    if view.created_at is not None:
        created_str = view.created_at.strftime("%d.%m.%Y %H:%M")
        lines.append(f"Дата регистрации: {created_str}")

    return "\n".join(lines)


__all__ = ["ProfileView", "render_profile"]