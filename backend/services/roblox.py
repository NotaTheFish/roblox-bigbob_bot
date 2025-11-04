"""Utilities for synchronising state with Roblox services."""
from __future__ import annotations

import asyncio
from typing import Any, Dict

from ..logging import get_logger
from ..models import RobloxSyncEvent

logger = get_logger(__name__)


async def sync_progress(session, roblox_user_id: str, payload: Dict[str, Any]) -> None:
    """Persist a record describing the sync operation.

    Real integration would call the Roblox API; for now we store a record so the
    action can be traced and retried by operators.
    """
    await _store_sync_event(session, roblox_user_id, "progress", payload)


async def sync_grant(session, roblox_user_id: str, payload: Dict[str, Any]) -> None:
    """Record reward grants intended for Roblox delivery."""
    await _store_sync_event(session, roblox_user_id, "grant", payload)


async def _store_sync_event(session, roblox_user_id: str, action: str, payload: Dict[str, Any]) -> None:
    event = RobloxSyncEvent(roblox_user_id=roblox_user_id, action=action, payload=payload)
    session.add(event)
    await session.flush()
    logger.info(
        "Roblox sync enqueued",
        extra={"roblox_user_id": roblox_user_id, "action": action, "payload": payload},
    )

    # Simulate asynchronous work with Roblox.
    await asyncio.sleep(0)