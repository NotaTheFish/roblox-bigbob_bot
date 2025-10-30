from aiogram import types, Dispatcher
from bot.db import SessionLocal, User, Admin
from bot.keyboards.verify_kb import verify_button
from bot.keyboards.main_menu import main_menu


async def start_cmd(message: types.Message):
    if not message.from_user:
        return  # защита от фейк-апдейтов

    tg_id = message.from_user.id
    tg_username = message.from_user.username or "Unknown"

    with SessionLocal() as s:
        user = s.query(User).filter_by(tg_id=tg_id).first()

        # Первый вход — создаём юзера
        if not user:
            user = User(
                tg_id=tg_id,
                tg_username=tg_username,
                username=None,
                roblox_id=None,
                balance=0,
                verified=False,
                code=None,
                is_blocked=False
            )
            s.add(user)
            s.commit()

            return await message.answer(
                "👋 Добро пожаловать!\n"
                "Перед началом нужно подтвердить Roblox-аккаунт.",
                reply_markup=verify_button()
            )

        # Обновляем username если человек сменил ник в Telegram
        if user.tg_username != tg_username:
            user.tg_username = tg_username
            s.commit()

        # Проверка блокировки
        if user.is_blocked:
            return await message.answer("🚫 Вы заблокированы администратором.")

        # Проверка верификации Roblox
        if not user.verified:
            return await message.answer(
                "🔐 Для продолжения нужно подтвердить Roblox-аккаунт.",
                reply_markup=verify_button()
            )

        # Проверка — админ или нет
        is_admin = bool(s.query(Admin).filter_by(telegram_id=tg_id).first())

    # Если уже зарегистрирован и верифицирован — даём меню
    await message.answer(
        f"✅ Добро пожаловать, <b>{tg_username}</b>!",
        reply_markup=main_menu(is_admin=is_admin)
    )


def register_start(dp: Dispatcher):
    dp.register_message_handler(start_cmd, commands=["start"])
