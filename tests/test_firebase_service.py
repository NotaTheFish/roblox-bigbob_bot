from __future__ import annotations

from types import SimpleNamespace

import pytest

from bot.firebase import firebase_service


@pytest.mark.anyio("asyncio")
async def test_add_ban_to_firebase_merges_custom_payload(monkeypatch):
    firebase_service._firebase_app = object()

    updates: list[dict] = []

    class FakeRef:
        def child(self, _key):
            return self

        def update(self, payload):
            updates.append(payload)

    def reference(path, app=None):
        assert path == "/bans"
        assert app is firebase_service._firebase_app
        return FakeRef()

    async def run_in_thread(func, *args, **kwargs):
        func(*args, **kwargs)

    monkeypatch.setattr(firebase_service, "db", SimpleNamespace(reference=reference))
    monkeypatch.setattr(firebase_service, "_run_in_thread", run_in_thread)

    await firebase_service.add_ban_to_firebase(
        "54321", {"reason": "test", "bannedBy": "bot"}
    )

    assert updates == [{"reason": "test", "bannedBy": "bot"}]