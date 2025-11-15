from __future__ import annotations

from types import SimpleNamespace

import pytest

from bot.constants.stars import STARS_PACKAGES
from bot.db import Invoice
from bot.handlers.user import balance
from bot.states.user_states import TopUpState

from tests.conftest import FakeAsyncSession, make_async_session_stub


@pytest.mark.anyio("asyncio")
async def test_stars_package_creates_invoice(monkeypatch, callback_query_factory, mock_state):
    package = STARS_PACKAGES[0]
    user = SimpleNamespace(id=10, tg_id=77)
    session = FakeAsyncSession(scalar_results=[user])
    monkeypatch.setattr(balance, "async_session", make_async_session_stub(session))

    await mock_state.set_state(TopUpState.waiting_for_package)
    call = callback_query_factory(f"stars_pack:{package.code}")

    await balance.topup_create_stars_invoice(call, mock_state)

    stored_invoice = next(obj for obj in session.added if isinstance(obj, Invoice))
    assert stored_invoice.provider == "telegram_stars"
    assert stored_invoice.amount_nuts == package.nuts_amount
    assert stored_invoice.amount_rub == package.stars_price
    assert stored_invoice.metadata_json["product_id"] == package.product_id
    assert session.committed is True
    assert call.message.answers
    text, _ = call.message.answers[-1]
    assert package.title in text
    assert call.bot.invoice_links
    assert call.answers[-1][0] == "Счёт создан"
    assert await mock_state.get_state() is None


@pytest.mark.anyio("asyncio")
async def test_stars_package_requires_registered_user(
    monkeypatch, callback_query_factory, mock_state
):
    package = STARS_PACKAGES[0]
    session = FakeAsyncSession(scalar_results=[None])
    monkeypatch.setattr(balance, "async_session", make_async_session_stub(session))

    await mock_state.set_state(TopUpState.waiting_for_package)
    call = callback_query_factory(f"stars_pack:{package.code}")

    await balance.topup_create_stars_invoice(call, mock_state)

    assert session.committed is False
    assert call.message.answers
    assert "Сначала нажмите /start" in call.message.answers[-1][0]
    assert await mock_state.get_state() is None