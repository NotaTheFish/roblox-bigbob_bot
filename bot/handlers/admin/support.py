"""Admin support handlers for replying to user requests."""

from __future__ import annotations

import html
import re

from aiogram import F, Router, types
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from sqlalchemy import select

from bot.db import LogEntry, User, async_session
from bot.states.admin_states import SupportReplyState
from bot.services.admin_access import is_admin


router = Router(name="admin_support")


def _extract_thread_id(message: types.Message | None) -> int | None:
    if not message or not message.text:
        return None

    match = re.search(r"Thread ID: (\d+)", message.text)
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:  # pragma: no cover - safeguard if parsing fails
        return None


@router.callback_query(F.data.startswith("reply_to_user:"), StateFilter(None))
async def start_support_reply(callback: types.CallbackQuery, state: FSMContext):
    if not callback.from_user:
        return

    if not await is_admin(callback.from_user.id):
        await callback.answer("⛔ У вас нет доступа", show_alert=True)
        return

    thread_id = _extract_thread_id(callback.message)
    if thread_id is None:
        await callback.answer("Не удалось определить обращение", show_alert=True)
        return

    try:
        tg_id = int(callback.data.split(":", 1)[1])
    except (IndexError, ValueError):
        await callback.answer("Некорректные данные кнопки", show_alert=True)
        return

    await state.set_state(SupportReplyState.waiting_for_message)
    await state.update_data(reply_to=tg_id, thread_id=thread_id)

    await callback.answer()
    await callback.message.answer(
        f"✍️ Введите ответ для пользователя <code>{tg_id}</code> по обращению #{thread_id}.",
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("support_close:"))
async def close_support_thread(callback: types.CallbackQuery, state: FSMContext):
    if not callback.from_user:
        return

    if not await is_admin(callback.from_user.id):
        await callback.answer("⛔ У вас нет доступа", show_alert=True)
        return

    try:
        thread_id = int(callback.data.split(":", 1)[1])
    except (IndexError, ValueError):
        await callback.answer("Некорректные данные кнопки", show_alert=True)
        return

    async with async_session() as session:
        thread_entry = await session.get(LogEntry, thread_id)
        session.add(
            LogEntry(
                user_id=thread_entry.user_id if thread_entry else None,
                telegram_id=callback.from_user.id,
                event_type="support_close",
                message=f"Thread {thread_id} closed",
                data={"thread_id": thread_id},
            )
        )
        await session.commit()

    if await state.get_state() == SupportReplyState.waiting_for_message:
        data = await state.get_data()
        if data.get("thread_id") == thread_id:
            await state.clear()

    await callback.answer("Диалог закрыт")
    if callback.message:
        await callback.message.edit_reply_markup()


@router.message(StateFilter(SupportReplyState.waiting_for_message))
async def send_support_reply(message: types.Message, state: FSMContext):
    if not message.from_user:
        return

    if not await is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет доступа")
        await state.clear()
        return

    data = await state.get_data()
    tg_id = data.get("reply_to")
    thread_id = data.get("thread_id")
    if not tg_id or not thread_id:
        await message.answer("Не удалось определить адресата.")
        await state.clear()
        return

    escaped_reply = html.escape(message.text)

    await message.bot.send_message(
        tg_id,
        f"📩 <b>Ответ от поддержки</b>\n\n{escaped_reply}",
        parse_mode="HTML",
    )

    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == tg_id))
        session.add(
            LogEntry(
                user_id=user.id if user else None,
                telegram_id=message.from_user.id,
                event_type="support_reply",
                message=message.text,
                data={"thread_id": thread_id, "to": tg_id},
            )
        )
        await session.commit()

    await message.answer("✅ Ответ отправлен пользователю.")
    await state.clear()