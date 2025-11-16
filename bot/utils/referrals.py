from __future__ import annotations

from typing import Optional
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db import Referral, User

DEFAULT_REFERRAL_TOPUP_SHARE_PERCENT = 10


async def ensure_referral_code(session: AsyncSession, user: User) -> str:
    if user.referral_code:
        return user.referral_code

    while True:
        candidate = uuid4().hex[:8]
        exists = await session.scalar(select(User).where(User.referral_code == candidate))
        if not exists:
            user.referral_code = candidate
            await session.flush()
            return candidate


async def find_referrer_by_code(session: AsyncSession, code: str) -> Optional[User]:
    return await session.scalar(select(User).where(User.referral_code == code))


async def attach_referral(session: AsyncSession, referrer: User, referred: User) -> Optional[Referral]:
    if referrer.id == referred.id:
        return None

    existing = await session.scalar(select(Referral).where(Referral.referred_id == referred.id))
    if existing:
        return existing

    referral = Referral(
        referrer_id=referrer.id,
        referrer_telegram_id=referrer.tg_id,
        referred_id=referred.id,
        referred_telegram_id=referred.tg_id,
        referral_code=referrer.referral_code or "",
        confirmed=False,
    )
    session.add(referral)
    await session.flush()
    return referral


async def confirm_referral(
    session: AsyncSession,
    referral: Referral,
    *,
    topup_share_percent: int = DEFAULT_REFERRAL_TOPUP_SHARE_PERCENT,
) -> Referral:
    if referral.confirmed and (
        (referral.metadata_json or {}).get("topup_share_percent") == topup_share_percent
    ):
        return referral

    referral.confirmed = True
    metadata = dict(referral.metadata_json or {})
    metadata["topup_share_percent"] = topup_share_percent
    referral.metadata_json = metadata
    await session.flush()
    return referral