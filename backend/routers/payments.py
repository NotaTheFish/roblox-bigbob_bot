"""Payment webhook API endpoints."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.constants.stars import STARS_PACKAGES_BY_PRODUCT_ID
from bot.db import Invoice

from ..database import session_scope
from ..logging import get_logger
from ..security import ensure_idempotency, finalize_idempotency, validate_hmac_signature
from ..services.nuts import add_nuts
from ..services.payments import apply_payment_to_user, mark_payment_processed, record_payment

router = APIRouter(prefix="/payments", tags=["payments"])
logger = get_logger(__name__)


class PaymentWebhook(BaseModel):
    payment_id: str = Field(..., description="Telegram payment identifier")
    telegram_user_id: int = Field(..., description="Telegram user identifier")
    amount: int = Field(..., description="Payment amount in the smallest currency unit")
    currency: str = Field(..., description="Currency code (ISO 4217)")
    payload: Dict[str, Any] = Field(default_factory=dict)


class StarsWebhook(BaseModel):
    invoice_id: str = Field(..., description="Provider invoice identifier")
    product_id: str = Field(..., description="Telegram product identifier")
    telegram_user_id: int = Field(..., description="Telegram user identifier")
    stars_amount: int = Field(..., description="Paid amount in Stars")
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

    payment = event.payment
    if payment is None:
        raise RuntimeError("Payment record missing for webhook event")

    await apply_payment_to_user(session, payment, payload.telegram_user_id, payload.amount)
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


@router.post("/stars/webhook", response_model=Dict[str, Any])
async def telegram_stars_webhook(
    payload: StarsWebhook,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> Dict[str, Any]:
    await validate_hmac_signature(request)
    idempotency_entry = await ensure_idempotency(session, request, "/payments/stars/webhook")
    if idempotency_entry.completed_at:
        return idempotency_entry.response_body or {"status": "ok"}

    invoice = await session.scalar(
        select(Invoice).where(Invoice.provider_invoice_id == payload.invoice_id)
    )
    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")

    package = STARS_PACKAGES_BY_PRODUCT_ID.get(payload.product_id)
    if not package:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown product id")

    if invoice.telegram_id != payload.telegram_user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User mismatch")

    stored_product = (invoice.metadata_json or {}).get("product_id") if invoice.metadata_json else None
    if stored_product and stored_product != payload.product_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Product mismatch")

    response = {
        "status": "ok",
        "invoice_id": payload.invoice_id,
        "product_id": payload.product_id,
    }

    if invoice.status == "paid":
        await finalize_idempotency(session, idempotency_entry, response, status.HTTP_200_OK)
        return response

    invoice.status = "paid"
    invoice.paid_at = datetime.now(tz=timezone.utc)
    metadata = dict(invoice.metadata_json or {})
    metadata.update({
        "package_code": package.code,
        "product_id": payload.product_id,
        "stars_amount": payload.stars_amount,
        "payload": payload.payload,
    })
    invoice.metadata_json = metadata

    await add_nuts(
        session,
        user_id=invoice.user_id,
        amount=invoice.amount_nuts,
        source="stars",
        invoice_id=invoice.id,
        metadata={
            "package_code": package.code,
            "product_id": payload.product_id,
            "stars_amount": payload.stars_amount,
        },
    )

    await finalize_idempotency(session, idempotency_entry, response, status.HTTP_200_OK)
    logger.info(
        "Stars invoice paid",
        extra={
            "invoice_id": payload.invoice_id,
            "product_id": payload.product_id,
            "telegram_user_id": payload.telegram_user_id,
        },
    )
    return response