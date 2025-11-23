"""Tools for querying and formatting admin log entries."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Mapping, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db import LogEntry, async_session


DEFAULT_LOGS_RANGE_HOURS = 24
LOGS_BATCH_SIZE = 20


class LogCategory(str, Enum):
    """Available log buckets shown to administrators."""

    TOPUPS = "topups"
    ACHIEVEMENTS = "achievements"
    PURCHASES = "purchases"
    PROMOCODES = "promocodes"
    ADMIN_ACTIONS = "admin"


_CATEGORY_EVENT_TYPES: Mapping[LogCategory, Sequence[str]] = {
    LogCategory.TOPUPS: ("payment_received", "payment_applied"),
    LogCategory.ACHIEVEMENTS: ("achievement_granted", "achievement_manual_granted"),
    LogCategory.PURCHASES: ("purchase_created",),
    LogCategory.PROMOCODES: ("promocode_redeemed",),
    LogCategory.ADMIN_ACTIONS: (
        "admin_demoted",
        "product_created",
        "product_deleted",
        "server_created",
        "server_deleted",
        "server_link_removed",
        "server_link_updated",
        "support_reply",
        "support_close",
    ),
}


@dataclass(slots=True, frozen=True)
class LogQuery:
    """Represents a log selection request."""

    category: LogCategory
    page: int = 1
    offset: int = 0
    start_at: datetime | None = None
    end_at: datetime | None = None
    user_id: int | None = None
    telegram_id: int | None = None


@dataclass(slots=True, frozen=True)
class LogRecord:
    """Lightweight view of a log entry suitable for rendering."""

    id: int
    created_at: datetime
    event_type: str
    message: str | None
    telegram_id: int | None
    user_id: int | None
    data: Mapping[str, object] | None


@dataclass(slots=True, frozen=True)
class LogPage:
    """A single page of log records with pagination hints."""

    entries: Sequence[LogRecord]
    page: int
    offset: int
    next_offset: int | None
    has_prev: bool


@dataclass(slots=True, frozen=True)
class LogBatch:
    """A batch of log records loaded from the database."""

    entries: Sequence[LogRecord]
    offset: int
    next_offset: int | None


class LogsRepository:
    """Repository encapsulating LogEntry queries."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def fetch(self, query: LogQuery) -> LogBatch:
        normalized_offset = max(0, query.offset)
        end_at = query.end_at or datetime.now(tz=timezone.utc)
        start_at = query.start_at or end_at - timedelta(hours=DEFAULT_LOGS_RANGE_HOURS)

        stmt = (
            select(LogEntry)
            .where(LogEntry.created_at >= start_at)
            .where(LogEntry.created_at <= end_at)
        )

        event_types = tuple(_CATEGORY_EVENT_TYPES.get(query.category, ()))
        if event_types:
            stmt = stmt.where(LogEntry.event_type.in_(event_types))

        if query.user_id is not None:
            stmt = stmt.where(LogEntry.user_id == query.user_id)
        if query.telegram_id is not None:
            stmt = stmt.where(LogEntry.telegram_id == query.telegram_id)

        stmt = stmt.order_by(LogEntry.created_at.desc())
        stmt = stmt.offset(normalized_offset).limit(LOGS_BATCH_SIZE + 1)

        result = await self._session.scalars(stmt)
        rows = list(result.all())

        has_more = len(rows) > LOGS_BATCH_SIZE
        if has_more:
            rows = rows[:LOGS_BATCH_SIZE]

        records = [
            LogRecord(
                id=row.id,
                created_at=row.created_at,
                event_type=row.event_type,
                message=row.message,
                telegram_id=row.telegram_id,
                user_id=row.user_id,
                data=row.data,
            )
            for row in rows
        ]

        next_offset = normalized_offset + len(records) if has_more else None

        return LogBatch(entries=records, offset=normalized_offset, next_offset=next_offset)


async def fetch_logs_page(query: LogQuery) -> LogBatch:
    """Fetch a batch of logs using the shared async session factory."""

    async with async_session() as session:
        repository = LogsRepository(session)
        return await repository.fetch(query)


__all__ = [
    "DEFAULT_LOGS_RANGE_HOURS",
    "LOGS_BATCH_SIZE",
    "LogBatch",
    "LogCategory",
    "LogPage",
    "LogQuery",
    "LogRecord",
    "LogsRepository",
    "fetch_logs_page",
]