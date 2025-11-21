"""Payment webhook API endpoints."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.constants.stars import STARS_PACKAGES_BY_PRODUCT_ID
from bot.db import Invoice, User

from ..database import session_scope
from ..logging import get_logger
from ..security import ensure_idempotency, finalize_idempotency, validate_hmac_signature
from ..services.achievements import evaluate_and_grant_achievements
from ..services.nuts import add_nuts
from ..services.payments import apply_payment_to_user, mark_payment_processed, record_payment
from ..services.referrals import grant_referral_topup_bonus

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


class WalletInvoicePayload(BaseModel):
    external_invoice_id: str = Field(..., description="Client-provided invoice id")
    status: str = Field(..., description="Wallet invoice status")
    invoice_id: str | None = Field(default=None, description="Wallet invoice identifier")
    amount: str | None = Field(default=None, description="Amount in currency units")
    currency_code: str | None = Field(default=None, description="Currency code")
    metadata: Dict[str, Any] = Field(default_factory=dict)
    raw_payload: Dict[str, Any] = Field(default_factory=dict)


class WalletWebhook(BaseModel):
    event_type: str = Field(..., description="Wallet event type")
    payload: WalletInvoicePayload


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

    user = await session.get(User, invoice.user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

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
    metadata.update(
        {
            "package_code": package.code,
            "product_id": payload.product_id,
            "stars_amount": payload.stars_amount,
            "payload": payload.payload,
        }
    )
    invoice.metadata_json = metadata

    await add_nuts(
        session,
        user=user,
        amount=invoice.amount_nuts,
        source="stars",
        transaction_type="stars",
        invoice_id=invoice.id,
        metadata={
            "package_code": package.code,
            "product_id": payload.product_id,
            "stars_amount": payload.stars_amount,
        },
    )

    await grant_referral_topup_bonus(
        session,
        payer=user,
        nuts_amount=invoice.amount_nuts,
        invoice=invoice,
    )

    await evaluate_and_grant_achievements(
        session,
        user=user,
        trigger="stars_topup",
        payload={
            "invoice_id": invoice.id,
            "provider_invoice_id": payload.invoice_id,
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


@router.post("/wallet/webhook", response_model=Dict[str, Any])
async def wallet_pay_webhook(
    payload: WalletWebhook,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> Dict[str, Any]:
    await validate_hmac_signature(request)

    invoice = await session.scalar(
        select(Invoice).where(Invoice.external_invoice_id == payload.payload.external_invoice_id)
    )
    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")

    user = await session.get(User, invoice.user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    now = datetime.now(tz=timezone.utc)
    response: Dict[str, Any] = {
        "external_invoice_id": payload.payload.external_invoice_id,
        "invoice_id": invoice.id,
    }

    if _expire_if_overdue(invoice, now):
        response["status"] = "expired"
        return response

    normalized_status = payload.payload.status.lower()
    response["status"] = normalized_status

    metadata = dict(invoice.metadata_json or {})
    metadata["wallet_payload"] = payload.model_dump()
    invoice.metadata_json = metadata

    if normalized_status == "paid":
        if invoice.status != "paid":
            invoice.status = "paid"
            invoice.paid_at = now
            paid_ton_amount, nuts_to_add_decimal = _calculate_wallet_nuts(invoice, payload)
            metadata.update(
                {
                    "wallet_paid_ton_amount": str(paid_ton_amount),
                    "wallet_nuts_calculated": str(nuts_to_add_decimal),
                }
            )
            invoice.metadata_json = metadata
            nuts_amount = int(nuts_to_add_decimal)
            audit_metadata = {
                "external_invoice_id": invoice.external_invoice_id,
                "currency_amount": str(paid_ton_amount),
                "currency_code": invoice.currency_code,
                "wallet_paid_ton_amount": str(paid_ton_amount),
                "wallet_nuts_calculated": str(nuts_to_add_decimal),
            }
            audit_metadata = {k: v for k, v in audit_metadata.items() if v is not None}
            await add_nuts(
                session,
                user=user,
                amount=nuts_amount,
                source="ton",
                transaction_type="ton",
                invoice_id=invoice.id,
                metadata=audit_metadata,
                rate_snapshot=_compose_rate_snapshot(invoice),
            )

            await grant_referral_topup_bonus(
                session,
                payer=user,
                nuts_amount=nuts_amount,
                invoice=invoice,
            )

            await evaluate_and_grant_achievements(
                session,
                user=user,
                trigger="wallet_topup",
                payload={
                    "invoice_id": invoice.id,
                    "external_invoice_id": invoice.external_invoice_id,
                    "wallet_status": normalized_status,
                    "paid_amount": str(paid_ton_amount),
                    "wallet_payload": payload.payload.model_dump(),
                },
            )
            logger.info(
                "Wallet invoice paid",
                extra={
                    "invoice_id": invoice.id,
                    "external_invoice_id": invoice.external_invoice_id,
                },
            )
    elif normalized_status in {"cancelled", "canceled"}:
        if invoice.status not in {"paid", "cancelled", "expired"}:
            invoice.status = "cancelled"
            invoice.cancelled_at = now
            logger.info(
                "Wallet invoice cancelled",
                extra={
                    "invoice_id": invoice.id,
                    "external_invoice_id": invoice.external_invoice_id,
                },
            )
    else:
        response["status"] = "ignored"

    return response


def _expire_if_overdue(invoice: Invoice, now: datetime) -> bool:
    if invoice.status != "pending":
        return False
    if invoice.expires_at and now > invoice.expires_at:
        invoice.status = "expired"
        invoice.cancelled_at = now
        return True
    return False


def _compose_rate_snapshot(invoice: Invoice) -> Dict[str, Any]:
    snapshot: Dict[str, Any] = {}
    if invoice.rate_snapshot:
        snapshot.update(invoice.rate_snapshot)
    if invoice.ton_rate_at_invoice is not None:
        snapshot.setdefault("ton_rate_at_invoice", str(Decimal(invoice.ton_rate_at_invoice)))
    return snapshot


def _calculate_wallet_nuts(
    invoice: Invoice, payload: WalletWebhook
) -> tuple[Decimal, Decimal]:
    paid_ton = _resolve_paid_ton_amount(invoice, payload)
    if invoice.ton_rate_at_invoice is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="TON rate missing on invoice",
        )
    ton_rate = Decimal(str(invoice.ton_rate_at_invoice))
    nuts_to_add = paid_ton * ton_rate
    if nuts_to_add % Decimal("1") != 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Computed nuts amount must be a whole number",
        )
    return paid_ton, nuts_to_add


def _resolve_paid_ton_amount(invoice: Invoice, payload: WalletWebhook) -> Decimal:
    if payload.payload.amount is not None:
        raw_amount: Any = payload.payload.amount
    elif invoice.currency_amount is not None:
        raw_amount = str(invoice.currency_amount)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="TON amount missing from payload and invoice",
        )

    try:
        return Decimal(str(raw_amount))
    except (InvalidOperation, TypeError) as exc:  # pragma: no cover - defensive
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid TON amount provided",
        ) from exc