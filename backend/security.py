"""Security helpers for signature validation and idempotency."""
from __future__ import annotations

import hmac
import json
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Dict

from fastapi import HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import get_settings
from .logging import get_logger
from .models import IdempotencyKey

logger = get_logger(__name__)


async def validate_hmac_signature(request: Request) -> bytes:
    """Ensure the request carries a valid HMAC signature."""
    signature = request.headers.get("X-Signature")
    if not signature:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing HMAC signature")

    body = await request.body()
    expected = hmac.new(get_settings().hmac_secret.encode(), body, sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid HMAC signature")

    request.state.raw_body = body
    return body


async def ensure_idempotency(
    session: AsyncSession, request: Request, endpoint: str
) -> IdempotencyKey:
    """Persist and return idempotency information for a request."""
    key = request.headers.get("Idempotency-Key")
    if not key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing Idempotency-Key header")

    result = await session.execute(select(IdempotencyKey).where(IdempotencyKey.key == key))
    entry = result.scalar_one_or_none()
    if entry and entry.completed_at:
        logger.info(
            "Idempotent replay",
            extra={
                "endpoint": endpoint,
                "idempotency_key": key,
                "status_code": entry.status_code,
            },
        )
        return entry

    if entry and not entry.completed_at:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Idempotency key already in progress")

    entry = IdempotencyKey(
        key=key,
        endpoint=endpoint,
        created_at=datetime.now(tz=timezone.utc),
    )
    session.add(entry)
    await session.flush()
    return entry


async def finalize_idempotency(
    session: AsyncSession,
    entry: IdempotencyKey,
    response_body: Dict[str, Any],
    status_code: int,
) -> None:
    """Store the response for subsequent idempotent replays."""
    entry.response_body = json.loads(json.dumps(response_body, default=str))
    entry.status_code = status_code
    entry.completed_at = datetime.now(tz=timezone.utc)
    await session.flush()