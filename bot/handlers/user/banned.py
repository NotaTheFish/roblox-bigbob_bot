"""Handlers related to banned users (ban appeals)."""

from __future__ import annotations

import html
from datetime import datetime, timezone

from aiogram import F, Router, types
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from sqlalchemy import select

from bot.config import ROOT_ADMIN_ID
from bot.db import Admin, LogEntry, User, async_session
from bot.keyboards.ban_appeal import BAN_APPEAL_CALLBACK
from bot.states.user_states import BanAppealState

router = Router(name="user_banned")


@router.callback_query(F.data == BAN_APPEAL_CALLBACK)
async def start_ban_appeal(call: types.CallbackQuery, state: FSMContext) -> None:
    if not call.from_user:
        return

    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == call.from_user.id))
        if not user or not user.is_blocked:
            await call.answer("Это действие доступно только заблокированным пользователям.", show_alert=True)
            return

        if user.ban_appeal_submitted:
            await call.answer("Вы уже отправили обращение. Ожидайте ответа от администрации.", show_alert=True)
            return

    await state.set_state(BanAppealState.waiting_for_message)
    if call.message:
        await call.message.answer(
            "📮 Напишите одним сообщением, почему вы считаете бан ошибочным. Это обращение увидят администраторы.",
        )
    await call.answer()


@router.message(StateFilter(BanAppealState.waiting_for_message))
async def process_ban_appeal(message: types.Message, state: FSMContext) -> None:
    if not message.from_user:
        await state.clear()
        return

    if not message.text:
        await message.answer("Пожалуйста, отправьте текстовое сообщение.")
        return

    log_entry_id: int | None = None
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == message.from_user.id))
        if not user or not user.is_blocked:
            await state.clear()
            await message.answer("❗ Команда доступна только заблокированным пользователям.")
            return

        if user.ban_appeal_submitted:
            await state.clear()
            await message.answer("Вы уже отправили обращение. Ожидайте ответа.")
            return

        log_entry = LogEntry(
            user_id=user.id,
            telegram_id=message.from_user.id,
            event_type="ban_appeal",
            message=message.text,
            data={
                "message_id": message.message_id,
                "username": message.from_user.username,
                "full_name": message.from_user.full_name,
            },
        )
        session.add(log_entry)
        await session.flush()
        log_entry_id = log_entry.id

        admin_ids = (
            await session.scalars(select(Admin.telegram_id).where(Admin.telegram_id.is_not(None)))
        ).all()

        user.ban_appeal_submitted = True
        user.ban_appeal_at = datetime.now(timezone.utc)

        await session.commit()

    sender = message.from_user
    recipients = set(admin_ids)
    if ROOT_ADMIN_ID:
        recipients.add(ROOT_ADMIN_ID)

    if recipients:
        user_link = f"<a href=\"tg://user?id={sender.id}\">{html.escape(sender.full_name)}</a>"
        notification_text = (
            "📮 <b>Обжалование бана</b>\n"
            f"Log ID: <code>{log_entry_id}</code>\n"
            f"Telegram ID: <code>{sender.id}</code>\n"
            f"Пользователь: {user_link}\n"
        )
        if sender.username:
            notification_text += f"Username: @{sender.username}\n"
        notification_text += "\nСообщение:\n" + html.escape(message.text)

        for admin_id in recipients:
            try:
                await message.bot.send_message(
                    admin_id,
                    notification_text,
                    parse_mode="HTML",
                    disable_web_page_preview=True,
                )
            except Exception:
                continue

    await state.clear()
    await message.answer(
        "✅ Ваше обращение отправлено администраторам. Мы свяжемся с вами после проверки.",
    )