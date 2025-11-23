"""User support handlers."""

from __future__ import annotations

import html

from aiogram import F, Router, types
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import select

from bot.config import ROOT_ADMIN_ID
from bot.db import Admin, LogEntry, User, async_session
from bot.keyboards.main_menu import support_menu
from bot.middleware.user_sync import normalize_tg_username
from bot.states.user_states import SupportRequestState


router = Router(name="user_support")


@router.message(StateFilter(None), F.text == "🆘 Поддержка")
async def open_support_menu(message: types.Message):
    await message.answer(
        "🆘 Поддержка\nНапишите ваш вопрос, нажав «✍️ Написать в поддержку».",
        reply_markup=support_menu(),
    )


@router.message(F.text == "✍️ Написать в поддержку", StateFilter(None))
async def start_support_request(message: types.Message, state: FSMContext):
    await state.set_state(SupportRequestState.waiting_for_message)
    await message.answer(
        "✍️ Опишите вашу проблему одним сообщением. Наш менеджер @mp_ideu ответит вам как можно быстрее.",
    )


@router.message(StateFilter(SupportRequestState.waiting_for_message))
async def handle_support_message(message: types.Message, state: FSMContext):
    if not message.from_user:
        return

    if not message.text:
        await message.answer("Пожалуйста, отправьте текстовое сообщение для поддержки.")
        return

    sender_username = normalize_tg_username(message.from_user.username)

    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == message.from_user.id))
        if not user:
            await state.clear()
            await message.answer("❗ Сначала нажмите /start")
            return

        log_entry = LogEntry(
            user_id=user.id,
            telegram_id=message.from_user.id,
            event_type="support_request",
            message=message.text,
            data={
                "message_id": message.message_id,
                "username": sender_username,
                "full_name": message.from_user.full_name,
            },
        )
        session.add(log_entry)
        await session.flush()

        thread_id = log_entry.id
        log_entry.data = {
            **(log_entry.data or {}),
            "thread_id": thread_id,
        }

        admin_ids = (
            await session.scalars(select(Admin.telegram_id).where(Admin.telegram_id.is_not(None)))
        ).all()

        await session.commit()

    await state.clear()

    notification_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✍️ Ответить",
                    callback_data=f"reply_to_user:{message.from_user.id}",
                ),
                InlineKeyboardButton(
                    text="✅ Закрыть",
                    callback_data=f"support_close:{thread_id}",
                ),
            ]
        ]
    )

    sender = message.from_user
    user_link = f"<a href=\"tg://user?id={sender.id}\">{sender.full_name}</a>"

    notification_text = (
        "🆘 <b>Новое обращение в поддержку</b>\n"
        f"Thread ID: {thread_id}\n"
        f"Пользователь: {user_link}\n"
    )
    if sender_username:
        notification_text += f"Username: @{sender_username}\n"
    escaped_message = html.escape(message.text)
    notification_text += f"\nСообщение:\n{escaped_message}"

    recipients = set(admin_ids)
    if ROOT_ADMIN_ID:
        recipients.add(ROOT_ADMIN_ID)

    for admin_id in recipients:
        try:
            await message.bot.send_message(
                admin_id,
                notification_text,
                reply_markup=notification_keyboard,
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
        except Exception:  # pragma: no cover - ignore failures to reach admins
            continue

    await message.answer(
        "✅ Ваше обращение отправлено! Мы свяжемся с вами с аккаунта @mp_ideu."
    )