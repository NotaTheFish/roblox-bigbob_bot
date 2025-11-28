import asyncio
import logging
import time
from random import randint

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from bot.db import Admin, BannedRobloxAccount, LogEntry, Referral, User, async_session
from bot.firebase.firebase_service import (
    add_whitelist,
    fetch_firebase_ban,
    remove_whitelist,
)
from bot.keyboards.main_menu import main_menu
from bot.keyboards.verify_kb import verify_button, verify_check_button
from bot.middleware.user_sync import normalize_tg_username
from bot.states.verify_state import VerifyState
from backend.services.achievements import evaluate_and_grant_achievements
from bot.utils.referrals import (
    DEFAULT_REFERRAL_TOPUP_SHARE_PERCENT,
    confirm_referral,
)
from bot.utils.roblox import get_roblox_profile


router = Router(name="user_verify")
logger = logging.getLogger(__name__)


# === Start verification ===
@router.callback_query(F.data == "start_verify", StateFilter(None))
async def start_verify(call: types.CallbackQuery, state: FSMContext):
    await call.message.answer("Введите ваш Roblox ник:")
    await state.set_state(VerifyState.waiting_for_username)


# === User enters Roblox nickname ===
@router.message(StateFilter(VerifyState.waiting_for_username))
async def set_username(message: types.Message, state: FSMContext):
    username = message.text.strip()
    code = randint(10000, 99999)

    if not message.from_user:
        return

    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == message.from_user.id))
        if not user:
            return

        if user.roblox_id:
            await message.answer(
                "❌ Этот Telegram уже привязан к Roblox аккаунту. "
                "Сначала отвяжите текущий аккаунт через поддержку, затем повторите попытку."
            )
            await state.clear()
            return

        previous_roblox_id = user.roblox_id

        normalized_previous_id: str | None = None
        if previous_roblox_id:
            try:
                normalized_previous_id = str(int(previous_roblox_id))
            except (TypeError, ValueError):
                logger.warning(
                    "Failed to normalise roblox_id=%s for whitelist removal",
                    previous_roblox_id,
                )

        if normalized_previous_id:
            removed = await remove_whitelist(normalized_previous_id)
            if not removed:
                logger.warning(
                    "Failed to remove roblox_id=%s from Firebase whitelist",
                    normalized_previous_id,
                )

        user.username = username
        user.code = str(code)
        user.roblox_id = None
        user.verified = False
        await session.commit()

    text = (
        f"✅ Ваш Roblox ник: <b>{username}</b>\n\n"
        f"Теперь вставьте этот код в <b>описание</b> или <b>статус</b> Roblox:\n"
        f"<code>{code}</code>\n\n"
        "После вставки нажмите кнопку ниже 👇"
    )

    await message.answer(text, parse_mode="HTML", reply_markup=verify_check_button())
    await state.set_state(VerifyState.waiting_for_check)


# === Check verification ===
@router.callback_query(F.data == "check_verify", StateFilter(VerifyState.waiting_for_check))
async def check_verify(call: types.CallbackQuery, state: FSMContext):
    await call.message.answer("⏳ Проверяем ваш Roblox профиль…\nЭто может занять до 5 секунд 🔥")

    if not call.from_user:
        return await call.message.answer("❌ Пользователь не найден. Нажмите /start")

    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == call.from_user.id))
        if not user:
            return await call.message.answer("❌ Профиль не найден. Нажмите /start")
        username = user.username
        code = user.code

    await asyncio.sleep(2)  # имитация загрузки

    desc, status, roblox_id = get_roblox_profile(username)
    if desc is None:
        return await call.message.answer("❌ Не удалось найти профиль Roblox.\nПроверьте ник и попробуйте снова.")

    full_text = f"{desc} {status}"

    if code and code in full_text:
        is_admin = False
        normalized_roblox_id: str | None = None
        firebase_ban: dict | None = None
        if roblox_id:
            try:
                normalized_roblox_id = str(int(roblox_id))
            except (TypeError, ValueError):
                logger.warning(
                    "Failed to normalise roblox_id=%s for Firebase ban check", roblox_id
                )
            else:
                firebase_ban = await fetch_firebase_ban(normalized_roblox_id)

        if firebase_ban is not None:
            async with async_session() as session:
                db_user = await session.scalar(
                    select(User).where(User.tg_id == call.from_user.id)
                )

                if db_user:
                    if roblox_id and not db_user.roblox_id:
                        db_user.roblox_id = roblox_id

                    db_user.is_blocked = True

                    existing_ban = await session.scalar(
                        select(BannedRobloxAccount).where(
                            BannedRobloxAccount.roblox_id == normalized_roblox_id,
                            BannedRobloxAccount.unblocked_at.is_(None),
                        )
                    )

                    if not existing_ban:
                        session.add(
                            BannedRobloxAccount(
                                roblox_id=normalized_roblox_id,
                                username=db_user.username,
                                user_id=db_user.id,
                            )
                        )

                    await session.commit()
                else:
                    await session.rollback()

            await state.clear()
            await call.message.answer(
                "❌ Этот Roblox аккаунт заблокирован. Верификация невозможна.",
                reply_markup=verify_button(),
            )
            return
        referrer_notify: dict | None = None
        async with async_session() as session:
            db_user = await session.scalar(select(User).where(User.tg_id == call.from_user.id))
            if db_user:
                if roblox_id is not None:
                    roblox_id = str(roblox_id)

                if roblox_id:
                    existing_user = await session.scalar(
                        select(User).where(
                            User.roblox_id == roblox_id,
                            User.id != db_user.id,
                        )
                    )
                    if existing_user:
                        await state.clear()
                        await call.message.answer(
                            "❌ Этот Roblox аккаунт уже привязан к другому Telegram. "
                            "Отвяжите его в текущем профиле или обратитесь в поддержку."
                        )
                        return

                if db_user.roblox_id and roblox_id and db_user.roblox_id != roblox_id:
                    await state.clear()
                    await call.message.answer(
                        "❌ Ваш Telegram уже привязан к другому Roblox аккаунту. "
                        "Сначала отвяжите текущий Roblox, затем попробуйте снова."
                    )
                    return

                try:
                    async with session.begin():
                        db_user.verified = True
                        if roblox_id:
                            db_user.roblox_id = roblox_id
                        referral = await session.scalar(
                            select(Referral)
                            .options(selectinload(Referral.referrer))
                            .where(Referral.referred_id == db_user.id)
                        )
                        referrer_user: User | None = None
                        if referral and not referral.confirmed:
                            referral = await confirm_referral(session, referral)
                            referrer_user = referral.referrer
                            if referrer_user:
                                granted_achievements = await evaluate_and_grant_achievements(
                                    session,
                                    user=referrer_user,
                                    trigger="referral_confirmed",
                                    payload={
                                        "referral_id": referral.id,
                                        "referred_user_id": db_user.id,
                                    },
                                )
                                referrer_notify = {
                                    "tg_id": referrer_user.tg_id,
                                    "referred_username": normalize_tg_username(
                                        call.from_user.username
                                    ),
                                }
                                achievement_ids = [
                                    achievement.achievement_id
                                    for achievement in granted_achievements
                                ]
                                session.add(
                                    LogEntry(
                                        user_id=referrer_user.id,
                                        telegram_id=referrer_user.tg_id,
                                        event_type="referral_confirmed",
                                        message="🎉 Новый подтверждённый реферал!",
                                        data={
                                            "referred_id": db_user.id,
                                            "topup_share_percent": DEFAULT_REFERRAL_TOPUP_SHARE_PERCENT,
                                            "granted_achievements": achievement_ids,
                                        },
                                    )
                                )
                                session.add(
                                    LogEntry(
                                        user_id=referrer_user.id,
                                        telegram_id=referrer_user.tg_id,
                                        event_type="referral_achievements_evaluated",
                                        message="Автоматическая проверка достижений после подтверждения реферала.",
                                        data={
                                            "referral_id": referral.id,
                                            "referred_user_id": db_user.id,
                                            "granted_achievement_ids": achievement_ids,
                                        },
                                    )
                                )
                                logger.info(
                                    "Evaluated achievements after referral confirmation",
                                    extra={
                                        "referral_id": referral.id,
                                        "referrer_id": referrer_user.id,
                                        "referred_user_id": db_user.id,
                                        "granted_achievement_ids": achievement_ids,
                                    },
                                )
                        is_admin = bool(
                            await session.scalar(
                                select(Admin).where(Admin.telegram_id == call.from_user.id)
                            )
                        )
                except IntegrityError:
                    await session.rollback()
                    await state.clear()
                    await call.message.answer(
                        "❌ Не удалось привязать аккаунт: Roblox или Telegram уже связаны с другим профилем. "
                        "Отвяжите прежнюю связь и попробуйте снова."
                    )
                    return

                if normalized_roblox_id:
                    whitelist_payload = {
                        "addedBy": call.from_user.username or str(call.from_user.id),
                        "timestamp": int(time.time()),
                    }
                    success = await add_whitelist(
                        normalized_roblox_id, whitelist_payload
                    )
                    if not success:
                        logger.warning(
                            "Failed to push roblox_id=%s to Firebase whitelist", roblox_id
                        )

        if referrer_notify:
            referred_username = referrer_notify["referred_username"]
            text = (
                "🎉 Новый подтверждённый реферал!\n"
                f"@{referred_username} прошёл проверку Roblox.\n"
                f"Вы будете получать {DEFAULT_REFERRAL_TOPUP_SHARE_PERCENT}% его будущих пополнений."
            )
            try:
                await call.bot.send_message(referrer_notify["tg_id"], text)
            except Exception:  # pragma: no cover - network/runtime issues
                logger.warning(
                    "Failed to notify referrer %s about confirmed referral %s",
                    referrer_notify["tg_id"],
                    call.from_user.id,
                    exc_info=True,
                )

        await state.clear()
        await call.message.answer(
            "✅ Аккаунт Roblox успешно подтверждён!\nДобро пожаловать! 🎉",
            reply_markup=main_menu(is_admin=is_admin),
        )
        return

    await call.message.answer(
        "❌ Код не найден. Убедитесь, что он в описании или статусе и попробуйте снова."
    )
    await call.message.answer(
        "Нажмите «🔍 Проверить» снова, когда будете готовы:",
        reply_markup=verify_check_button(),
    )


# === Cancel verification ===
@router.callback_query(F.data == "cancel_verify")
async def cancel_verify(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.answer("❌ Верификация отменена", reply_markup=verify_button())
