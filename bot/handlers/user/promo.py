from aiogram import types, Dispatcher
from aiogram.dispatcher.filters import Command
from datetime import datetime

from bot.bot_instance import bot
from bot.config import ROOT_ADMIN_ID
from bot.db import SessionLocal, PromoCode, User
from bot.utils.achievement_checker import check_achievements


async def activate_promo(message: types.Message):
    code = message.get_args().upper()

    if not code:
        return await message.reply("Введите промокод:\n`/promo CODE`", parse_mode="Markdown")

    uid = message.from_user.id

    with SessionLocal() as s:
        promo = s.query(PromoCode).filter_by(code=code).first()

        if not promo or not promo.active:
            return await message.reply("❌ Такой промокод не существует")

        # Лимит использования
        if promo.max_uses is not None and promo.uses >= promo.max_uses:
            return await message.reply("⚠️ Этот промокод больше недоступен")

        # Проверка срока действия
        if promo.expires_at and datetime.utcnow() > promo.expires_at:
            return await message.reply("⛔ Срок действия промокода истёк")

        # Получаем юзера
        user = s.query(User).filter_by(telegram_id=uid).first()
        if not user:
            return await message.reply("❗ Ошибка: вы не зарегистрированы")

        # ✅ Награда
        if promo.promo_type == "money":
            user.balance += int(promo.value)
            reward_text = f"💰 +{promo.value}"
        else:
            # Roblox item (пока только уведомление)
            reward_text = f"🎁 Roblox item ID {promo.value}"
            # TODO: Roblox delivery later

        # Обновляем счётчик
        promo.uses += 1
        s.commit()

        # ✅ Проверяем достижения
        check_achievements(user)

    await message.reply(f"✅ Промокод активирован!\nВы получили: {reward_text}")

    # ✅ Уведомляем главного админа
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
