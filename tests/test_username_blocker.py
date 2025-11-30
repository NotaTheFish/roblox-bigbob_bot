import pytest

from datetime import datetime, timedelta, timezone

from bot.constants.users import DEFAULT_TG_USERNAME
from bot.db import LogEntry, User
from bot.services import username_blocker
from tests.conftest import FakeAsyncSession


@pytest.mark.anyio
async def test_blocks_only_after_timeout(monkeypatch):
    now = datetime(2024, 1, 1, tzinfo=timezone.utc)
    eligible = User(
        id=1,
        tg_id=111,
        tg_username=DEFAULT_TG_USERNAME,
        verified=False,
        created_at=now - timedelta(hours=3),
    )
    too_new = User(
        id=2,
        tg_id=222,
        tg_username=DEFAULT_TG_USERNAME,
        verified=False,
        created_at=now - timedelta(minutes=30),
    )
    verified = User(
        id=3,
        tg_id=333,
        tg_username=DEFAULT_TG_USERNAME,
        verified=True,
        created_at=now - timedelta(hours=5),
    )
    other_username = User(
        id=4,
        tg_id=444,
        tg_username="other",
        verified=False,
        created_at=now - timedelta(hours=5),
    )

    session = FakeAsyncSession(scalars_results=[[eligible, too_new, verified, other_username]])
    blocked: list[tuple[int, str | None]] = []

    async def fake_block_user(
        session_obj,
        *,
        user,
        operator_admin,
        confirmed=False,
        duration=None,
        reason=None,
        interface=None,
        operator_username=None,
    ):
        blocked.append((user.id, reason))
        user.is_blocked = True

    monkeypatch.setattr(username_blocker, "block_user", fake_block_user)

    blocked_count = await username_blocker.enforce_missing_username_block(session, now=now)

    assert blocked_count == 1
    assert blocked == [(eligible.id, username_blocker.MISSING_USERNAME_REASON)]
    assert len(session.added) == 1

    log_entry = session.added[0]
    assert isinstance(log_entry, LogEntry)
    assert log_entry.event_type == username_blocker.MISSING_USERNAME_EVENT
    assert log_entry.telegram_id == eligible.tg_id
    assert log_entry.user_id == eligible.id


@pytest.mark.anyio
async def test_repeated_blocks(monkeypatch):
    now = datetime(2024, 1, 1, tzinfo=timezone.utc)
    user = User(
        id=5,
        tg_id=555,
        tg_username=DEFAULT_TG_USERNAME,
        verified=False,
        created_at=now - timedelta(hours=4),
    )

    existing_log = LogEntry(
        event_type=username_blocker.MISSING_USERNAME_EVENT,
        user_id=user.id,
        created_at=now,
    )

    session = FakeAsyncSession(
        scalars_results=[[user], [user]],
        scalar_results=[None, None, None, existing_log],
    )
    blocked_reasons: list[str | None] = []

    async def fake_block_user(
        session_obj,
        *,
        user,
        operator_admin,
        confirmed=False,
        duration=None,
        reason=None,
        interface=None,
        operator_username=None,
    ):
        blocked_reasons.append(reason)
        user.is_blocked = True

    monkeypatch.setattr(username_blocker, "block_user", fake_block_user)

    await username_blocker.enforce_missing_username_block(session, now=now)
    user.is_blocked = False
    user.block_reason = None

    await username_blocker.enforce_missing_username_block(
        session, now=now + timedelta(minutes=5)
    )

    assert blocked_reasons == [
        username_blocker.MISSING_USERNAME_REASON,
        username_blocker.MISSING_USERNAME_REASON,
    ]
    assert len(session.added) == 1


@pytest.mark.anyio
async def test_skips_already_blocked_users(monkeypatch):
    now = datetime(2024, 1, 1, tzinfo=timezone.utc)
    blocked_user = User(
        id=6,
        tg_id=666,
        tg_username=DEFAULT_TG_USERNAME,
        verified=False,
        created_at=now - timedelta(hours=3),
        is_blocked=True,
    )

    session = FakeAsyncSession(scalars_results=[[blocked_user]])
    blocked_reasons: list[str | None] = []

    async def fake_block_user(*_args, **kwargs):
        blocked_reasons.append(kwargs.get("reason"))

    monkeypatch.setattr(username_blocker, "block_user", fake_block_user)

    blocked_count = await username_blocker.enforce_missing_username_block(
        session, now=now
    )

    assert blocked_count == 0
    assert blocked_reasons == []
    assert session.added == []


@pytest.mark.anyio
async def test_deduplicates_existing_missing_username_logs(monkeypatch):
    now = datetime(2024, 1, 1, tzinfo=timezone.utc)
    user = User(
        id=7,
        tg_id=777,
        tg_username=DEFAULT_TG_USERNAME,
        verified=False,
        created_at=now - timedelta(hours=3),
    )

    recent_log = LogEntry(
        event_type=username_blocker.MISSING_USERNAME_EVENT,
        user_id=user.id,
        created_at=now - timedelta(minutes=10),
    )

    session = FakeAsyncSession(
        scalars_results=[[user]],
        scalar_results=[None, recent_log],
    )

    blocked_reasons: list[str | None] = []

    async def fake_block_user(*_args, **kwargs):
        blocked_reasons.append(kwargs.get("reason"))
        user.is_blocked = True

    monkeypatch.setattr(username_blocker, "block_user", fake_block_user)

    blocked_count = await username_blocker.enforce_missing_username_block(
        session, now=now
    )

    assert blocked_count == 1
    assert blocked_reasons == [username_blocker.MISSING_USERNAME_REASON]
    assert session.added == []
