from __future__ import annotations

import html
import logging
from datetime import datetime

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from sqlalchemy import select

from bot.config import ROOT_ADMIN_ID
from bot.db import Admin, LogEntry, async_session
from bot.keyboards.admin_keyboards import (
    LOGS_ACHIEVEMENTS_BUTTON,
    LOGS_ADMIN_PICK_BUTTON,
    LOGS_NEXT_BUTTON,
    LOGS_PREV_BUTTON,
    LOGS_REFRESH_BUTTON,
    LOGS_SEARCH_BUTTON,
    admin_logs_filters_inline,
    admin_logs_menu_kb,
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
from bot.services.user_search import find_user_by_query
from bot.states.admin_states import AdminLogsState
from bot.utils.time import to_msk


router = Router(name="admin_logs")
logger = logging.getLogger(__name__)


MAX_MESSAGE_LENGTH = 4096


async def is_admin(uid: int) -> bool:
    async with async_session() as session:
        return bool(await session.scalar(select(Admin).where(Admin.telegram_id == uid)))


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
) -> None:
    chunks = _split_html_text(text)
    if not chunks:
        return

    if len(chunks) == 1:
        await message.edit_text(chunks[0], parse_mode=parse_mode, reply_markup=reply_markup)
        return

    await message.edit_text(chunks[0], parse_mode=parse_mode)

    for chunk in chunks[1:-1]:
        await message.answer(chunk, parse_mode=parse_mode)

    await message.answer(chunks[-1], parse_mode=parse_mode, reply_markup=reply_markup)


@router.message(F.text == "📜 Логи")
async def enter_logs_menu(message: types.Message, state: FSMContext):
    if not message.from_user:
        return

    if not await is_admin(message.from_user.id):
        return await message.answer("⛔ У вас нет доступа", reply_markup=admin_main_menu_kb())

    await state.set_state(AdminLogsState.browsing)
    await state.update_data(
        category=LogCategory.TOPUPS.value,
        page=1,
        user_id=None,
        telegram_id=None,
        search_label=None,
        reply_keyboard_sent=False,
    )
    await _send_logs_message(message, state)


@router.message(AdminLogsState.browsing, F.text == LOGS_REFRESH_BUTTON)
async def refresh_logs(message: types.Message, state: FSMContext):
    if await _require_admin_message(message):
        await _send_logs_message(message, state)


@router.message(AdminLogsState.browsing, F.text == LOGS_NEXT_BUTTON)
async def next_page(message: types.Message, state: FSMContext):
    if not await _require_admin_message(message):
        return

    data = await state.get_data()
    current = int(data.get("page", 1))
    await state.update_data(page=current + 1)
    await _send_logs_message(message, state)


@router.message(AdminLogsState.browsing, F.text == LOGS_PREV_BUTTON)
async def previous_page(message: types.Message, state: FSMContext):
    if not await _require_admin_message(message):
        return

    data = await state.get_data()
    current = max(1, int(data.get("page", 1)) - 1)
    await state.update_data(page=current)
    await _send_logs_message(message, state)


@router.message(AdminLogsState.browsing, F.text == LOGS_SEARCH_BUTTON)
async def prompt_search(message: types.Message, state: FSMContext):
    if not await _require_admin_message(message):
        return

    await state.set_state(AdminLogsState.waiting_for_query)
    await message.answer("Введите ник в боте/username/ID/tg_username пользователя для поиска:")


@router.message(AdminLogsState.browsing, F.text == LOGS_ADMIN_PICK_BUTTON)
async def prompt_admin_search(message: types.Message, state: FSMContext):
    if not await _require_admin_message(message):
        return

    if not message.from_user or message.from_user.id != ROOT_ADMIN_ID:
        await message.answer("Только root-админ может выбирать администраторов")
        return

    await state.set_state(AdminLogsState.waiting_for_admin)
    await message.answer("Введите ник в боте/username/ID/tg_username администратора:")


@router.message(AdminLogsState.waiting_for_query)
async def handle_search_query(message: types.Message, state: FSMContext):
    await _handle_search_input(message, state, require_admin=False)


@router.message(AdminLogsState.waiting_for_admin)
async def handle_admin_search(message: types.Message, state: FSMContext):
    await _handle_search_input(message, state, require_admin=True)


@router.message(AdminLogsState.browsing, F.text == LOGS_ACHIEVEMENTS_BUTTON)
async def show_achievement_logs(message: types.Message, state: FSMContext):
    if not await _require_admin_message(message):
        return

    await state.update_data(
        category=LogCategory.ACHIEVEMENTS.value,
        page=1,
    )
    await _send_logs_message(message, state)


@router.callback_query(F.data.startswith("logs:category:"))
async def category_callback(call: types.CallbackQuery, state: FSMContext):
    if not await _require_admin_callback(call):
        return

    category_value = call.data.split(":", 2)[2]
    try:
        category = LogCategory(category_value)
    except ValueError:
        return await call.answer("Неизвестная категория", show_alert=True)

    await state.update_data(category=category.value, page=1)
    await _send_logs_callback(call, state)


@router.callback_query(F.data.startswith("logs:demote_confirm:"))
async def demote_confirm(call: types.CallbackQuery, state: FSMContext):
    if not call.from_user:
        return await call.answer()
    if call.from_user.id != ROOT_ADMIN_ID:
        return await call.answer("Недостаточно прав", show_alert=True)

    try:
        _, _, target_raw = (call.data or "").split(":", 2)
        target_id = int(target_raw)
    except (ValueError, AttributeError):
        return await call.answer("Некорректные данные", show_alert=True)

    if target_id == ROOT_ADMIN_ID:
        return await call.answer("Нельзя разжаловать root-админа", show_alert=True)

    success = await _demote_admin_via_logs(target_id, call.from_user.id, call.bot)
    if not success:
        return await call.answer("Не удалось разжаловать администратора", show_alert=True)

    await state.update_data(search_is_admin=False)
    await _send_logs_callback(call, state)
    await call.answer("Администратор разжалован")



async def _handle_search_input(
    message: types.Message,
    state: FSMContext,
    *,
    require_admin: bool,
) -> None:
    if not await _require_admin_message(message):
        return

    query_text = (message.text or "").strip()
    if not query_text:
        await message.answer("Введите непустой поисковый запрос")
        return

    user = await find_user_by_query(query_text)
    if not user:
        await message.answer("Пользователь не найден")
        return

    is_target_admin = await is_admin(user.tg_id)
    if require_admin and not is_target_admin:
        await message.answer("Этот пользователь не является администратором")
        return

    await state.update_data(
        user_id=user.id,
        telegram_id=user.tg_id,
        search_label=_describe_user(user),
        page=1,
    )
    await state.set_state(AdminLogsState.browsing)
    await _send_logs_message(message, state)


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


async def _send_logs_message(message: types.Message, state: FSMContext) -> None:
    if not message.from_user:
        return

    await state.set_state(AdminLogsState.browsing)
    await _ensure_reply_keyboard(message, state)
    text, markup, _ = await _prepare_logs_view(state, message.from_user.id)
    await message.answer(text, parse_mode="HTML", reply_markup=markup)


async def _send_logs_callback(call: types.CallbackQuery, state: FSMContext) -> None:
    if not call.message or not call.from_user:
        return

    text, markup, _ = await _prepare_logs_view(state, call.from_user.id)
    await send_chunked_html(
        call.message,
        text,
        parse_mode="HTML",
        reply_markup=markup,
    )


async def _prepare_logs_view(
    state: FSMContext, viewer_id: int
) -> tuple[str, types.InlineKeyboardMarkup, LogPage]:
    data = await state.get_data()
    category = _category_from_state(data)
    page_number = max(1, int(data.get("page", 1)))
    query = LogQuery(
        category=category,
        page=page_number,
        user_id=data.get("user_id"),
        telegram_id=data.get("telegram_id"),
    )
    page = await fetch_logs_page(query)
    text = _format_logs_text(page, category, data)
    markup = admin_logs_filters_inline(category)
    return text, markup, page


async def _ensure_reply_keyboard(message: types.Message, state: FSMContext) -> None:
    if not message.from_user:
        return

    data = await state.get_data()
    if data.get("reply_keyboard_sent"):
        return

    await message.answer(
        "Используйте клавиатуру ниже для навигации по логам.",
        reply_markup=admin_logs_menu_kb(is_root=message.from_user.id == ROOT_ADMIN_ID),
    )
    await state.update_data(reply_keyboard_sent=True)


def _category_from_state(data: dict) -> LogCategory:
    value = data.get("category") or LogCategory.TOPUPS.value
    try:
        return LogCategory(value)
    except ValueError:
        return LogCategory.TOPUPS


def _format_logs_text(page: LogPage, category: LogCategory, data: dict) -> str:
    lines = [
        f"📜 <b>{_CATEGORY_TITLES[category]}</b>",
        f"Период: последние {DEFAULT_LOGS_RANGE_HOURS} ч.",
        f"Страница {page.page}",
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

    hints = []
    if page.has_prev:
        hints.append("Есть предыдущая страница")
    if page.has_next:
        hints.append("Есть следующая страница")
    if hints:
        lines.extend(("", " / ".join(hints)))

    return "\n".join(lines)


def _format_record_line(position: int, record: LogRecord) -> str:
    timestamp = to_msk(record.created_at).strftime("%d.%m %H:%M")
    title = html.escape(record.message or record.event_type)

    user_bits: list[str] = []
    if record.telegram_id:
        user_bits.append(f"tg:<code>{record.telegram_id}</code>")
    if record.user_id:
        user_bits.append(f"id:{record.user_id}")
    suffix = f" ({' '.join(user_bits)})" if user_bits else ""

    data_preview = _format_data_preview(record.data)
    preview_line = f"\n    <i>{data_preview}</i>" if data_preview else ""

    return f"{position}. <b>{timestamp}</b> — {title}{suffix}{preview_line}"


def _format_data_preview(data: object) -> str:
    if not isinstance(data, dict) or not data:
        return ""
    items = list(data.items())[:2]
    formatted = [f"{html.escape(str(k))}={html.escape(str(v))}" for k, v in items]
    return ", ".join(formatted)


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
}