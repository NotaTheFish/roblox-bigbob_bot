from aiogram import types, Dispatcher
from aiogram.dispatcher.filters import Command
from datetime import datetime
from sqlalchemy import select

from bot.bot_instance import bot
from bot.config import ROOT_ADMIN_ID
from bot.db import LogEntry, PromoCode, PromocodeRedemption, User, async_session
from bot.utils.achievement_checker import check_achievements


async def activate_promo(message: types.Message):
    code = message.get_args().upper()

    if not code:
        return await message.reply("Введите промокод:\n`/promo CODE`", parse_mode="Markdown")

    if not message.from_user:
        return

    uid = message.from_user.id

    async with async_session() as session:
        promo = await session.scalar(select(PromoCode).where(PromoCode.code == code))

        if not promo or not promo.active:
            return await message.reply("❌ Такой промокод не существует")

        if promo.max_uses is not None and (promo.uses or 0) >= promo.max_uses:
            return await message.reply("⚠️ Этот промокод больше недоступен")

        if promo.expires_at and datetime.utcnow() > promo.expires_at:
            return await message.reply("⛔ Срок действия промокода истёк")

        user = await session.scalar(select(User).where(User.tg_id == uid))
        if not user:
            return await message.reply("❗ Ошибка: вы не зарегистрированы")

        # Проверяем что пользователь не использовал этот промо ранее
        already_used = await session.scalar(
            select(PromocodeRedemption).where(
                PromocodeRedemption.promocode_id == promo.id,
                PromocodeRedemption.user_id == user.id,
            )
        )
        if already_used:
            return await message.reply("⚠️ Вы уже активировали этот промокод")

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
            metadata={"promo_value": promo.value},
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
        await bot.send_message(
            ROOT_ADMIN_ID,
            f"🎟 Промокод <code>{code}</code> активировал @{message.from_user.username}\n"
            f"Выдано: {reward_text}",
            parse_mode="HTML"
        )
    except:
        pass


def register_promo(dp: Dispatcher):
    dp.register_message_handler(activate_promo, Command("promo"))
