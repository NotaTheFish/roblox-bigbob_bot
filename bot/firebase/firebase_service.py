"""Helpers for interacting with Firebase and keeping it in sync with Postgres."""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

import firebase_admin
from firebase_admin import credentials, db
from firebase_admin.db import Reference
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from bot.db import BannedRobloxAccount, User, async_session


LOGGER = logging.getLogger(__name__)

DEFAULT_DATABASE_URL = (
    "https://moderation-ad9f6-default-rtdb.europe-west1.firebasedatabase.app"
)

BASE_DIR = Path(__file__).resolve().parent
SERVICE_ACCOUNT_PATH = Path(
    os.getenv("FIREBASE_SERVICE_ACCOUNT", BASE_DIR / "serviceAccountKey.json")
)
DATABASE_URL = os.getenv("FIREBASE_DATABASE_URL", DEFAULT_DATABASE_URL)

_firebase_app: Optional[firebase_admin.App] = None
_db_reference: Optional[Reference] = None


def init_firebase() -> firebase_admin.App:
    """Initialise the Firebase Admin SDK if it has not been initialised yet."""

    global _firebase_app, _db_reference

    if _firebase_app is not None:
        return _firebase_app

    if not SERVICE_ACCOUNT_PATH.exists():
        raise FileNotFoundError(
            f"Firebase service account file not found: {SERVICE_ACCOUNT_PATH}"
        )

    cred = credentials.Certificate(str(SERVICE_ACCOUNT_PATH))
    _firebase_app = firebase_admin.initialize_app(
        cred,
        {"databaseURL": DATABASE_URL},
    )
    _db_reference = db.reference("/", app=_firebase_app)
    LOGGER.info("Firebase initialised using %s", SERVICE_ACCOUNT_PATH)
    return _firebase_app


def get_db() -> Reference:
    """Return the cached root database reference, initialising Firebase if needed."""

    if _db_reference is None:
        init_firebase()
    assert _db_reference is not None  # for type-checkers
    return _db_reference


def _get_reference(path: str) -> Reference:
    ref = get_db()
    cleaned = path.strip("/")
    if not cleaned:
        return ref
    for part in cleaned.split("/"):
        ref = ref.child(part)
    return ref


async def _run_in_thread(func, *args, **kwargs):
    return await asyncio.to_thread(func, *args, **kwargs)


async def add_firebase_ban(
    roblox_id: Optional[str], data: Optional[Dict[str, Any]] = None
) -> bool:
    """Add or overwrite a ban record in Firebase."""

    if not roblox_id:
        LOGGER.warning("Cannot add Firebase ban without roblox_id")
        return False

    payload = data or {"banned": True}
    try:
        await _run_in_thread(_get_reference(f"bans/{roblox_id}").set, payload)
        return True
    except Exception:  # pragma: no cover - defensive logging
        LOGGER.exception("Failed to add ban for roblox_id=%s", roblox_id)
        return False


async def remove_firebase_ban(roblox_id: Optional[str]) -> bool:
    """Remove a ban record from Firebase."""

    if not roblox_id:
        LOGGER.warning("Cannot remove Firebase ban without roblox_id")
        return False

    try:
        await _run_in_thread(_get_reference(f"bans/{roblox_id}").delete)
        return True
    except Exception:  # pragma: no cover - defensive logging
        LOGGER.exception("Failed to remove ban for roblox_id=%s", roblox_id)
        return False


async def fetch_all_firebase_bans() -> Dict[str, Any]:
    """Return all ban entries stored in Firebase."""

    try:
        data = await _run_in_thread(_get_reference("bans").get)
        if not data:
            return {}
        return {str(key): value for key, value in data.items() if key}
    except Exception:  # pragma: no cover - defensive logging
        LOGGER.exception("Failed to fetch Firebase bans")
        return {}


async def add_whitelist(
    roblox_id: Optional[str], data: Optional[Dict[str, Any]] = None
) -> bool:
    if not roblox_id:
        LOGGER.warning("Cannot add whitelist entry without roblox_id")
        return False

    payload = data or True
    try:
        await _run_in_thread(_get_reference(f"yes/{roblox_id}").set, payload)
        return True
    except Exception:  # pragma: no cover - defensive logging
        LOGGER.exception("Failed to add whitelist entry for roblox_id=%s", roblox_id)
        return False


async def remove_whitelist(roblox_id: Optional[str]) -> bool:
    if not roblox_id:
        LOGGER.warning("Cannot remove whitelist entry without roblox_id")
        return False

    try:
        await _run_in_thread(_get_reference(f"yes/{roblox_id}").delete)
        return True
    except Exception:  # pragma: no cover - defensive logging
        LOGGER.exception(
            "Failed to remove whitelist entry for roblox_id=%s", roblox_id
        )
        return False


async def fetch_whitelist() -> Dict[str, Any]:
    try:
        data = await _run_in_thread(_get_reference("yes").get)
        if not data:
            return {}
        return {str(key): value for key, value in data.items() if key}
    except Exception:  # pragma: no cover - defensive logging
        LOGGER.exception("Failed to fetch whitelist entries from Firebase")
        return {}


async def fetch_player_times() -> Dict[str, Any]:
    try:
        data = await _run_in_thread(_get_reference("playerTimes").get)
        if not data:
            return {}
        return data
    except Exception:  # pragma: no cover - defensive logging
        LOGGER.exception("Failed to fetch player times from Firebase")
        return {}


async def sync_bans() -> None:
    """Synchronise bans between Firebase and Postgres."""

    firebase_bans = await fetch_all_firebase_bans()
    firebase_ids = set(firebase_bans.keys())
    changed = False

    async with async_session() as session:
        result = await session.execute(
            select(BannedRobloxAccount).options(
                selectinload(BannedRobloxAccount.source_user)
            )
        )
        db_bans = result.scalars().all()
        db_ids = set()

        for ban in db_bans:
            roblox_id = (ban.roblox_id or "").strip()
            if not roblox_id:
                continue
            db_ids.add(roblox_id)

            user = ban.source_user
            if user and not user.is_blocked:
                user.is_blocked = True
                changed = True

            if roblox_id not in firebase_ids:
                payload = {
                    "username": ban.username
                    or (user.username if user and user.username else None),
                    "user_id": ban.user_id,
                }
                if await add_firebase_ban(roblox_id, payload):
                    firebase_ids.add(roblox_id)

        missing_in_db = firebase_ids - db_ids
        for roblox_id in missing_in_db:
            entry = firebase_bans.get(roblox_id, {})
            username = entry.get("username") if isinstance(entry, dict) else None
            user = await session.scalar(
                select(User).where(User.roblox_id == roblox_id)
            )
            ban = BannedRobloxAccount(
                roblox_id=roblox_id,
                username=username,
                user_id=user.id if user else None,
            )
            session.add(ban)
            if user and not user.is_blocked:
                user.is_blocked = True
            changed = True

        if changed:
            await session.commit()
        else:
            await session.rollback()


async def sync_whitelist() -> None:
    """Ensure verified users are present in the Firebase whitelist."""

    whitelist = await fetch_whitelist()
    whitelist_ids = set(whitelist.keys())

    async with async_session() as session:
        result = await session.execute(
            select(User).where(
                User.verified.is_(True),
                User.roblox_id.isnot(None),
            )
        )
        verified_users = result.scalars().all()

    for user in verified_users:
        roblox_id = user.roblox_id.strip() if user.roblox_id else ""
        if not roblox_id or roblox_id in whitelist_ids:
            continue
        payload = {
            "username": user.username,
            "user_id": user.id,
        }
        await add_whitelist(roblox_id, payload)
        whitelist_ids.add(roblox_id)


async def firebase_sync_loop(interval_seconds: int = 60) -> None:
    """Continuously keep Firebase bans/whitelist in sync with Postgres."""

    init_firebase()
    LOGGER.info("Starting Firebase sync loop with %s second interval", interval_seconds)
    while True:
        try:
            await sync_bans()
        except asyncio.CancelledError:
            raise
        except Exception:  # pragma: no cover - defensive logging
            LOGGER.exception("sync_bans failed")

        try:
            await sync_whitelist()
        except asyncio.CancelledError:
            raise
        except Exception:  # pragma: no cover - defensive logging
            LOGGER.exception("sync_whitelist failed")

        try:
            await asyncio.sleep(interval_seconds)
        except asyncio.CancelledError:
            LOGGER.info("Firebase sync loop cancelled")
            raise


__all__ = [
    "init_firebase",
    "get_db",
    "add_firebase_ban",
    "remove_firebase_ban",
    "fetch_all_firebase_bans",
    "add_whitelist",
    "remove_whitelist",
    "fetch_whitelist",
    "fetch_player_times",
    "sync_bans",
    "sync_whitelist",
    "firebase_sync_loop",
]