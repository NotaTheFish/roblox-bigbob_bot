import os
import json
import logging
import asyncio
import time
from pathlib import Path
from typing import Any, Dict, Optional

import firebase_admin
from firebase_admin import credentials, db
from firebase_admin.db import Reference

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from bot.db import BannedRobloxAccount, User, async_session


logger = logging.getLogger(__name__)

# -------------------------------
# Firebase Settings
# -------------------------------

FIREBASE_ENV_VAR = "FIREBASE_SERVICE_ACCOUNT"
FIREBASE_DATABASE_URL_ENV = "FIREBASE_DATABASE_URL"


def load_credentials() -> credentials.Certificate:
    """
    Loads Firebase credentials from:
    1) FIREBASE_SERVICE_ACCOUNT (JSON string, Railway)
    2) serviceAccountKey.json (local)
    """

    env_value = os.getenv(FIREBASE_ENV_VAR)

    if env_value:
        try:
            logger.info("🔥 Initializing Firebase from FIREBASE_SERVICE_ACCOUNT env")
            info = json.loads(env_value)
            return credentials.Certificate(info)
        except Exception as e:
            logger.error(f"❌ Invalid FIREBASE_SERVICE_ACCOUNT JSON: {e}")
            raise

    local_path = Path(__file__).resolve().parent / "serviceAccountKey.json"
    if not local_path.exists():
        raise FileNotFoundError(
            f"❌ Firebase key not found.\n"
            f"Tried env var {FIREBASE_ENV_VAR} and local file: {local_path}"
        )

    logger.info("🔥 Initializing Firebase from local serviceAccountKey.json")
    return credentials.Certificate(str(local_path))


_firebase_app: Optional[firebase_admin.App] = None
_db_reference: Optional[Reference] = None


def init_firebase() -> firebase_admin.App:
    global _firebase_app, _db_reference

    if _firebase_app is not None:
        return _firebase_app

    cred = load_credentials()
    db_url = os.getenv(FIREBASE_DATABASE_URL_ENV)

    if not db_url:
        raise RuntimeError(
            f"❌ {FIREBASE_DATABASE_URL_ENV} environment variable is required for Firebase"
        )

    _firebase_app = firebase_admin.initialize_app(
        cred, {"databaseURL": db_url}
    )
    _db_reference = db.reference("/", app=_firebase_app)

    logger.info("✅ Firebase initialized successfully")
    return _firebase_app


def get_db() -> Reference:
    if _db_reference is None:
        init_firebase()
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


# ----------------------------------------
# BAN Management
# ----------------------------------------

async def add_firebase_ban(
    roblox_id: Optional[str], data: Optional[Dict[str, Any]] = None
) -> bool:
    if not roblox_id:
        logger.warning("Cannot add Firebase ban without roblox_id")
        return False

    payload = data or {"banned": True}
    try:
        await _run_in_thread(_get_reference(f"bans/{roblox_id}").set, payload)
        return True
    except Exception:
        logger.exception("Failed to add ban for roblox_id=%s", roblox_id)
        return False


async def add_ban_to_firebase(
    roblox_id: Optional[str], data: Optional[Dict[str, Any]] = None
) -> bool:
    """Add or update a ban entry under `/bans` in Firebase."""

    if not roblox_id:
        logger.warning("Cannot add Firebase ban without roblox_id")
        return False

    try:
        app = _firebase_app or init_firebase()
        ref = db.reference("/bans", app=app).child(str(roblox_id))
        if data:
            await _run_in_thread(ref.update, data)
        else:
            await _run_in_thread(ref.set, {})
        return True
    except Exception:
        logger.exception("Failed to add Firebase ban for roblox_id=%s", roblox_id)
        return False


async def remove_firebase_ban(roblox_id: Optional[str]) -> bool:
    if not roblox_id:
        logger.warning("Cannot remove Firebase ban without roblox_id")
        return False

    try:
        await _run_in_thread(_get_reference(f"bans/{roblox_id}").delete)
        return True
    except Exception:
        logger.exception("Failed to remove ban for roblox_id=%s", roblox_id)
        return False


async def remove_ban_from_firebase(roblox_id: Optional[str]) -> bool:
    """Remove a ban entry from `/bans` in Firebase."""

    if not roblox_id:
        logger.warning("Cannot remove Firebase ban without roblox_id")
        return False

    try:
        app = _firebase_app or init_firebase()
        ref = db.reference("/bans", app=app).child(str(roblox_id))
        await _run_in_thread(ref.delete)
        return True
    except Exception:
        logger.exception(
            "Failed to remove Firebase ban entry for roblox_id=%s", roblox_id
        )
        return False


async def fetch_firebase_ban(roblox_id: Optional[str]) -> Optional[Dict[str, Any]]:
    if not roblox_id:
        logger.warning("Cannot fetch Firebase ban without roblox_id")
        return None

    try:
        data = await _run_in_thread(_get_reference(f"bans/{roblox_id}").get)
        if data is None:
            return None
        if isinstance(data, dict):
            return data
        logger.warning(
            "Unexpected Firebase ban payload for roblox_id=%s: %s", roblox_id, data
        )
        return None
    except Exception:
        logger.exception("Failed to fetch Firebase ban for roblox_id=%s", roblox_id)
        return None


async def fetch_all_firebase_bans() -> Dict[str, Any]:
    try:
        data = await _run_in_thread(_get_reference("bans").get)
        if not data:
            return {}
        return {str(key): value for key, value in data.items() if key}
    except Exception:
        logger.exception("Failed to fetch Firebase bans")
        return {}


# ----------------------------------------
# WHITELIST
# ----------------------------------------

async def add_whitelist(
    roblox_id: Optional[str], data: Optional[Dict[str, Any]] = None
) -> bool:
    if not roblox_id:
        logger.warning("Cannot add whitelist entry without roblox_id")
        return False

    payload = data or {"addedBy": "system", "timestamp": int(time.time())}
    try:
        await _run_in_thread(_get_reference(f"yes/{roblox_id}").set, payload)
        return True
    except Exception:
        logger.exception("Failed to add whitelist entry for roblox_id=%s", roblox_id)
        return False


async def remove_whitelist(roblox_id: Optional[str]) -> bool:
    if not roblox_id:
        logger.warning("Cannot remove whitelist entry without roblox_id")
        return False

    try:
        await _run_in_thread(_get_reference(f"yes/{roblox_id}").delete)
        return True
    except Exception:
        logger.exception("Failed to remove whitelist entry for roblox_id=%s", roblox_id)
        return False


async def fetch_whitelist() -> Dict[str, Any]:
    try:
        data = await _run_in_thread(_get_reference("yes").get)
        if not data:
            return {}
        return {str(key): value for key, value in data.items() if key}
    except Exception:
        logger.exception("Failed to fetch whitelist")
        return {}


async def fetch_player_times() -> Dict[str, Any]:
    try:
        data = await _run_in_thread(_get_reference("playerTimes").get)
        return data or {}
    except Exception:
        logger.exception("Failed to fetch player times")
        return {}


# ----------------------------------------
# SYNC LOGIC
# ----------------------------------------

async def sync_bans() -> None:
    firebase_bans = await fetch_all_firebase_bans()
    firebase_ids = set(firebase_bans.keys())
    changed = False

    async with async_session() as session:
        result = await session.execute(
            select(BannedRobloxAccount).options(
                selectinload(BannedRobloxAccount.source_user)
            ).where(BannedRobloxAccount.unblocked_at.is_(None))
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

        missing = firebase_ids - db_ids
        for roblox_id in missing:
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
    whitelist = await fetch_whitelist()
    whitelist_ids = set(whitelist.keys())
    firebase_bans = await fetch_all_firebase_bans()
    banned_ids = {str(roblox_id).strip() for roblox_id in firebase_bans.keys() if roblox_id}

    async with async_session() as session:
        db_banned_result = await session.execute(
            select(BannedRobloxAccount.roblox_id).where(
                BannedRobloxAccount.roblox_id.isnot(None),
                BannedRobloxAccount.unblocked_at.is_(None),
            )
        )
        banned_ids.update(
            {
                stripped
                for roblox_id, in db_banned_result
                if (stripped := (roblox_id or "").strip())
            }
        )

        result = await session.execute(
            select(User).where(
                User.verified.is_(True),
                User.roblox_id.isnot(None),
            )
        )
        verified_users = result.scalars().all()

    banned_whitelist_ids = {roblox_id for roblox_id in whitelist_ids if roblox_id in banned_ids}
    for roblox_id in banned_whitelist_ids:
        await remove_whitelist(roblox_id)
        whitelist_ids.discard(roblox_id)

    for user in verified_users:
        roblox_id = (user.roblox_id or "").strip()
        if not roblox_id or roblox_id in whitelist_ids or roblox_id in banned_ids:
            continue

        payload = {"username": user.username, "user_id": user.id}
        await add_whitelist(roblox_id, payload)
        whitelist_ids.add(roblox_id)


async def firebase_sync_loop(interval_seconds: int = 60) -> None:
    init_firebase()
    logger.info("Starting Firebase sync loop (%s sec interval)", interval_seconds)

    while True:
        try:
            await sync_bans()
        except Exception:
            logger.exception("sync_bans failed")

        try:
            await sync_whitelist()
        except Exception:
            logger.exception("sync_whitelist failed")

        await asyncio.sleep(interval_seconds)


__all__ = [
    "init_firebase",
    "get_db",
    "add_firebase_ban",
    "add_ban_to_firebase",
    "remove_firebase_ban",
    "remove_ban_from_firebase",
    "fetch_firebase_ban",
    "fetch_all_firebase_bans",
    "add_whitelist",
    "remove_whitelist",
    "fetch_whitelist",
    "fetch_player_times",
    "sync_bans",
    "sync_whitelist",
    "firebase_sync_loop",
]
