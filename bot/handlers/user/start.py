from aiogram import Router, types
from aiogram.filters import CommandStart
from aiogram.filters.command import CommandStart as CommandStartFilter
from sqlalchemy import select

from bot.db import Admin, LogEntry, User, async_session
from bot.keyboards.ban_appeal import ban_appeal_keyboard
from bot.keyboards.verify_kb import verify_button
from bot.keyboards.main_menu import main_menu
from bot.texts.block import BAN_NOTIFICATION_TEXT
from bot.utils.referrals import attach_referral, ensure_referral_code, find_referrer_by_code

router = Router(name="user_start")


@router.message(CommandStartFilter())
async def start_cmd(message: types.Message, command: CommandStart):
    if not message.from_user:
        return

    tg_id = message.from_user.id
    tg_username = message.from_user.username or "Unknown"
    referral_code = (command.args or "").strip()  # ✅ Aiogram v3 способ

    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == tg_id))

        if not user:
            user = User(
                tg_id=tg_id,
                tg_username=tg_username,
                username=None,
                roblox_id=None,
                balance=0,
                verified=False,
                code=None,
                is_blocked=False,
            )
            session.add(user)
            await session.flush()

            code = await ensure_referral_code(session, user)
            referrer = None
            if referral_code:
                referrer = await find_referrer_by_code(session, referral_code)

            if referrer:
                referral = await attach_referral(session, referrer, user)
                if referral:
                    session.add(LogEntry(
                        user_id=referrer.id,
                        telegram_id=referrer.tg_id,
                        event_type="referral_attached",
                        message="Новый реферал",
                        data={"referred_id": user.id, "referral_code": referral_code},
                    ))
                    session.add(LogEntry(
                        user_id=user.id,
                        telegram_id=user.tg_id,
                        event_type="referred_signup",
                        message="Регистрация по реферальной ссылке",
                        data={"referrer_id": referrer.id},
                    ))

            session.add(LogEntry(
                user_id=user.id,
                telegram_id=user.tg_id,
                event_type="user_registered",
                message="Пользователь зарегистрирован",
                data={"referral_code": code},
            ))
            await session.commit()

            return await message.answer(
                "👋 Добро пожаловать!\n"
                "Перед началом нужно подтвердить Roblox-аккаунт.",
                reply_markup=verify_button(),
            )

        # Обновление username
        if user.tg_username != tg_username:
            user.tg_username = tg_username
            await ensure_referral_code(session, user)
            await session.commit()

        # Проверка блокировки
        if user.is_blocked:
            reply_markup = ban_appeal_keyboard() if user.ban_appeal_at is None else None
            return await message.answer(
                BAN_NOTIFICATION_TEXT,
                reply_markup=reply_markup,
            )

        # Проверка Roblox верификации
        if not user.verified:
            return await message.answer(
                "🔐 Для продолжения нужно подтвердить Roblox-аккаунт.",
                reply_markup=verify_button(),
            )

        is_admin = bool(
            await session.scalar(select(Admin).where(Admin.telegram_id == tg_id))
        )

    await message.answer(
        f"✅ Добро пожаловать, <b>{tg_username}</b>!",
        reply_markup=main_menu(is_admin=is_admin),
    )
