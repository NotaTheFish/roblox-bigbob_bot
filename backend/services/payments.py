"""Payment webhook processing utilities."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db import LogEntry, Payment, User
from ..logging import get_logger
from ..models import PaymentWebhookEvent
from .achievements import evaluate_and_grant_achievements
from .nuts import add_nuts
from .referrals import grant_referral_topup_bonus

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

    # Проверяем, есть ли платеж
    payment = await session.scalar(
        select(Payment).where(Payment.provider_payment_id == payment_id)
    )

    if payment:
        # Проверяем ивент вебхука
        event = await session.scalar(
            select(PaymentWebhookEvent).where(PaymentWebhookEvent.telegram_payment_id == payment_id)
        )
        if event:
            logger.info(
                "Payment replay detected",
                extra={"telegram_payment_id": payment_id, "telegram_user_id": telegram_user_id},
            )
            return event

    else:
        user = await session.scalar(select(User).where(User.tg_id == telegram_user_id))

        payment = Payment(
            provider="telegram",
            provider_payment_id=payment_id,
            user_id=user.id if user else None,
            telegram_id=telegram_user_id,
            amount=amount,
            currency=currency,
            status="received",
            metadata_json=payload,
        )
        session.add(payment)
        await session.flush()

    # Регистрируем событие вебхука
    event = PaymentWebhookEvent(
        payment_id=payment.id,
        telegram_payment_id=payment_id,
        telegram_user_id=telegram_user_id,
        amount=amount,
        currency=currency,
        raw_payload=payload,
        status="received",
    )
    session.add(event)

    # Логируем
    session.add(
        LogEntry(
            user_id=payment.user_id,
            telegram_id=telegram_user_id,
            request_id=payment.request_id,
            event_type="payment_received",
            message="Получен платёж",
            data={"payment_id": payment.id, "provider": payment.provider},
        )
    )

    await session.flush()
    return event


async def apply_payment_to_user(
    session: AsyncSession,
    payment: Payment,
    telegram_user_id: int,
    amount: int,
) -> None:
    """Increase the user's balance according to the payment amount."""
    user = await session.scalar(select(User).where(User.tg_id == telegram_user_id))

    if not user:
        logger.info(
            "Payment for unknown user",
            extra={"telegram_user_id": telegram_user_id, "amount": amount},
        )
        return

    await add_nuts(
        session,
        user=user,
        amount=amount,
        source="payment",
        transaction_type="payment",
        reason="Зачисление платежа",
        metadata={"payment_id": payment.id, "provider": payment.provider},
    )

    await grant_referral_topup_bonus(
        session,
        payer=user,
        nuts_amount=amount,
        payment=payment,
    )

    await evaluate_and_grant_achievements(
        session,
        user=user,
        trigger="topup",
        payload={
            "payment_id": payment.id,
            "provider": payment.provider,
            "amount": amount,
        },
    )
    payment.status = "applied"
    payment.user_id = user.id

    await session.flush()

    logger.info(
        "User balance updated from payment",
        extra={
            "telegram_user_id": telegram_user_id,
            "amount": amount,
            "new_balance": user.nuts_balance,
        },
    )

    session.add(
        LogEntry(
            user_id=user.id,
            telegram_id=user.tg_id,
            request_id=payment.request_id,
            event_type="payment_applied",
            message="Платёж зачислен на баланс",
            data={"payment_id": payment.id, "amount": amount},
        )
    )


async def mark_payment_processed(event: PaymentWebhookEvent) -> None:
    """Mark the payment event as processed."""
    event.status = "processed"
    event.processed_at = datetime.now(tz=timezone.utc)

    if event.payment:
        event.payment.status = "processed"
        event.payment.completed_at = datetime.now(tz=timezone.utc)
