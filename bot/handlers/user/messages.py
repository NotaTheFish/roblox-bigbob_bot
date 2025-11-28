"""Message handler for secret word achievements."""

import logging
import time
import unicodedata

from aiogram import F, Router, types
from aiogram.filters import StateFilter
from sqlalchemy import select

from bot import config
from bot.db import Achievement, Admin, User, async_session
from backend.services.achievements import evaluate_and_grant_achievements
from bot.services.reply_keyboard import (
    send_main_menu_keyboard,
    was_reply_keyboard_removed,
)

router = Router(name="user_messages")
logger = logging.getLogger(__name__)

last_secret_word_use: dict[int, float] = {}


def _normalize_text(text: str) -> str:
    """Normalize text for comparison using Unicode NFC and casefolding."""

    return unicodedata.normalize("NFC", text).casefold().strip()


async def _matches_secret_word(message: types.Message) -> bool:
    """Check whether the incoming message matches a secret word condition."""

    if not message.from_user:
        return False

    if getattr(message, "is_service", False):
        return False

    if message.content_type != types.ContentType.TEXT:
        return False

    if message.text is None:
        return False

    if message.text.startswith("/"):
        return False

    if _should_throttle_secret_word(message.from_user.id):
        logging.info("Secret word throttle: user %s attempted too fast", message.from_user.id)
        return False

    normalized_text = _normalize_text(message.text)
    if not normalized_text:
        return False

    async with async_session() as session:
        is_admin = await session.scalar(
            select(Admin.telegram_id).where(Admin.telegram_id == message.from_user.id)
        )
        if is_admin:
            return False

        secret_words = (
            await session.scalars(
                select(Achievement.condition_value).where(Achievement.condition_type == "secret_word")
            )
        ).all()

        compared_values = []
        for value in secret_words:
            if not isinstance(value, str):
                continue

            normalized_value = _normalize_text(value)
            compared_values.append(normalized_value)

            if normalized_text == normalized_value:
                logging.info(
                    "Secret word match for user %s: user_text=%r matched_value=%r",
                    message.from_user.id,
                    normalized_text,
                    normalized_value,
                )
                return True

    logging.info(
        "No secret word match for user %s: user_text=%r compared_values=%r",
        message.from_user.id,
        normalized_text,
        compared_values,
    )

    return False


def _should_throttle_secret_word(user_id: int, *, now: float | None = None) -> bool:
    """Return True when the user has triggered the secret word too recently."""

    current_time = time.monotonic() if now is None else now
    last_time = last_secret_word_use.get(user_id)

    if last_time is not None and current_time - last_time < config.SECRET_WORD_THROTTLE_SECONDS:
        return True

    last_secret_word_use[user_id] = current_time
    return False


@router.message(StateFilter(None), _matches_secret_word)
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


@router.message(StateFilter(None), F.text)
async def restore_reply_keyboard_on_plain_text(message: types.Message) -> None:
    """Restore the main menu keyboard when it was previously removed."""

    if not message.from_user:
        return

    user_id = message.from_user.id
    if not was_reply_keyboard_removed(user_id):
        return

    async with async_session() as session:
        restored = await send_main_menu_keyboard(
            message.bot,
            user_id,
            session=session,
            reason="plain_text_without_state",
        )

        if not restored:
            logger.info(
                "Keyboard restore skipped for user %s because user record is missing",
                user_id,
            )
