import importlib
import sys

import pytest


@pytest.fixture(autouse=True)
def reset_modules():
    # Ensure fresh imports between tests
    yield
    sys.modules.pop("bot.config", None)
    sys.modules.pop("bot.main_core", None)


def _prepare_required_env(monkeypatch, root_admin_value: str | None = None) -> None:
    monkeypatch.setenv("TELEGRAM_TOKEN", "123456:TESTTOKEN")
    monkeypatch.setenv("ADMIN_LOGIN_PASSWORD", "password")
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///./test.db")
    if root_admin_value is not None:
        monkeypatch.setenv("ROOT_ADMIN_ID", root_admin_value)
    else:
        monkeypatch.delenv("ROOT_ADMIN_ID", raising=False)


def test_root_admin_id_required(monkeypatch):
    _prepare_required_env(monkeypatch)

    with pytest.raises(RuntimeError, match="ROOT_ADMIN_ID must be set to a non-zero integer"):
        importlib.import_module("bot.config")


def test_zero_root_admin_id_rejected(monkeypatch):
    _prepare_required_env(monkeypatch, "0")

    with pytest.raises(RuntimeError, match="ROOT_ADMIN_ID must be set to a non-zero integer"):
        importlib.import_module("bot.config")


def test_ensure_root_admin_creates_record(monkeypatch):
    _prepare_required_env(monkeypatch, "777")

    config = importlib.import_module("bot.config")

    class AdminStub:
        telegram_id = 0

        def __init__(self, telegram_id: int, is_root: bool = False):
            self.telegram_id = telegram_id
            self.is_root = is_root

    class SessionStub:
        def __init__(self, existing_admin=None):
            self.existing_admin = existing_admin
            self.added = []
            self.committed = False

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def execute(self, *_args, **_kwargs):
            existing_admin = self.existing_admin

            class Result:
                def scalar_one_or_none(self_inner):
                    return existing_admin

            return Result()

        def add(self, obj):
            self.added.append(obj)

        async def commit(self):
            self.committed = True

    session = SessionStub()

    main_core = importlib.import_module("bot.main_core")
    monkeypatch.setattr(main_core, "Admin", AdminStub)
    monkeypatch.setattr(main_core, "ROOT_ADMIN_ID", config.ROOT_ADMIN_ID)
    monkeypatch.setattr(main_core, "async_session", lambda: session)

    class DummySelect:
        def where(self, *_args, **_kwargs):
            return self

    monkeypatch.setattr(main_core, "select", lambda *_args, **_kwargs: DummySelect())

    import asyncio

    asyncio.run(main_core.ensure_root_admin())

    assert session.committed is True
    assert len(session.added) == 1
    created_admin = session.added[0]
    assert isinstance(created_admin, AdminStub)
    assert created_admin.telegram_id == config.ROOT_ADMIN_ID
    assert created_admin.is_root is True