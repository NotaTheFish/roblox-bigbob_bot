from aiogram import types, Dispatcher
from aiogram.dispatcher.filters import Command
from bot.db import SessionLocal, PromoCode, User
from bot.main_core import bot
from bot.config import ROOT_ADMIN_ID


async def activate_promo(message: types.Message):
    code = message.get_args().upper()

    if not code:
        return await message.reply("Введите промокод:\n`/promo CODE`", parse_mode="Markdown")

    uid = message.from_user.id

    with SessionLocal() as s:
        promo = s.query(PromoCode).filter_by(code=code).first()

        if not promo:
            return await message.reply("❌ Такой промокод не существует")

        # check limit
        if promo.used_count >= promo.usage_limit:
            return await message.reply("⚠️ Этот промокод больше недоступен")

        # check expire
        if promo.expire_days is not None:
            from datetime import datetime, timedelta
            created = promo.created_at or datetime.now()
            expires = created + timedelta(days=promo.expire_days)
            if datetime.now() > expires:
                return await message.reply("⛔ Срок действия промокода истёк")

        user = s.query(User).filter_by(tg_id=uid).first()
        if not user:
            return await message.reply("❗ Ошибка: вы не зарегистрированы")

        # reward
        if promo.reward_type == "money":
            user.balance += int(promo.reward_value)
            reward_text = f"💰 +{promo.reward_value}"
        else:  # roblox item

from bot.utils.achievement_checker import check_achievements
check_achievements(user)

            reward_text = f"🎁 Roblox item ID {promo.reward_value}"
            # todo: later — real delivery via Roblox API

        promo.used_count += 1
        s.commit()

    await message.reply(
        f"✅ Промокод активирован!\nВы получили: {reward_text}"
    )

    # notify admin
    try:
        await bot.send_message(
            ROOT_ADMIN_ID,
            f"🎟 Промокод <code>{code}</code> активировал @{message.from_user.username}\n"
            f"Выдано: {reward_text}",
            parse_mode="HTML"
        )
    except:
        pass
