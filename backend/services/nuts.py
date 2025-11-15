"""Utility helpers for managing a user's nuts balance."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Mapping

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db import NutsTransaction, User


class NutsError(RuntimeError):
    """Base error for nuts balance operations."""


class NutsUserNotFoundError(NutsError):
    """Raised when the requested user cannot be located."""


class NutsInsufficientBalanceError(NutsError):
    """Raised when a debit would make the balance negative."""


async def _resolve_user(
    session: AsyncSession,
    *,
    user: User | None = None,
    user_id: int | None = None,
    telegram_id: int | None = None,
) -> User:
    """Return the requested user instance, loading it if needed."""

    if user is not None:
        return user

    stmt = select(User)
    if user_id is not None:
        stmt = stmt.where(User.id == user_id)
    elif telegram_id is not None:
        stmt = stmt.where(User.tg_id == telegram_id)
    else:
        raise ValueError("Either user, user_id or telegram_id must be provided")

    db_user = await session.scalar(stmt)
    if not db_user:
        raise NutsUserNotFoundError("User not found for nuts operation")
    return db_user


def _metadata_with_source(
    source: str,
    invoice_id: int | None,
    extra: Mapping[str, Any] | None,
) -> Dict[str, Any]:
    metadata: Dict[str, Any] = {"source": source}
    if invoice_id is not None:
        metadata["invoice_id"] = invoice_id
    if extra:
        metadata.update(extra)
    return metadata


async def get_nuts_balance(
    session: AsyncSession,
    *,
    user: User | None = None,
    user_id: int | None = None,
    telegram_id: int | None = None,
) -> int:
    """Return the user's current nuts balance."""

    db_user = await _resolve_user(
        session,
        user=user,
        user_id=user_id,
        telegram_id=telegram_id,
    )
    return db_user.nuts_balance or 0


async def add_nuts(
    session: AsyncSession,
    *,
    amount: int,
    source: str,
    transaction_type: str,
    reason: str | None = None,
    invoice_id: int | None = None,
    metadata: Mapping[str, Any] | None = None,
    rate_snapshot: Mapping[str, Any] | None = None,
    user: User | None = None,
    user_id: int | None = None,
    telegram_id: int | None = None,
) -> NutsTransaction:
    """Credit the specified amount of nuts to the user."""

    if amount <= 0:
        raise ValueError("Amount must be positive for add_nuts")

    db_user = await _resolve_user(
        session,
        user=user,
        user_id=user_id,
        telegram_id=telegram_id,
    )
    new_balance = (db_user.nuts_balance or 0) + amount
    db_user.nuts_balance = new_balance

    transaction = NutsTransaction(
        user_id=db_user.id,
        telegram_id=db_user.tg_id,
        amount=amount,
        transaction_type="credit",
        type=transaction_type,
        status="completed",
        reason=reason,
        metadata_json=_metadata_with_source(source, invoice_id, metadata),
        rate_snapshot=dict(rate_snapshot or {}),
        related_invoice=invoice_id,
        completed_at=datetime.now(tz=timezone.utc),
    )
    session.add(transaction)
    await session.flush()
    return transaction


async def subtract_nuts(
    session: AsyncSession,
    *,
    amount: int,
    source: str,
    transaction_type: str,
    reason: str | None = None,
    invoice_id: int | None = None,
    metadata: Mapping[str, Any] | None = None,
    user: User | None = None,
    user_id: int | None = None,
    telegram_id: int | None = None,
) -> NutsTransaction:
    """Debit nuts from the user while preventing negative balances."""

    if amount <= 0:
        raise ValueError("Amount must be positive for subtract_nuts")

    db_user = await _resolve_user(
        session,
        user=user,
        user_id=user_id,
        telegram_id=telegram_id,
    )
    current_balance = db_user.nuts_balance or 0
    if current_balance - amount < 0:
        raise NutsInsufficientBalanceError("Insufficient nuts balance")

    db_user.nuts_balance = current_balance - amount

    transaction = NutsTransaction(
        user_id=db_user.id,
        telegram_id=db_user.tg_id,
        amount=amount,
        transaction_type="debit",
        type=transaction_type,
        status="completed",
        reason=reason,
        metadata_json=_metadata_with_source(source, invoice_id, metadata),
        related_invoice=invoice_id,
        completed_at=datetime.now(tz=timezone.utc),
    )
    session.add(transaction)
    await session.flush()
    return transaction


__all__ = [
    "NutsError",
    "NutsInsufficientBalanceError",
    "NutsUserNotFoundError",
    "add_nuts",
    "get_nuts_balance",
    "subtract_nuts",
]