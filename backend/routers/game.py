"""Game-related API endpoints."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import session_scope
from ..logging import get_logger
from ..models import GameProgress, GrantEvent
from ..security import ensure_idempotency, finalize_idempotency, validate_hmac_signature
from ..services.roblox import sync_grant, sync_progress

router = APIRouter(prefix="/game", tags=["game"])
logger = get_logger(__name__)


class ProgressPushPayload(BaseModel):
    roblox_user_id: str = Field(..., description="Unique Roblox user identifier")
    progress: Dict[str, Any] = Field(..., description="Arbitrary progress payload")
    version: Optional[int] = Field(default=None, description="Client supplied progress version")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Extra metadata")


class ProgressPullRequest(BaseModel):
    roblox_user_id: str = Field(..., description="Unique Roblox user identifier")


class ProgressPullResponse(BaseModel):
    roblox_user_id: str
    progress: Dict[str, Any]
    version: int
    updated_at: datetime


class GrantReward(BaseModel):
    type: str
    amount: Optional[int] = None
    item_id: Optional[str] = None


class GrantRequest(BaseModel):
    request_id: str = Field(..., description="Client supplied unique request identifier")
    roblox_user_id: str
    rewards: List[GrantReward]
    source: Optional[str] = None


async def get_db_session() -> AsyncSession:
    async with session_scope() as session:
        yield session


@router.post("/progress/push", response_model=Dict[str, Any])
async def push_progress(
    payload: ProgressPushPayload,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> Dict[str, Any]:
    await validate_hmac_signature(request)
    idempotency_entry = await ensure_idempotency(session, request, "/game/progress/push")
    if idempotency_entry.completed_at:
        return idempotency_entry.response_body or {"status": "ok"}

    result = await session.execute(
        select(GameProgress).where(GameProgress.roblox_user_id == payload.roblox_user_id)
    )
    progress = result.scalar_one_or_none()

    now = datetime.now(tz=timezone.utc)

    if progress:
        progress.progress = payload.progress
        progress.version = payload.version or (progress.version + 1)
        progress.metadata_json = payload.metadata
        progress.updated_at = now
    else:
        progress = GameProgress(
            roblox_user_id=payload.roblox_user_id,
            progress=payload.progress,
            version=payload.version or 1,
            metadata_json=payload.metadata,
            updated_at=now,
        )
        session.add(progress)

    await session.flush()
    await sync_progress(session, payload.roblox_user_id, payload.progress)

    response = {
        "status": "ok",
        "roblox_user_id": payload.roblox_user_id,
        "version": progress.version,
        "updated_at": progress.updated_at,
    }

    await finalize_idempotency(session, idempotency_entry, response, status.HTTP_200_OK)
    logger.info(
        "Progress pushed",
        extra={
            "roblox_user_id": payload.roblox_user_id,
            "version": progress.version,
            "idempotency_key": idempotency_entry.key,
        },
    )
    return response


@router.post("/progress/pull", response_model=ProgressPullResponse)
async def pull_progress(
    payload: ProgressPullRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> ProgressPullResponse:
    await validate_hmac_signature(request)
    idempotency_entry = await ensure_idempotency(session, request, "/game/progress/pull")
    if idempotency_entry.completed_at and idempotency_entry.response_body:
        return ProgressPullResponse(**idempotency_entry.response_body)

    result = await session.execute(
        select(GameProgress).where(GameProgress.roblox_user_id == payload.roblox_user_id)
    )
    progress = result.scalar_one_or_none()
    if not progress:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Progress not found")

    response = ProgressPullResponse(
        roblox_user_id=progress.roblox_user_id,
        progress=progress.progress,
        version=progress.version,
        updated_at=progress.updated_at,
    )
    await finalize_idempotency(session, idempotency_entry, response.dict(), status.HTTP_200_OK)
    logger.info(
        "Progress pulled",
        extra={
            "roblox_user_id": payload.roblox_user_id,
            "version": progress.version,
            "idempotency_key": idempotency_entry.key,
        },
    )
    return response


@router.post("/grant", response_model=Dict[str, Any])
async def grant_rewards(
    payload: GrantRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> Dict[str, Any]:
    await validate_hmac_signature(request)
    idempotency_entry = await ensure_idempotency(session, request, "/game/grant")
    if idempotency_entry.completed_at:
        return idempotency_entry.response_body or {"status": "ok"}

    result = await session.execute(select(GrantEvent).where(GrantEvent.request_id == payload.request_id))
    event = result.scalar_one_or_none()
    if event:
        response = {
            "status": "ok",
            "roblox_user_id": event.roblox_user_id,
            "request_id": event.request_id,
        }
        await finalize_idempotency(session, idempotency_entry, response, status.HTTP_200_OK)
        return response

    event = GrantEvent(
        request_id=payload.request_id,
        roblox_user_id=payload.roblox_user_id,
        rewards=[reward.dict() for reward in payload.rewards],
        source=payload.source,
    )
    session.add(event)
    await session.flush()

    await sync_grant(session, payload.roblox_user_id, event.rewards)

    response = {
        "status": "ok",
        "roblox_user_id": payload.roblox_user_id,
        "request_id": payload.request_id,
    }
    await finalize_idempotency(session, idempotency_entry, response, status.HTTP_200_OK)
    logger.info(
        "Grant dispatched",
        extra={
            "roblox_user_id": payload.roblox_user_id,
            "request_id": payload.request_id,
            "rewards": [reward.dict() for reward in payload.rewards],
            "idempotency_key": idempotency_entry.key,
        },
    )
    return response