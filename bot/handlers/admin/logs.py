from __future__ import annotations

import html
import logging
from dataclasses import replace
from datetime import datetime

from aiogram import F, Router, types
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from sqlalchemy import select

from bot.config import ROOT_ADMIN_ID
from bot.db import Admin, LogEntry, async_session
from bot.keyboards.admin_keyboards import (
    LOGS_ACHIEVEMENTS_BUTTON,
    LOGS_BACK_BUTTON,
    LOGS_NEXT_BUTTON,
    LOGS_NEXT_CALLBACK,
    LOGS_PREV_BUTTON,
    LOGS_PREV_CALLBACK,
    LOGS_REFRESH_BUTTON,
    LOGS_REFRESH_CALLBACK,
    LOGS_SEARCH_BUTTON,
    LOGS_SEARCH_CALLBACK,
    admin_logs_controls_inline,
    admin_main_menu_kb,
)
from bot.keyboards.main_menu import main_menu
from bot.services.admin_logs import (
    DEFAULT_LOGS_RANGE_HOURS,
    LogCategory,
    LogPage,
    LogQuery,
    LogRecord,
    fetch_logs_page,
)
from bot.services.admin_access import is_admin
from bot.services.user_search import find_user_by_query
from bot.states.admin_states import AdminLogsState
from bot.handlers.admin.achievements import admin_achievements_menu
from bot.utils.time import to_msk


router = Router(name="admin_logs")
logger = logging.getLogger(__name__)


MAX_MESSAGE_LENGTH = 4096
LOGS_PAGE_TEXT_LIMIT = 3900


def _visible_categories_for(user_id: int | None) -> tuple[LogCategory, ...]:
    common_categories = (
        LogCategory.TOPUPS,
        LogCategory.ACHIEVEMENTS,
        LogCategory.PURCHASES,
        LogCategory.PROMOCODES,
        LogCategory.ADMIN_ACTIONS,
        LogCategory.SECURITY,
    )

    return common_categories


def _extract_offsets(data: dict) -> list[int]:
    offsets = data.get("offsets")
    if isinstance(offsets, (list, tuple)) and all(
        isinstance(item, int) for item in offsets
    ):
        return list(offsets) or [0]
    return [0]


def _split_html_text(text: str, limit: int = MAX_MESSAGE_LENGTH) -> list[str]:
    if limit <= 0:
        return [text]

    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for line in text.splitlines():
        line_length = len(line)
        separator_len = 1 if current else 0
        if current_len + separator_len + line_length <= limit:
            if current:
                current_len += separator_len
            current.append(line)
            current_len += line_length
            continue

        if current:
            chunks.append("\n".join(current))
            current = []
            current_len = 0

        while line_length > limit:
            chunks.append(line[:limit])
            line = line[limit:]
            line_length = len(line)

        if line:
            current = [line]
            current_len = line_length

    if current:
        chunks.append("\n".join(current))

    return chunks or [""]


async def send_chunked_html(
    message: types.Message,
    text: str,
    *,
    parse_mode: str | None = None,
    reply_markup: types.InlineKeyboardMarkup | None = None,
    delete_original: bool = False,
    attach_markup_to_first: bool = False,
) -> None:
    chunks = _split_html_text(text)
    if not chunks:
        return

    if delete_original:
        try:
            await message.delete()
        except TelegramBadRequest:  # pragma: no cover - Telegram API errors
            pass

    first_markup = reply_markup if len(chunks) == 1 or attach_markup_to_first else None
    await message.answer(chunks[0], parse_mode=parse_mode, reply_markup=first_markup)

    for chunk in chunks[1:-1]:
        await message.answer(chunk, parse_mode=parse_mode)

    if len(chunks) > 1:
        tail_markup = None if attach_markup_to_first else reply_markup
        await message.answer(chunks[-1], parse_mode=parse_mode, reply_markup=tail_markup)


@router.message(F.text == "📜 Логи")
async def enter_logs_menu(message: types.Message, state: FSMContext):
    if not message.from_user:
        return

    if not await is_admin(message.from_user.id):
        return await message.answer("⛔ У вас нет доступа", reply_markup=admin_main_menu_kb())

    current_state = await state.get_state()
    if current_state and current_state not in {
        AdminLogsState.browsing.state,
        AdminLogsState.waiting_for_query.state,
    }:
        return

    await state.set_state(AdminLogsState.browsing)
    await state.update_data(
        category=LogCategory.TOPUPS.value,
        page=1,
        offsets=[0],
        user_id=None,
        telegram_id=None,
        search_label=None,
    )

    await _send_logs_message(message, state)


@router.message(AdminLogsState.waiting_for_query)
async def handle_search_query(message: types.Message, state: FSMContext):
    await _handle_search_input(message, state)


@router.callback_query(StateFilter(AdminLogsState.browsing), F.data.startswith("logs:category:"))
async def category_callback(call: types.CallbackQuery, state: FSMContext):
    if not await _require_admin_callback(call):
        return

    category_value = call.data.split(":", 2)[2]
    try:
        category = LogCategory(category_value)
    except ValueError:
        return await call.answer("Неизвестная категория", show_alert=True)

    if category not in _visible_categories_for(call.from_user.id):
        return await call.answer("Недостаточно прав", show_alert=True)

    await call.answer()
    await state.update_data(category=category.value, page=1, offsets=[0])

    await _send_logs_callback(call, state)


@router.callback_query(
    StateFilter(AdminLogsState.browsing), F.data.startswith("demote_admin_confirm:")
)
async def demote_confirm(call: types.CallbackQuery, state: FSMContext):
    if not await _is_browsing_state(state):
        return await call.answer()

    if not call.from_user:
        return await call.answer()
    if call.from_user.id != ROOT_ADMIN_ID:
        return await call.answer("Недостаточно прав", show_alert=True)

    try:
        _, target_raw = (call.data or "").split(":", 1)
        target_id = int(target_raw)
    except (ValueError, AttributeError, TypeError):
        return await call.answer("Некорректные данные", show_alert=True)

    if target_id == ROOT_ADMIN_ID:
        return await call.answer("Нельзя разжаловать root-админа", show_alert=True)

    success = await _demote_admin_via_logs(target_id, call.from_user.id, call.bot)
    if not success:
        return await call.answer("Не удалось разжаловать администратора", show_alert=True)

    await _send_logs_callback(call, state)
    await call.answer("Администратор разжалован")


@router.callback_query(StateFilter(AdminLogsState.browsing), F.data == LOGS_REFRESH_CALLBACK)
async def refresh_logs(call: types.CallbackQuery, state: FSMContext):
    if not await _is_browsing_state(state):
        return await call.answer()

    await _handle_refresh(call, state)


@router.callback_query(StateFilter(AdminLogsState.browsing), F.data == LOGS_NEXT_CALLBACK)
async def next_page(call: types.CallbackQuery, state: FSMContext):
    if not await _is_browsing_state(state):
        return await call.answer()

    await _handle_page_change(call, state, delta=1)


@router.callback_query(StateFilter(AdminLogsState.browsing), F.data == LOGS_PREV_CALLBACK)
async def previous_page(call: types.CallbackQuery, state: FSMContext):
    if not await _is_browsing_state(state):
        return await call.answer()

    await _handle_page_change(call, state, delta=-1)


@router.callback_query(StateFilter(AdminLogsState.browsing), F.data == LOGS_SEARCH_CALLBACK)
async def prompt_search(call: types.CallbackQuery, state: FSMContext):
    if not await _is_browsing_state(state):
        return await call.answer()

    await _handle_search_prompt(call, state)


@router.message(StateFilter(AdminLogsState.browsing), F.text == LOGS_ACHIEVEMENTS_BUTTON)
async def open_admin_achievements(message: types.Message, state: FSMContext):
    if not await _is_browsing_state(state):
        return

    if not await _require_admin_message(message):
        return

    await state.clear()
    await admin_achievements_menu(message)


@router.message(StateFilter(AdminLogsState.browsing), F.text == LOGS_REFRESH_BUTTON)
async def refresh_logs_message(message: types.Message, state: FSMContext):
    if not await _is_browsing_state(state):
        return

    await _handle_refresh(message, state)


@router.message(StateFilter(AdminLogsState.browsing), F.text == LOGS_NEXT_BUTTON)
async def next_page_message(message: types.Message, state: FSMContext):
    if not await _is_browsing_state(state):
        return

    await _handle_page_change(message, state, delta=1)


@router.message(StateFilter(AdminLogsState.browsing), F.text == LOGS_PREV_BUTTON)
async def previous_page_message(message: types.Message, state: FSMContext):
    if not await _is_browsing_state(state):
        return

    await _handle_page_change(message, state, delta=-1)


@router.message(StateFilter(AdminLogsState.browsing), F.text == LOGS_SEARCH_BUTTON)
async def prompt_search_message(message: types.Message, state: FSMContext):
    if not await _is_browsing_state(state):
        return

    await _handle_search_prompt(message, state)


@router.message(StateFilter(AdminLogsState.browsing), F.text == LOGS_BACK_BUTTON)
async def exit_logs_menu(message: types.Message, state: FSMContext):
    if not await _require_admin_message(message):
        return

    await state.clear()
    await message.answer("Возвращаюсь в главное меню", reply_markup=admin_main_menu_kb())


@router.message(AdminLogsState.waiting_for_query, F.text == LOGS_BACK_BUTTON)
async def cancel_logs_search(message: types.Message, state: FSMContext):
    if not await _require_admin_message(message):
        return

    await state.clear()
    await message.answer("Возвращаюсь в главное меню", reply_markup=admin_main_menu_kb())


@router.callback_query(StateFilter(AdminLogsState.browsing), F.data == "logs:noop")
async def logs_noop(call: types.CallbackQuery):
    await call.answer("Недоступно", show_alert=True)



async def _handle_search_input(
    message: types.Message,
    state: FSMContext,
) -> None:
    if not await _require_admin_message(message):
        return

    query_text = (message.text or "").strip()
    if not query_text:
        await message.answer("Введите непустой поисковый запрос")
        await state.set_state(AdminLogsState.browsing)
        return

    user = await find_user_by_query(query_text)
    if not user:
        await message.answer("Пользователь не найден")
        await state.set_state(AdminLogsState.browsing)
        return

    await state.update_data(
        user_id=user.id,
        telegram_id=user.tg_id,
        search_label=_describe_user(user),
        page=1,
        offsets=[0],
    )
    await state.set_state(AdminLogsState.browsing)
    await _send_logs_message(message, state)


async def _handle_refresh(
    trigger: types.CallbackQuery | types.Message, state: FSMContext
) -> None:
    if isinstance(trigger, types.CallbackQuery):
        if not await _require_admin_callback(trigger):
            return

        await trigger.answer()
        await _send_logs_callback(trigger, state)
    else:
        if not await _require_admin_message(trigger):
            return

        await _send_logs_message(trigger, state)


async def _handle_page_change(
    trigger: types.CallbackQuery | types.Message, state: FSMContext, *, delta: int
) -> None:
    if isinstance(trigger, types.CallbackQuery):
        if not await _require_admin_callback(trigger):
            return

        await _update_page(state, delta)
        await trigger.answer()
        await _send_logs_callback(trigger, state)
    else:
        if not await _require_admin_message(trigger):
            return

        await _update_page(state, delta)
        await _send_logs_message(trigger, state)


async def _update_page(state: FSMContext, delta: int) -> None:
    data = await state.get_data()
    current = int(data.get("page", 1))
    offsets = _extract_offsets(data)
    first_page = int(data.get("first_page", 1))
    total_pages = int(data.get("total_pages", len(offsets))) or len(offsets)

    if delta < 0:
        await state.update_data(page=max(first_page, current + delta))
        return

    max_page = total_pages if total_pages > 0 else len(offsets)
    if delta > 0 and current < max_page:
        await state.update_data(page=min(max_page, current + 1))


async def _handle_search_prompt(
    trigger: types.CallbackQuery | types.Message, state: FSMContext
) -> None:
    if not await _is_browsing_state(state):
        if isinstance(trigger, types.CallbackQuery):
            await trigger.answer()
        return

    if isinstance(trigger, types.CallbackQuery):
        if not await _require_admin_callback(trigger):
            return

        await trigger.answer()
        target_message = trigger.message
    else:
        if not await _require_admin_message(trigger):
            return

        target_message = trigger

    await state.set_state(AdminLogsState.waiting_for_query)
    if target_message:
        await target_message.answer(
            "Введите ник в боте/username/ID/tg_username пользователя для поиска:"
        )


async def _require_admin_message(message: types.Message) -> bool:
    if not message.from_user:
        return False
    if not await is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет доступа", reply_markup=admin_main_menu_kb())
        return False
    return True


async def _require_admin_callback(call: types.CallbackQuery) -> bool:
    if not call.from_user:
        return False
    if not await is_admin(call.from_user.id):
        await call.answer("Нет доступа", show_alert=True)
        return False
    return True


async def _is_browsing_state(state: FSMContext) -> bool:
    return (await state.get_state()) == AdminLogsState.browsing.state


async def _send_logs_message(message: types.Message, state: FSMContext) -> None:
    if not message.from_user:
        return

    await state.set_state(AdminLogsState.browsing)
    text, inline_markup, _ = await _prepare_logs_view(
        state, message.from_user.id
    )

    await send_chunked_html(
        message,
        text,
        parse_mode="HTML",
        reply_markup=inline_markup,
        attach_markup_to_first=True,
    )


async def _send_logs_callback(call: types.CallbackQuery, state: FSMContext) -> None:
    if not call.message or not call.from_user:
        return

    text, markup, _ = await _prepare_logs_view(state, call.from_user.id)
    await send_chunked_html(
        call.message,
        text,
        parse_mode="HTML",
        reply_markup=markup,
        delete_original=True,
    )


async def _prepare_logs_view(
    state: FSMContext, viewer_id: int
) -> tuple[
    str, types.InlineKeyboardMarkup, LogPage
]:
    data = await state.get_data()
    visible_categories = _visible_categories_for(viewer_id)
    category = _category_from_state(data, visible_categories)
    requested_page = max(int(data.get("page", 1)), int(data.get("first_page", 1)))
    offsets = _extract_offsets(data)
    start_offset = offsets[min(requested_page - 1, len(offsets) - 1)]
    query = LogQuery(
        category=category,
        page=requested_page,
        offset=start_offset,
        user_id=data.get("user_id"),
        telegram_id=data.get("telegram_id"),
    )
    page = await _collect_logs_page(query, category, data)
    updated_offsets = page.pages_offsets
    await state.update_data(
        offsets=updated_offsets,
        page=page.page,
        total_pages=page.total_pages,
        first_page=page.first_page,
        category=category.value,
    )
    text = _format_logs_text(page, category, data)
    inline_markup = admin_logs_controls_inline(
        selected=category,
        has_prev=page.has_prev,
        has_next=page.next_offset is not None,
        current_page=page.page,
        total_pages=page.total_pages,
        is_root=viewer_id == ROOT_ADMIN_ID,
        visible_categories=visible_categories,
    )
    return text, inline_markup, page


def _category_from_state(
    data: dict, visible_categories: tuple[LogCategory, ...]
) -> LogCategory:
    fallback = visible_categories[0] if visible_categories else LogCategory.TOPUPS
    value = data.get("category") or fallback.value
    try:
        category = LogCategory(value)
    except ValueError:
        return fallback

    if category not in visible_categories:
        return fallback

    return category


async def _collect_logs_page(
    query: LogQuery, category: LogCategory, data: dict
) -> LogPage:
    offsets, pages = await _paginate_logs(query, category, data)
    total_pages = len(offsets) or 1
    first_page = 1 if total_pages <= 10 else total_pages - 9
    target_page = min(max(query.page, first_page), total_pages)

    page = pages.get(target_page)
    if page is None:
        target_offset = offsets[target_page - 1] if offsets else 0
        page = await _build_log_page(
            replace(query, page=target_page, offset=target_offset), category, data
        )

    has_prev = target_page > first_page
    next_offset = page.next_offset if target_page < total_pages else None

    return replace(
        page,
        page=target_page,
        total_pages=total_pages,
        first_page=first_page,
        pages_offsets=tuple(offsets),
        next_offset=next_offset,
        has_prev=has_prev,
    )


async def _paginate_logs(
    query: LogQuery, category: LogCategory, data: dict
) -> tuple[list[int], dict[int, LogPage]]:
    offsets: list[int] = []
    pages: dict[int, LogPage] = {}
    current_offset = 0
    page_number = 1

    while True:
        page_query = replace(query, page=page_number, offset=current_offset)
        page = await _build_log_page(page_query, category, data)
        pages[page_number] = page
        offsets.append(current_offset)

        if page.next_offset is None:
            break

        current_offset = page.next_offset
        page_number += 1

    return offsets, pages


async def _build_log_page(
    query: LogQuery, category: LogCategory, data: dict
) -> LogPage:
    start_offset = max(0, query.offset)
    entries: list[LogRecord] = []
    current_offset = start_offset

    while True:
        batch = await fetch_logs_page(replace(query, offset=current_offset))

        if not batch.entries:
            next_offset = batch.next_offset
            break

        for idx, record in enumerate(batch.entries):
            candidate_entries = [*entries, record]
            more_ahead = idx < len(batch.entries) - 1 or batch.next_offset is not None

            candidate_page = LogPage(
                entries=candidate_entries,
                page=query.page,
                total_pages=query.page,
                first_page=1,
                offset=start_offset,
                pages_offsets=(),
                next_offset=(start_offset + len(candidate_entries)) if more_ahead else None,
                has_prev=query.page > 1,
            )
            if len(_format_logs_text(candidate_page, category, data)) > LOGS_PAGE_TEXT_LIMIT:
                next_offset = start_offset + len(entries)
                return LogPage(
                    entries=entries,
                    page=query.page,
                    total_pages=query.page,
                    first_page=1,
                    offset=start_offset,
                    pages_offsets=(),
                    next_offset=next_offset,
                    has_prev=query.page > 1,
                )

            entries.append(record)

        if batch.next_offset is None:
            next_offset = None
            break

        current_offset = batch.next_offset

    return LogPage(
        entries=entries,
        page=query.page,
        total_pages=query.page,
        first_page=1,
        offset=start_offset,
        pages_offsets=(),
        next_offset=next_offset,
        has_prev=query.page > 1,
    )


def _format_logs_text(page: LogPage, category: LogCategory, data: dict) -> str:
    lines = [
        f"📜 <b>{_CATEGORY_TITLES[category]}</b>",
        f"Период: последние {DEFAULT_LOGS_RANGE_HOURS} ч.",
        f"Страница {page.page}/{page.total_pages}",
    ]
    search_label = data.get("search_label")
    if search_label:
        lines.append(f"👤 Поиск: <i>{html.escape(search_label)}</i>")
    lines.append("")

    if not page.entries:
        lines.append("Записей не найдено")
    else:
        for idx, record in enumerate(page.entries, start=1):
            lines.append(_format_record_line(idx, record))

    return "\n".join(lines)


def _format_record_line(position: int, record: LogRecord) -> str:
    timestamp = to_msk(record.created_at).strftime("%d.%m %H:%M")
    title = html.escape(record.message or record.event_type)

    user_line = _format_user_line(record)
    meta_line = (
        f"    Событие: #{record.id} • {html.escape(record.event_type)}"
    )
    details = _format_data_details(record)

    parts = [
        f"{position}. <b>{timestamp}</b> — {title}",
        user_line,
        meta_line,
        *details,
    ]
    return "\n".join(parts)


def _format_user_line(record: LogRecord) -> str:
    details: list[str] = []
    data = record.data if isinstance(record.data, dict) else {}

    for key in ("username", "tg_username", "redeemed_by_username"):
        username = data.get(key)
        if username:
            username = str(username)
            prefix = "" if username.startswith("@") else "@"
            details.append(f"{prefix}{html.escape(username)}")

    full_name = data.get("full_name")
    if full_name:
        details.append(html.escape(str(full_name)))

    if record.telegram_id:
        details.append(f"tg:<code>{record.telegram_id}</code>")
    if record.user_id:
        details.append(f"id:{record.user_id}")

    summary = "; ".join(details) if details else "—"
    return f"    Пользователь: {summary}"


def _format_data_details(record: LogRecord) -> list[str]:
    if not isinstance(record.data, dict) or not record.data:
        return []

    allowed_keys = _EVENT_DATA_KEYS.get(record.event_type)
    payload = record.data

    if allowed_keys is None:
        keys = [key for key in _DATA_LABELS if key in payload]
    else:
        keys = [key for key in allowed_keys if key in payload]

    lines: list[str] = []
    for key in keys:
        value = payload.get(key)
        if value in (None, ""):
            continue
        label = _DATA_LABELS.get(key, key)
        lines.append(f"    • {label}: {html.escape(str(value))}")

    return ["    Детали:", *lines] if lines else []


_DATA_LABELS: dict[str, str] = {
    "achievement_id": "ID достижения",
    "amount": "Сумма",
    "closed_message": "Сообщение",
    "demoted_by": "Разжалован",
    "full_name": "Имя",
    "limit": "Лимит на пользователя",
    "message_id": "ID сообщения",
    "observed": "Наблюдаемое значение",
    "payment_id": "ID платежа",
    "product_id": "ID товара",
    "promo_code": "Промокод",
    "promo_id": "ID промокода",
    "promo_type": "Тип",
    "promo_type_label": "Тип",
    "provider": "Провайдер",
    "redeemed_by_username": "Username",
    "referral_code": "Реферальный код",
    "referral_id": "ID реферала",
    "referral_bonus": "Реферальный бонус",
    "referred_id": "ID приглашённого",
    "referrer_id": "ID реферера",
    "reward_amount": "Награда",
    "reward_effect": "Эффект",
    "reward_text": "Описание награды",
    "reward_type": "Тип награды",
    "server_id": "ID сервера",
    "server_name": "Сервер",
    "slug": "Slug",
    "status": "Статус",
    "thread_id": "Тред",
    "threshold": "Порог",
    "to": "Получатель",
    "trigger": "Триггер",
    "url": "URL",
    "username": "Username",
}


_EVENT_DATA_KEYS: dict[str, list[str]] = {
    "achievement_granted": ["achievement_id", "trigger", "observed", "threshold"],
    "achievement_manual_granted": ["achievement_id", "trigger"],
    "admin_demoted": ["demoted_by"],
    "ban_appeal": ["full_name", "username", "message_id"],
    "payment_applied": ["payment_id", "amount"],
    "payment_received": ["payment_id", "provider"],
    "product_created": ["product_id", "slug", "limit", "referral_bonus"],
    "product_deleted": ["product_id"],
    "promocode_redeemed": [
        "promo_code",
        "promo_type_label",
        "reward_text",
        "reward_amount",
    ],
    "purchase_created": ["product_id", "status"],
    "referral_attached": ["referred_id", "referral_code"],
    "referred_signup": ["referrer_id", "referral_code"],
    "server_created": ["slug", "url"],
    "server_deleted": ["server_id", "server_name"],
    "server_link_removed": ["closed_message"],
    "server_link_updated": ["url"],
    "support_close": ["thread_id"],
    "support_reply": ["thread_id", "to"],
    "user_registered": ["referral_code"],
}


def _describe_user(user) -> str:
    parts: list[str] = []
    if getattr(user, "bot_nickname", None):
        parts.append(str(user.bot_nickname))
    if getattr(user, "username", None):
        parts.append(str(user.username))
    if getattr(user, "tg_username", None):
        parts.append(f"@{user.tg_username}")
    if getattr(user, "tg_id", None):
        parts.append(str(user.tg_id))
    return " / ".join(parts) if parts else str(getattr(user, "id", ""))


async def _demote_admin_via_logs(target_id: int, moderator_id: int, bot) -> bool:
    async with async_session() as session:
        admin = await session.scalar(select(Admin).where(Admin.telegram_id == target_id))
        if not admin or admin.is_root:
            return False

        await session.delete(admin)
        session.add(
            LogEntry(
                telegram_id=target_id,
                event_type="admin_demoted",
                message="Администратор разжалован",
                data={"demoted_by": moderator_id},
            )
        )
        await session.commit()

    try:
        is_target_admin = await is_admin(target_id)
        await bot.send_message(
            target_id,
            "⚠️ Вы лишены прав администратора.",
            reply_markup=main_menu(is_admin=is_target_admin),
        )
    except Exception:  # pragma: no cover - network errors
        logger.exception("Не удалось уведомить пользователя %s о разжаловании", target_id)

    return True


_CATEGORY_TITLES = {
    LogCategory.TOPUPS: "Пополнения",
    LogCategory.ACHIEVEMENTS: "Достижения",
    LogCategory.PURCHASES: "Покупки",
    LogCategory.PROMOCODES: "Промокоды",
    LogCategory.ADMIN_ACTIONS: "Админ-действия",
    LogCategory.SECURITY: "Безопасность",
}