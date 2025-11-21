from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bot.db import Invoice, LogEntry, Payment, Referral, User
from bot.utils.referrals import DEFAULT_REFERRAL_TOPUP_SHARE_PERCENT

from ..logging import get_logger
from .achievements import evaluate_and_grant_achievements
from .nuts import add_nuts
from .telegram import TelegramNotificationError, send_message

logger = get_logger(__name__)

_REFERRAL_METADATA_KEY = "referral_bonus_topups"


async def grant_referral_topup_bonus(
    session: AsyncSession,
    *,
    payer: User,
    nuts_amount: int,
    payment: Payment | None = None,
    invoice: Invoice | None = None,
) -> None:
    """Grant a referral bonus for a balance top-up if applicable."""

    if nuts_amount <= 0:
        return

    referral = await _load_confirmed_referral(session, payer.id)
    if not referral:
        return

    if referral.referrer_id == payer.id:
        logger.warning(
            "Skipping referral bonus due to self-referral",
            extra={"user_id": payer.id, "referral_id": referral.id},
        )
        return

    referrer = referral.referrer or await session.get(User, referral.referrer_id)
    if not referrer:
        logger.warning(
            "Referrer missing for confirmed referral", extra={"referral_id": referral.id}
        )
        return

    bonus_amount = (nuts_amount * DEFAULT_REFERRAL_TOPUP_SHARE_PERCENT) // 100
    if bonus_amount <= 0:
        return

    source_target, source_kind, source_id, request_id = _resolve_source(payment, invoice)
    metadata_bundle = None
    if source_target is not None:
        metadata_bundle = _load_referral_metadata(source_target)
        if _has_bonus_record(metadata_bundle.records, source_kind, source_id):
            logger.info(
                "Referral bonus already granted for source",
                extra={"source_kind": source_kind, "source_id": source_id},
            )
            return

    bonus_metadata = {
        "referral_id": referral.id,
        "referred_user_id": payer.id,
        "percent": DEFAULT_REFERRAL_TOPUP_SHARE_PERCENT,
        "source_kind": source_kind,
        "source_id": source_id,
    }
    if payment is not None:
        bonus_metadata["payment_id"] = payment.id
    if invoice is not None:
        bonus_metadata["invoice_id"] = invoice.id

    await add_nuts(
        session,
        user=referrer,
        amount=bonus_amount,
        source="referral_bonus",
        transaction_type="referral_bonus_topup",
        reason="Реферальный бонус за пополнение",
        metadata=bonus_metadata,
    )

    await evaluate_and_grant_achievements(
        session,
        user=referrer,
        trigger="referral_bonus",
        payload={
            "referral_id": referral.id,
            "source_kind": source_kind,
            "source_id": source_id,
            "payer_id": payer.id,
        },
    )
    await evaluate_and_grant_achievements(
        session,
        user=payer,
        trigger="referral_progress",
        payload={
            "referral_id": referral.id,
            "source_kind": source_kind,
            "source_id": source_id,
        },
    )

    if metadata_bundle is not None:
        _append_bonus_record(
            source_target,
            metadata_bundle,
            source_kind,
            source_id,
            payer,
            referrer,
            nuts_amount,
            bonus_amount,
        )

    notification_text = _format_notification_text(payer, nuts_amount, bonus_amount)
    log_payload = {
        "referral_id": referral.id,
        "referrer_id": referrer.id,
        "referrer_bot_user_id": referrer.bot_user_id,
        "referrer_telegram_id": referrer.tg_id,
        "referred_user_id": payer.id,
        "referred_bot_user_id": payer.bot_user_id,
        "bonus_amount": bonus_amount,
        "credited_amount": nuts_amount,
        "percent": DEFAULT_REFERRAL_TOPUP_SHARE_PERCENT,
        "source_kind": source_kind,
        "source_id": source_id,
        "payment_id": payment.id if payment else None,
        "invoice_id": invoice.id if invoice else None,
    }

    session.add(
        LogEntry(
            user_id=referrer.id,
            telegram_id=referrer.tg_id,
            request_id=request_id,
            event_type="referral_topup_bonus_granted",
            message=notification_text,
            data=log_payload,
        )
    )
    session.add(
        LogEntry(
            user_id=payer.id,
            telegram_id=payer.tg_id,
            request_id=request_id,
            event_type="referral_topup_recorded",
            message=(
                f"Реферальный бонус {bonus_amount} монет начислен "
                f"рефереру {referrer.bot_user_id}"
            ),
            data=log_payload,
        )
    )

    try:
        await send_message(referrer.tg_id, notification_text)
    except TelegramNotificationError:
        logger.warning(
            "Failed to notify referrer about bonus",
            extra={
                "referrer_id": referrer.id,
                "referrer_tg_id": referrer.tg_id,
                "referred_id": payer.id,
                "source_kind": source_kind,
                "source_id": source_id,
            },
            exc_info=True,
        )


def _format_notification_text(payer: User, nuts_amount: int, bonus_amount: int) -> str:
    payer_id = payer.bot_user_id or f"ID {payer.id}"
    return (
        f"💰 Ваш реферал {payer_id} пополнил баланс на {nuts_amount} монет.\n"
        f"💸 Вы получили {bonus_amount} монет ({DEFAULT_REFERRAL_TOPUP_SHARE_PERCENT}% бонус)."
    )


async def _load_confirmed_referral(
    session: AsyncSession, user_id: int
) -> Referral | None:
    stmt = (
        select(Referral)
        .options(selectinload(Referral.referrer))
        .where(Referral.referred_id == user_id, Referral.confirmed.is_(True))
    )
    return await session.scalar(stmt)


class _MetadataBundle:
    def __init__(self, metadata: Dict[str, Any], records: List[Dict[str, Any]]):
        self.metadata = metadata
        self.records = records


def _load_referral_metadata(target: Payment | Invoice) -> _MetadataBundle:
    metadata = dict(getattr(target, "metadata_json", {}) or {})
    raw_records = metadata.get(_REFERRAL_METADATA_KEY)
    records: List[Dict[str, Any]]
    if isinstance(raw_records, list):
        records = list(raw_records)
    else:
        records = []
    return _MetadataBundle(metadata, records)


def _has_bonus_record(records: List[Dict[str, Any]], kind: str, identifier: int | None) -> bool:
    if identifier is None:
        return False
    return any(
        record.get("kind") == kind and record.get("id") == identifier for record in records
    )


def _append_bonus_record(
    target: Payment | Invoice,
    bundle: _MetadataBundle,
    kind: str,
    identifier: int | None,
    payer: User,
    referrer: User,
    nuts_amount: int,
    bonus_amount: int,
) -> None:
    if identifier is None:
        return
    record = {
        "kind": kind,
        "id": identifier,
        "bonus_amount": bonus_amount,
        "credited_amount": nuts_amount,
        "percent": DEFAULT_REFERRAL_TOPUP_SHARE_PERCENT,
        "referrer_id": referrer.id,
        "referred_user_id": payer.id,
        "granted_at": datetime.now(tz=timezone.utc).isoformat(),
    }
    bundle.records.append(record)
    bundle.metadata[_REFERRAL_METADATA_KEY] = bundle.records
    target.metadata_json = bundle.metadata


def _resolve_source(
    payment: Payment | None, invoice: Invoice | None
) -> Tuple[Payment | Invoice | None, str, int | None, str | None]:
    if payment is not None:
        return payment, "payment", payment.id, payment.request_id
    if invoice is not None:
        return invoice, "invoice", invoice.id, invoice.request_id
    return None, "unknown", None, None


__all__ = ["grant_referral_topup_bonus"]