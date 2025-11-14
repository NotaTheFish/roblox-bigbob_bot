"""Handlers and helpers for promo code redemptions from user messages."""

from __future__ import annotations

from datetime import datetime
import logging
import re

from aiogram import F, Router, types
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from sqlalchemy import select

from bot.config import ROOT_ADMIN_ID
from bot.db import LogEntry, PromoCode, PromocodeRedemption, User, async_session
from bot.states.user_states import PromoInputState
from bot.utils.achievement_checker import check_achievements


router = Router(name="user_promocode_use")
logger = logging.getLogger(__name__)

PROMOCODE_PATTERN = re.compile(r"^[A-Z0-9-]{4,32}$", re.IGNORECASE)


async def redeem_promocode(message: types.Message, raw_code: str) -> bool:
    """Redeem the provided promo code for the message author."""

    if not message.from_user:
        return False

    code = (raw_code or "").strip().upper()

    if not code:
        await message.reply("⚠️ Промокод не должен быть пустым")
        return False

    async with async_session() as session:
        async with session.begin():
            promo = await session.scalar(
                select(PromoCode).where(PromoCode.code == code)
            )

            if not promo or not promo.active:
                await message.reply("❌ Такой промокод не существует")
                return False

            uses_count = promo.uses or 0
            max_uses = promo.max_uses or 0
            if max_uses > 0 and uses_count >= max_uses:
                await message.reply("⚠️ Этот промокод больше недоступен")
                return False

            if promo.expires_at and datetime.utcnow() > promo.expires_at:
                await message.reply("⛔ Срок действия промокода истёк")
                return False

            user = await session.scalar(
                select(User).where(User.tg_id == message.from_user.id)
            )
            if not user:
                await message.reply("❗ Ошибка: вы не зарегистрированы")
                return False

            already_used = await session.scalar(
                select(PromocodeRedemption).where(
                    PromocodeRedemption.promocode_id == promo.id,
                    PromocodeRedemption.user_id == user.id,
                )
            )
            if already_used:
                await message.reply("⚠️ Вы уже активировали этот промокод")
                return False

            reward_amount = promo.reward_amount or 0
            reward_type = (promo.reward_type or "balance").lower()
            promo_type_label = str(promo.promo_type or reward_type or "balance")
            reward_text = "🎁 Промокод активирован."
            
            if reward_type == "nuts":
                reward_amount = int(reward_amount)
                user.balance += reward_amount
                reward_text = f"🥜 На баланс начислено {reward_amount} орешков."
            elif reward_type == "discount":
                raw_value = promo.value or reward_amount or 0
                try:
                    discount_value = float(raw_value)
                except (TypeError, ValueError):
                    discount_value = float(reward_amount or 0)

                previous_discount = user.discount or 0
                user.discount = discount_value
                if previous_discount and previous_discount != discount_value:
                    reward_text = (
                        f"💸 Скидка {discount_value:g}% активирована (было {previous_discount:g}%)."
                    )
                else:
                    reward_text = f"💸 Скидка {discount_value:g}% активирована."
            else:
                reward_text = f"🎁 Промокод типа {promo_type_label} активирован."

            promo.uses = uses_count + 1

            redemption = PromocodeRedemption(
                promocode_id=promo.id,
                user_id=user.id,
                telegram_id=user.tg_id,
                reward_amount=reward_amount,
                reward_type=reward_type,
                metadata_json={
                    "promo_type": promo_type_label,
                    "promo_type": promo.promo_type,
                },
            )
            session.add(redemption)
            await session.flush()

            session.add(
                LogEntry(
                    user_id=user.id,
                    telegram_id=user.tg_id,
                    request_id=redemption.request_id,
                    event_type="promocode_redeemed",
                    message=f"Активация промокода {promo.code}",
                    data={"promo_id": promo.id},
                )
            )

    await check_achievements(user)

    reward_message = f"🎉 Промокод {code} активирован!\n{reward_text}"
    await message.reply(reward_message)

    try:
        await message.bot.send_message(
            ROOT_ADMIN_ID,
            f"🎟 Промокод <code>{code}</code> активировал @{message.from_user.username}\n"
            f"Выдано: {reward_text}",
            parse_mode="HTML",
        )
    except Exception:  # pragma: no cover - exercised via unit tests
        logger.exception(
            "Failed to notify root admin %s about promocode redemption %s by user %s",
            ROOT_ADMIN_ID,
            code,
            message.from_user.id,
            extra={"user_id": message.from_user.id, "promo_code": code},
        )

    return True


@router.message(StateFilter(None, PromoInputState.waiting_for_code), F.text.regexp(PROMOCODE_PATTERN))
async def promo_from_message(message: types.Message, state: FSMContext):
    """Automatically redeem promo codes typed directly in chat."""

    text = (message.text or "").strip()
    if not PROMOCODE_PATTERN.fullmatch(text):
        return

    data = await state.get_data()
    current_state = await state.get_state()
    in_profile = data.get("in_profile", False)
    waiting = current_state == PromoInputState.waiting_for_code.state

    if not in_profile and not waiting:
        return

    redeemed = await redeem_promocode(message, text)

    if redeemed and waiting:
        await state.clear()
        if in_profile:
            await state.update_data(in_profile=True)