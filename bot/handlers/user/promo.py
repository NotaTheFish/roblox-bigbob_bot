from datetime import datetime
import logging
import re

from aiogram import F, Router, types
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from sqlalchemy import select

from bot.config import ROOT_ADMIN_ID
from bot.db import LogEntry, PromoCode, PromocodeRedemption, User, async_session
from bot.utils.achievement_checker import check_achievements
from bot.states.user_states import PromoInputState


router = Router(name="user_promo")
logger = logging.getLogger(__name__)


PROMOCODE_PATTERN = re.compile(r"^[A-Z0-9-]{4,32}$", re.IGNORECASE)


async def redeem_promocode(message: types.Message, raw_code: str) -> bool:
    if not message.from_user:
        return False

    code = (raw_code or "").strip().upper()

    if not code:
        await message.reply("⚠️ Промокод не должен быть пустым")
        return False

    async with async_session() as session:
        promo = await session.scalar(select(PromoCode).where(PromoCode.code == code))

        if not promo or not promo.active:
            await message.reply("❌ Такой промокод не существует")
            return False

        if promo.max_uses is not None and (promo.uses or 0) >= promo.max_uses:
            await message.reply("⚠️ Этот промокод больше недоступен")
            return False

        if promo.expires_at and datetime.utcnow() > promo.expires_at:
            await message.reply("⛔ Срок действия промокода истёк")
            return False

        user = await session.scalar(select(User).where(User.tg_id == message.from_user.id))
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

        reward_amount = 0
        if promo.promo_type == "money":
            reward_amount = promo.reward_amount or int(promo.value or 0)
            user.balance += reward_amount
            reward_text = f"💰 +{reward_amount}"
            reward_type = "balance"
        else:
            reward_text = f"🎁 Roblox item ID {promo.value}"
            reward_type = promo.promo_type

        promo.uses = (promo.uses or 0) + 1

        redemption = PromocodeRedemption(
            promocode_id=promo.id,
            user_id=user.id,
            telegram_id=user.tg_id,
            reward_amount=reward_amount,
            reward_type=reward_type,
            metadata_json={"promo_value": promo.value},
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

        await session.commit()

    await check_achievements(user)

    await message.reply(f"✅ Промокод активирован!\nВы получили: {reward_text}")

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


@router.message(Command("promo"))
async def activate_promo(
    message: types.Message, command: CommandObject, state: FSMContext
):
    raw_code = (command.args or "").strip()

    if not raw_code:
        await state.set_state(PromoInputState.waiting_for_code)
        await message.reply("Введите код прямо в чат")
        return

    redeemed = await redeem_promocode(message, raw_code)

    if redeemed:
        current_state = await state.get_state()
        if current_state == PromoInputState.waiting_for_code.state:
            data = await state.get_data()
            in_profile = data.get("in_profile", False)
            await state.clear()
            if in_profile:
                await state.update_data(in_profile=True)


@router.message(F.text.regexp(PROMOCODE_PATTERN))
async def promo_from_message(message: types.Message, state: FSMContext):
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