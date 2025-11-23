import logging

from aiogram import Router, types
from aiogram.filters import CommandStart, StateFilter
from aiogram.filters.command import CommandStart as CommandStartFilter
from aiogram.fsm.context import FSMContext
from sqlalchemy import select, text

from bot.db import Admin, LogEntry, User, async_session
from bot.keyboards.verify_kb import verify_button
from bot.keyboards.main_menu import main_menu
from bot.middleware.user_sync import normalize_tg_username
from bot.utils.referrals import attach_referral, ensure_referral_code, find_referrer_by_code
from bot.states.user_states import UserSearchState
from db.constants import BOT_USER_ID_PREFIX, BOT_USER_ID_SEQUENCE

router = Router(name="user_start")
logger = logging.getLogger(__name__)


def _extract_referral_argument(
    message: types.Message, command: CommandStart | None
) -> str:
    """Safely derive referral argument even if CommandStart is missing."""

    if command and getattr(command, "args", None):
        return (command.args or "").strip()

    get_args = getattr(message, "get_args", None)
    if callable(get_args):
        try:
            return (get_args() or "").strip()
        except Exception:  # pragma: no cover - defensive
            pass

    text = (message.text or "") if hasattr(message, "text") else ""
    if text:
        parts = text.split(maxsplit=1)
        if parts and parts[0].startswith("/start") and len(parts) > 1:
            return parts[1].strip()

    return ""


async def _generate_bot_user_id(session) -> str:
    """Reserve the next bot-specific user identifier."""

    result = await session.execute(
        text(f"SELECT nextval('{BOT_USER_ID_SEQUENCE}'::regclass)")
    )
    next_value = result.scalar_one()
    return f"{BOT_USER_ID_PREFIX}{next_value}"


@router.message(CommandStartFilter(), StateFilter(UserSearchState.query))
async def clear_search_state_and_restart(
    message: types.Message, state: FSMContext, command: CommandStart | None = None
):
    await state.clear()
    return await start_cmd(message, command)


@router.message(CommandStartFilter())
async def start_cmd(message: types.Message, command: CommandStart | None = None):
    if not message.from_user:
        return

    tg_id = message.from_user.id
    tg_username = normalize_tg_username(message.from_user.username)
    referral_code = _extract_referral_argument(message, command)
    branch = "unknown"

    try:
        async with async_session() as session:
            user = await session.scalar(select(User).where(User.tg_id == tg_id))

            if not user:
                branch = "new_user_registered"
                bot_user_id = await _generate_bot_user_id(session)
                user = User(
                    bot_user_id=bot_user_id,
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
                        pending_message = (
                            "Новый реферал — бонус будет доступен после подтверждения Roblox."
                        )
                        session.add(
                            LogEntry(
                                user_id=referrer.id,
                                telegram_id=referrer.tg_id,
                                event_type="referral_attached",
                                message=pending_message,
                                data={
                                    "referred_id": user.id,
                                    "referral_code": referral_code,
                                    "pending": True,
                                },
                            )
                        )
                        session.add(
                            LogEntry(
                                user_id=user.id,
                                telegram_id=user.tg_id,
                                event_type="referred_signup",
                                message="Регистрация по реферальной ссылке",
                                data={"referrer_id": referrer.id},
                            )
                        )

                        referred_username = normalize_tg_username(message.from_user.username)
                        notify_text = (
                            "Новый реферал!\n"
                            f"@{referred_username} зарегистрировался по вашей ссылке.\n"
                            "Бонус будет начислен после подтверждения его Roblox-аккаунта."
                        )
                        try:
                            await message.bot.send_message(referrer.tg_id, notify_text)
                        except Exception:  # pragma: no cover - network/runtime issues
                            logger.warning(
                                "Failed to notify referrer %s about pending referral from %s",
                                referrer.tg_id,
                                user.tg_id,
                                exc_info=True,
                            )

                session.add(LogEntry(
                    user_id=user.id,
                    telegram_id=user.tg_id,
                    event_type="user_registered",
                    message="Пользователь зарегистрирован",
                    data={"referral_code": code},
                ))
                await session.commit()

                logger.info(
                    "Handled /start for new user",
                    extra={
                        "telegram_id": tg_id,
                        "referral_code": referral_code,
                        "branch": branch,
                    },
                )

                return await message.answer(
                    "👋 Добро пожаловать!\n",
                    "Перед началом нужно подтвердить Roblox-аккаунт.",
                    reply_markup=verify_button(),
                )

            # Проверка Roblox верификации
            if not user.verified:
                branch = "unverified_user"
                logger.info(
                    "Handled /start for unverified user",
                    extra={
                        "telegram_id": tg_id,
                        "referral_code": referral_code,
                        "branch": branch,
                    },
                )
                return await message.answer(
                    "🔐 Для продолжения нужно подтвердить Roblox-аккаунт.",
                    reply_markup=verify_button(),
                )

            is_admin = bool(
                await session.scalar(select(Admin).where(Admin.telegram_id == tg_id))
            )
            branch = "verified_user"

        logger.info(
            "Handled /start for verified user",
            extra={
                "telegram_id": tg_id,
                "referral_code": referral_code,
                "branch": branch,
            },
        )

        await message.answer(
            f"✅ Добро пожаловать, <b>{tg_username}</b>!",
            reply_markup=main_menu(is_admin=is_admin),
        )
    except Exception:
        logger.exception(
            "Failed to handle /start",
            extra={
                "telegram_id": tg_id,
                "referral_code": referral_code,
                "branch": branch,
            },
        )
        try:
            await message.answer(
                "⚠️ Не удалось обработать команду. Пожалуйста, попробуйте позже."
            )
        except Exception:
            logger.warning(
                "Failed to send fallback response for /start",
                extra={
                    "telegram_id": tg_id,
                    "referral_code": referral_code,
                    "branch": branch,
                },
                exc_info=True,
            )
