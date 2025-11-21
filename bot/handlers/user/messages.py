"""General message tracker for user achievements."""

from aiogram import F, Router, types
from aiogram.filters import Command, StateFilter
from sqlalchemy import select

from bot.db import LogEntry, User, async_session
from backend.services.achievements import evaluate_and_grant_achievements
from .promocode_use import PROMOCODE_PATTERN


router = Router(name="user_messages")


@router.message(
    StateFilter(None),
    F.text,
    ~F.text.startswith("/"),
    ~F.text.regexp(PROMOCODE_PATTERN),
)
async def record_user_message(message: types.Message) -> None:
    """Record a user's free-form message and trigger achievement evaluation."""

    if not message.from_user:
        return

    text = (message.text or "").strip()
    if not text:
        return

    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == message.from_user.id))
        if not user:
            return

        has_marker = await session.scalar(
            select(LogEntry.id)
            .where(
                LogEntry.user_id == user.id,
                LogEntry.event_type == "user_message_seen",
            )
            .limit(1)
        )

        log_added = False
        if not has_marker:
            session.add(
                LogEntry(
                    user_id=user.id,
                    telegram_id=user.tg_id,
                    event_type="user_message_seen",
                    message="Первое пользовательское сообщение",
                    data={"message_id": message.message_id},
                )
            )
            log_added = True

        granted = await evaluate_and_grant_achievements(
            session,
            user=user,
            trigger="user_message",
            payload={"message_id": message.message_id},
        )

        if log_added or granted:
            await session.commit()