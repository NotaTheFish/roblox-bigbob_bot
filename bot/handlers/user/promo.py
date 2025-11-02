from aiogram import types, Dispatcher
from aiogram.dispatcher.filters import Command
from datetime import datetime
from sqlalchemy import select

from bot.bot_instance import bot
from bot.config import ROOT_ADMIN_ID
from bot.db import PromoCode, User, async_session
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

        # Проверка лимита
        if promo.max_uses is not None and promo.uses >= promo.max_uses:
            return await message.reply("⚠️ Этот промокод больше недоступен")

        # Проверка срока
        if promo.expires_at and datetime.utcnow() > promo.expires_at:
            return await message.reply("⛔ Срок действия промокода истёк")

        # Получаем юзера
        user = await session.scalar(select(User).where(User.tg_id == uid))
        if not user:
            return await message.reply("❗ Ошибка: вы не зарегистрированы")

        # Награда
        if promo.promo_type == "money":
            amount = int(promo.value or 0)
            user.balance += amount
            reward_text = f"💰 +{amount}"
        else:
            reward_text = f"🎁 Roblox item ID {promo.value}"

        promo.uses += 1
        await session.commit()

    await check_achievements(user)

    await message.reply(f"✅ Промокод активирован!\nВы получили: {reward_text}")

    # Уведомление админу
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
