from __future__ import annotations

from aiogram import Router, types
from aiogram.enums import ContentType
from aiogram.filters import Filter
from sqlalchemy import select

from bot.db import Admin, async_session

router = Router(name="attachment_blocker")

SERVICE_CONTENT_TYPES: tuple[ContentType, ...] = (
    ContentType.NEW_CHAT_MEMBERS,
    ContentType.LEFT_CHAT_MEMBER,
    ContentType.NEW_CHAT_TITLE,
    ContentType.NEW_CHAT_PHOTO,
    ContentType.DELETE_CHAT_PHOTO,
    ContentType.GROUP_CHAT_CREATED,
    ContentType.SUPERGROUP_CHAT_CREATED,
    ContentType.CHANNEL_CHAT_CREATED,
    ContentType.MESSAGE_AUTO_DELETE_TIMER_CHANGED,
    ContentType.MIGRATE_TO_CHAT_ID,
    ContentType.MIGRATE_FROM_CHAT_ID,
    ContentType.PINNED_MESSAGE,
    ContentType.CONNECTED_WEBSITE,
    ContentType.WRITE_ACCESS_ALLOWED,
    ContentType.PROXIMITY_ALERT_TRIGGERED,
    ContentType.VIDEO_CHAT_SCHEDULED,
    ContentType.VIDEO_CHAT_STARTED,
    ContentType.VIDEO_CHAT_ENDED,
    ContentType.VIDEO_CHAT_PARTICIPANTS_INVITED,
    ContentType.FORUM_TOPIC_CREATED,
    ContentType.FORUM_TOPIC_EDITED,
    ContentType.FORUM_TOPIC_CLOSED,
    ContentType.FORUM_TOPIC_REOPENED,
    ContentType.GENERAL_FORUM_TOPIC_HIDDEN,
    ContentType.GENERAL_FORUM_TOPIC_UNHIDDEN,
    ContentType.GIVEAWAY_CREATED,
    ContentType.GIVEAWAY_COMPLETED,
    ContentType.GIVEAWAY,
    ContentType.GIVEAWAY_WINNERS,
    ContentType.SUGGESTED_POST_APPROVED,
    ContentType.SUGGESTED_POST_APPROVAL_FAILED,
    ContentType.SUGGESTED_POST_DECLINED,
    ContentType.SUGGESTED_POST_PAID,
    ContentType.SUGGESTED_POST_REFUNDED,
    ContentType.CHECKLIST_TASKS_ADDED,
    ContentType.CHECKLIST_TASKS_DONE,
    ContentType.CHECKLIST,
    ContentType.DIRECT_MESSAGE_PRICE_CHANGED,
    ContentType.PAID_MESSAGE_PRICE_CHANGED,
)


async def _is_admin(tg_id: int, data: dict | None = None) -> bool:
    session = data.get("session") if data else None
    if session:
        return bool(await session.scalar(select(Admin).where(Admin.telegram_id == tg_id)))

    async with async_session() as new_session:
        return bool(await new_session.scalar(select(Admin).where(Admin.telegram_id == tg_id)))


class AttachmentBlockerFilter(Filter):
    """Filter that catches non-text messages from non-admin users."""

    async def __call__(self, event: types.TelegramObject, **data) -> bool:
        if not isinstance(event, types.Message):
            return False

        if event.text:
            return False

        if not event.from_user:
            return False

        if event.content_type in SERVICE_CONTENT_TYPES:
            return False

        if await _is_admin(event.from_user.id, data):
            return False

        return True


@router.message(AttachmentBlockerFilter())
async def block_attachments(message: types.Message) -> None:
    await message.answer("❌ Файлы и вложения не принимаются. Введите текстовое сообщение.")


__all__ = ["router", "AttachmentBlockerFilter"]