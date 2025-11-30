import pytest

from bot.middleware.banned import BannedMiddleware
from bot.services.user_blocking import block_user, unblock_user
from db.models import Admin, BannedRobloxAccount, LogEntry, User
from tests.conftest import FakeAsyncSession


@pytest.mark.anyio
async def test_block_user_logs_security_entry():
    user = User(id=1, tg_id=123, username="blocked_user", roblox_id="42")
    admin = Admin(id=10, telegram_id=999, is_root=True)
    session = FakeAsyncSession(scalar_results=[None, None])

    await block_user(
        session,
        user=user,
        operator_admin=admin,
        confirmed=True,
        reason="violation",
        interface="callback",
        operator_username="root_admin",
    )

    assert user.is_blocked is True
    banned_entry = next(
        obj for obj in session.added if isinstance(obj, BannedRobloxAccount)
    )
    assert banned_entry.user_id == user.id
    assert banned_entry.unblocked_at is None

    log_entry = next(obj for obj in session.added if isinstance(obj, LogEntry))
    assert log_entry.event_type == "security.user_blocked"
    assert log_entry.data["operator_admin_id"] == admin.id
    assert log_entry.data["interface"] == "callback"
    assert log_entry.data["reason"] == "violation"


@pytest.mark.anyio
async def test_unblock_user_marks_history_and_logs_once():
    user = User(id=2, tg_id=321, is_blocked=True, block_reason="manual")
    admin = Admin(id=11, telegram_id=555)
    ban = BannedRobloxAccount(id=5, user_id=user.id)
    session = FakeAsyncSession(scalars_results=[[ban], []])

    success_first = await unblock_user(
        session,
        user=user,
        operator_admin=admin,
        reason="manual_unblock",
        interface="callback",
        operator_username="moderator",
    )
    success_second = await unblock_user(session, user=user, operator_admin=admin)

    assert success_first is True
    assert success_second is False
    assert ban.unblocked_at is not None
    assert ban.revoked_by == admin.id

    logs = [obj for obj in session.added if isinstance(obj, LogEntry)]
    assert len(logs) == 1
    assert logs[0].event_type == "security.user_unblocked"
    assert logs[0].data["interface"] == "callback"


@pytest.mark.anyio
async def test_banned_history_survives_profile_changes():
    user = User(id=3, tg_id=777, is_blocked=False)
    ban = BannedRobloxAccount(user_id=user.id, unblocked_at=None)
    session = FakeAsyncSession(scalar_results=[ban])
    middleware = BannedMiddleware()

    enforced = await middleware._enforce_banned_account(session, user)  # noqa: SLF001

    assert enforced is True
    assert user.is_blocked is True


@pytest.mark.anyio
async def test_admin_bypass(monkeypatch, caplog):
    middleware = BannedMiddleware()
    handler_called = False

    async def fake_is_admin(uid: int) -> bool:  # noqa: ARG001
        return True

    async def handler(event, data):  # noqa: ANN001, ARG001
        nonlocal handler_called
        handler_called = True
        return "ok"

    monkeypatch.setattr("bot.middleware.banned.is_admin", fake_is_admin)
    monkeypatch.setattr(
        middleware, "_extract_event_entities", lambda _event: (object(), None)
    )
    monkeypatch.setattr(
        middleware,
        "_extract_user_id",
        lambda _message, _callback: 424242,
    )
    async def fail_resolve_session(_data):  # noqa: ANN001
        raise AssertionError("session should not be used")

    monkeypatch.setattr(middleware, "_resolve_session", fail_resolve_session)

    with caplog.at_level("INFO", logger="bot.middleware.banned"):
        result = await middleware(handler, object(), {"is_admin": True})

    assert handler_called is True
    assert result == "ok"
    assert "Skipping banned middleware for admin user." in caplog.text