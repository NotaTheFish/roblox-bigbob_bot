"""Payment webhook processing utilities."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db import User

from ..logging import get_logger
from ..models import PaymentWebhookEvent

logger = get_logger(__name__)


async def record_payment(
    session: AsyncSession,
    payment_id: str,
    telegram_user_id: int,
    amount: int,
    currency: str,
    payload: Dict[str, Any],
) -> PaymentWebhookEvent:
    """Persist the payment webhook event for auditing."""
    result = await session.execute(
        select(PaymentWebhookEvent).where(PaymentWebhookEvent.telegram_payment_id == payment_id)
    )
    event = result.scalar_one_or_none()
    if event:
        logger.info(
            "Payment replay detected",
            extra={"telegram_payment_id": payment_id, "telegram_user_id": telegram_user_id},
        )
        return event

    event = PaymentWebhookEvent(
        telegram_payment_id=payment_id,
        telegram_user_id=telegram_user_id,
        amount=amount,
        currency=currency,
        raw_payload=payload,
        status="received",
    )
    session.add(event)
    await session.flush()
    return event


async def apply_payment_to_user(
    session: AsyncSession,
    telegram_user_id: int,
    amount: int,
) -> None:
    """Increase the user's balance according to the payment amount."""
    result = await session.execute(select(User).where(User.tg_id == telegram_user_id))
    user = result.scalar_one_or_none()
    if not user:
        logger.info(
            "Payment for unknown user",
            extra={"telegram_user_id": telegram_user_id, "amount": amount},
        )
        return

    user.balance = (user.balance or 0) + amount
    await session.flush()
    logger.info(
        "User balance updated from payment",
        extra={"telegram_user_id": telegram_user_id, "amount": amount, "new_balance": user.balance},
    )


async def mark_payment_processed(event: PaymentWebhookEvent) -> None:
    """Mark the payment event as processed."""
    event.status = "processed"
    event.processed_at = datetime.now(tz=timezone.utc)