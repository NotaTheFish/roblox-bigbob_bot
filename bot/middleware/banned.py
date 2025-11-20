"""Middleware that blocks banned users from interacting with the bot."""
from __future__ import annotations

from contextlib import suppress
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, Tuple

from aiogram import BaseMiddleware
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, TelegramObject, Update
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db import BannedRobloxAccount, User, async_session
from bot.keyboards.ban_appeal import BAN_APPEAL_CALLBACK, ban_appeal_keyboard
from bot.states.user_states import BanAppealState
from bot.texts.block import BAN_NOTIFICATION_TEXT


class BannedMiddleware(BaseMiddleware):
    """Stop processing updates for banned users except for ban appeals."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        message, callback = self._extract_event_entities(event)
        user_id = self._extract_user_id(message, callback)

        if user_id is None:
            return await handler(event, data)

        session, owns_session = await self._resolve_session(data)
        try:
            current_user = await self._resolve_user(data, session, user_id)
            if current_user and session:
                await self._enforce_banned_account(session, current_user)
            if not current_user or not current_user.is_blocked:
                return await handler(event, data)

            if callback and callback.data == BAN_APPEAL_CALLBACK:
                if "ban_appeal_was_open" not in data:
                    data["ban_appeal_was_open"] = bool(getattr(current_user, "appeal_open", False))
                if not current_user.appeal_open and session:
                    current_user.appeal_open = True
                    await session.commit()
                return await handler(event, data)

            if await self._is_ban_appeal_message(event, data):
                return await handler(event, data)

            notified = False
            if current_user.ban_notified_at is None and session:
                notified = await self._notify_user(
                    event,
                    message,
                    callback,
                    user_id,
                    data,
                )
                if notified:
                    current_user.ban_notified_at = datetime.now(timezone.utc)
                    await session.commit()

            # Always answer callbacks even if we do not notify the user.
            if callback:
                with suppress(Exception):
                    await callback.answer()

            # Stop any further processing for banned users once we have notified them.
            return None
        finally:
            if owns_session:
                await session.close()

    async def _resolve_session(
        self, data: Dict[str, Any]
    ) -> Tuple[AsyncSession | None, bool]:
        session = data.get("session")
        if session is not None:
            return session, False
        session = async_session()
        return session, True

    async def _resolve_user(
        self,
        data: Dict[str, Any],
        session: AsyncSession | None,
        user_id: int,
    ) -> User | None:
        user = data.get("current_user")
        if user and getattr(user, "tg_id", None) == user_id:
            return user
        if not session:
            return None
        user = await session.scalar(select(User).where(User.tg_id == user_id))
        if user and "current_user" not in data:
            data["current_user"] = user
        return user

    async def _is_ban_appeal_message(
        self,
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> bool:
        if isinstance(event, CallbackQuery):
            return False
        if isinstance(event, Message):
            state: FSMContext | None = data.get("state")
            if not state:
                return False
            current_state = await state.get_state()
            return current_state == BanAppealState.waiting_for_message.state
        if isinstance(event, Update):
            if event.callback_query:
                return await self._is_ban_appeal_message(event.callback_query, data)
            if event.message:
                return await self._is_ban_appeal_message(event.message, data)
        return False

    async def _notify_user(
        self,
        event: TelegramObject,
        message: Message | None,
        callback: CallbackQuery | None,
        user_id: int,
        data: Dict[str, Any],
    ) -> bool:
        reply_markup = ban_appeal_keyboard()
        bot = data.get("bot") or getattr(event, "bot", None)

        if callback:
            notified = await self._notify_callback(callback, reply_markup)
            if notified:
                return True
            if bot and callback.from_user:
                with suppress(Exception):
                    await bot.send_message(
                        callback.from_user.id,
                        BAN_NOTIFICATION_TEXT,
                        reply_markup=reply_markup,
                    )
                    return True
            return False

        if message:
            await self._update_reply_markup(message, reply_markup)
            with suppress(Exception):
                await message.answer(
                    BAN_NOTIFICATION_TEXT,
                    reply_markup=reply_markup,
                )
                return True
            return False

        if bot:
            with suppress(Exception):
                await bot.send_message(
                    user_id,
                    BAN_NOTIFICATION_TEXT,
                    reply_markup=reply_markup,
                )
                return True
        return False

    async def _notify_callback(self, callback: CallbackQuery, reply_markup) -> bool:
        if callback.message:
            try:
                await callback.message.edit_text(
                    BAN_NOTIFICATION_TEXT,
                    reply_markup=reply_markup,
                )
                return True
            except TelegramBadRequest:
                await self._update_reply_markup(callback.message, reply_markup)
                with suppress(Exception):
                    await callback.message.answer(
                        BAN_NOTIFICATION_TEXT,
                        reply_markup=reply_markup,
                    )
                    return True
            except Exception:
                return False
        return False

    async def _update_reply_markup(self, message: Message, reply_markup) -> bool:
        with suppress(Exception):
            await message.edit_reply_markup(reply_markup=reply_markup)
            return True
        return False

    def _extract_event_entities(
        self,
        event: TelegramObject,
    ) -> Tuple[Message | None, CallbackQuery | None]:
        if isinstance(event, CallbackQuery):
            return event.message, event
        if isinstance(event, Message):
            return event, None
        if isinstance(event, Update):
            if event.callback_query:
                return event.callback_query.message, event.callback_query
            if event.message:
                return event.message, None
            if event.edited_message:
                return event.edited_message, None
        return None, None

    def _extract_user_id(
        self,
        message: Message | None,
        callback: CallbackQuery | None,
    ) -> int | None:
        if callback and callback.from_user:
            return callback.from_user.id
        if message and message.from_user:
            return message.from_user.id
        return None

    async def _enforce_banned_account(self, session: AsyncSession, user: User) -> bool:
        filters = self._build_banned_filters(user)
        if not filters:
            return False

        stmt = select(BannedRobloxAccount).where(or_(*filters))
        banned_account = await session.scalar(stmt)
        if not banned_account:
            return False

        if not user.is_blocked:
            user.is_blocked = True
            user.ban_appeal_at = None
            user.ban_appeal_submitted = False
            user.appeal_open = False
            user.appeal_submitted_at = None
            user.ban_notified_at = None
            await session.commit()
        return True

    def _build_banned_filters(self, user: User) -> list:
        filters = []
        if getattr(user, "roblox_id", None):
            filters.append(BannedRobloxAccount.roblox_id == user.roblox_id)
        if getattr(user, "username", None):
            filters.append(BannedRobloxAccount.username == user.username)
        return filters

__all__ = ["BannedMiddleware"]