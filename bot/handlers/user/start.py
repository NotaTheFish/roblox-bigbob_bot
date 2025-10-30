from aiogram import types, Dispatcher
from bot.db import SessionLocal, User
from bot.keyboards.verify_kb import verify_button
from bot.keyboards.main_menu import main_menu  # ⚠️ Убедись что это твоя клавиатура главного меню


async def start_cmd(message: types.Message):
    tg_id = message.from_user.id
    username = message.from_user.username or "Unknown"

    with SessionLocal() as s:
        user = s.query(User).filter_by(tg_id=tg_id).first()

        # ✅ Если юзер первый раз
        if not user:
            new_user = User(
                tg_id=tg_id,
                username=username,
                balance=0,
                roblox_user=None,
                verified=False,
                code=None,
                is_blocked=False
            )
            s.add(new_user)
            s.commit()

            return await message.answer(
                "👋 Добро пожаловать!\n\n"
                "Для начала вы должны подтвердить свой Roblox аккаунт 👇",
                reply_markup=verify_button()
            )

        # ✅ Если пользователь заблокирован
        if user.is_blocked:
            return await message.answer("🚫 Вы заблокированы и не можете использовать бота.")

        # ✅ Если НЕ верифицирован
        if not user.verified:
            return await message.answer(
                "🔐 Для использования бота подтвердите Roblox аккаунт:",
                reply_markup=verify_button()
            )

        # ✅ Если всё ОК — запускаем меню
        await message.answer(
            f"✅ Добро пожаловать обратно, <b>{user.username}</b>!",
            reply_markup=main_menu
        )


def register_start(dp: Dispatcher):
    dp.register_message_handler(start_cmd, commands=["start"])
