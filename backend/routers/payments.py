"""Payment webhook API endpoints."""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import session_scope
from ..logging import get_logger
from ..security import ensure_idempotency, finalize_idempotency, validate_hmac_signature
from ..services.payments import apply_payment_to_user, mark_payment_processed, record_payment

router = APIRouter(prefix="/payments", tags=["payments"])
logger = get_logger(__name__)


class PaymentWebhook(BaseModel):
    payment_id: str = Field(..., description="Telegram payment identifier")
    telegram_user_id: int = Field(..., description="Telegram user identifier")
    amount: int = Field(..., description="Payment amount in the smallest currency unit")
    currency: str = Field(..., description="Currency code (ISO 4217)")
    payload: Dict[str, Any] = Field(default_factory=dict)


async def get_db_session() -> AsyncSession:
    async with session_scope() as session:
        yield session


@router.post("/webhook", response_model=Dict[str, Any])
async def telegram_payment_webhook(
    payload: PaymentWebhook,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> Dict[str, Any]:
    await validate_hmac_signature(request)
    idempotency_entry = await ensure_idempotency(session, request, "/payments/webhook")
    if idempotency_entry.completed_at:
        return idempotency_entry.response_body or {"status": "ok"}

    event = await record_payment(
        session,
        payment_id=payload.payment_id,
        telegram_user_id=payload.telegram_user_id,
        amount=payload.amount,
        currency=payload.currency,
        payload=payload.payload,
    )

    await apply_payment_to_user(session, payload.telegram_user_id, payload.amount)
    await mark_payment_processed(event)

    response = {
        "status": "ok",
        "payment_id": payload.payment_id,
        "telegram_user_id": payload.telegram_user_id,
    }

    await finalize_idempotency(session, idempotency_entry, response, status.HTTP_200_OK)
    logger.info(
        "Payment webhook processed",
        extra={
            "payment_id": payload.payment_id,
            "telegram_user_id": payload.telegram_user_id,
            "amount": payload.amount,
            "idempotency_key": idempotency_entry.key,
        },
    )
    return response