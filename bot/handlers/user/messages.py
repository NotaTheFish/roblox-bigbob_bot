"""Message handler for secret word achievements."""

from aiogram import Router, types
from sqlalchemy import select

from bot.db import Achievement, User, async_session
from backend.services.achievements import evaluate_and_grant_achievements

router = Router(name="user_messages")


async def _matches_secret_word(message: types.Message) -> bool:
    """Check whether the incoming message matches a secret word condition."""

    if not message.from_user:
        return False

    text = (message.text or "").strip()
    if not text:
        return False

    async with async_session() as session:
        secret_words = await session.scalars(
            select(Achievement.condition_value).where(Achievement.condition_type == "secret_word")
        )

        lowered_text = text.lower()
        for value in secret_words:
            if isinstance(value, str) and lowered_text == value.strip().lower():
                return True

    return False


@router.message(_matches_secret_word)
async def handle_secret_word_message(message: types.Message) -> None:
    """Grant achievements when the message matches a configured secret word."""

    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == message.from_user.id))
        if not user:
            return

        await evaluate_and_grant_achievements(
            session,
            user=user,
            trigger="secret_word",
            payload={"message_id": message.message_id, "text": message.text or ""},
        )

        await session.commit()