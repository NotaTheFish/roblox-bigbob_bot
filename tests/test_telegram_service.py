from __future__ import annotations

import httpx
import pytest

from backend import config
from backend.services import telegram as telegram_service
from backend.services.telegram import TelegramNotificationError, send_message


@pytest.fixture(autouse=True)
def _setup_settings(monkeypatch):
    monkeypatch.setenv("BACKEND_HMAC_SECRET", "test-secret")
    config.get_settings.cache_clear()
    yield
    config.get_settings.cache_clear()


class FakeResponse:
    def __init__(self, status_code: int = 200, json_data: dict | None = None):
        self.status_code = status_code
        self._json = json_data or {"ok": True}
        self.request = httpx.Request("POST", "https://api.telegram.org")

    def raise_for_status(self):
        if self.status_code >= 400:
            response = httpx.Response(self.status_code, request=self.request)
            raise httpx.HTTPStatusError("error", request=self.request, response=response)

    def json(self):
        return self._json


class FakeClient:
    def __init__(self, response: FakeResponse):
        self._response = response

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def post(self, *args, **kwargs):
        return self._response


@pytest.mark.anyio("asyncio")
async def test_send_message_skips_on_forbidden(monkeypatch, caplog):
    response = FakeResponse(status_code=403)
    monkeypatch.setattr(httpx, "AsyncClient", lambda *args, **kwargs: FakeClient(response))

    class Recorder:
        def __init__(self):
            self.messages: list[str] = []

        def warning(self, message, *args, **kwargs):
            self.messages.append(message)

    recorder = Recorder()
    monkeypatch.setattr(telegram_service, "logger", recorder)

    with caplog.at_level("WARNING"):
        await send_message(chat_id=123, text="hello")

    assert "Telegram API request forbidden" in recorder.messages


@pytest.mark.anyio("asyncio")
async def test_send_message_raises_on_other_http_errors(monkeypatch):
    response = FakeResponse(status_code=500)
    monkeypatch.setattr(httpx, "AsyncClient", lambda *args, **kwargs: FakeClient(response))

    with pytest.raises(TelegramNotificationError):
        await send_message(chat_id=123, text="hello")


@pytest.mark.anyio("asyncio")
async def test_send_message_raises_on_api_error(monkeypatch):
    response = FakeResponse(status_code=200, json_data={"ok": False, "description": "bad"})
    monkeypatch.setattr(httpx, "AsyncClient", lambda *args, **kwargs: FakeClient(response))

    with pytest.raises(TelegramNotificationError):
        await send_message(chat_id=123, text="hello")