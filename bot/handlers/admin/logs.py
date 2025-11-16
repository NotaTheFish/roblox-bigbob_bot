from __future__ import annotations

import html
import logging
from datetime import datetime

from aiogram import Bot, F, Router, types
from aiogram.fsm.context import FSMContext
from sqlalchemy import select

from bot.config import ROOT_ADMIN_ID
from bot.db import Admin, LogEntry, async_session
from bot.keyboards.admin_keyboards import (
    LOGS_ADMIN_PICK_BUTTON,
    LOGS_NEXT_BUTTON,
    LOGS_PREV_BUTTON,
    LOGS_REFRESH_BUTTON,
    LOGS_RESET_FILTER_BUTTON,
    LOGS_SEARCH_BUTTON,
    admin_logs_demote_confirm_kb,
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


async def is_admin(uid: int) -> bool:
    async with async_session() as session:
        return bool(await session.scalar(select(Admin).where(Admin.telegram_id == uid)))


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
        search_is_admin=False,
        demote_pending=False,
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
    await state.update_data(page=current + 1, demote_pending=False)
    await _send_logs_message(message, state)


@router.message(AdminLogsState.browsing, F.text == LOGS_PREV_BUTTON)
async def previous_page(message: types.Message, state: FSMContext):
    if not await _require_admin_message(message):
        return

    data = await state.get_data()
    current = max(1, int(data.get("page", 1)) - 1)
    await state.update_data(page=current, demote_pending=False)
    await _send_logs_message(message, state)


@router.message(AdminLogsState.browsing, F.text == LOGS_RESET_FILTER_BUTTON)
async def reset_filters(message: types.Message, state: FSMContext):
    if not await _require_admin_message(message):
        return

    data = await state.get_data()
    if not data.get("user_id") and not data.get("telegram_id"):
        await message.answer("Фильтр не активен")
        return

    await state.update_data(
        user_id=None,
        telegram_id=None,
        search_label=None,
        search_is_admin=False,
        demote_pending=False,
        page=1,
    )
    await _send_logs_message(message, state)


@router.message(AdminLogsState.browsing, F.text == LOGS_SEARCH_BUTTON)
async def prompt_search(message: types.Message, state: FSMContext):
    if not await _require_admin_message(message):
        return

    await state.set_state(AdminLogsState.waiting_for_query)
    await message.answer("Введите username/ID/tg_username пользователя для поиска:")


@router.message(AdminLogsState.browsing, F.text == LOGS_ADMIN_PICK_BUTTON)
async def prompt_admin_search(message: types.Message, state: FSMContext):
    if not await _require_admin_message(message):
        return

    if not message.from_user or message.from_user.id != ROOT_ADMIN_ID:
        await message.answer("Только root-админ может выбирать администраторов")
        return

    await state.set_state(AdminLogsState.waiting_for_admin)
    await message.answer("Введите username/ID/tg_username администратора:")


@router.message(AdminLogsState.waiting_for_query)
async def handle_search_query(message: types.Message, state: FSMContext):
    await _handle_search_input(message, state, require_admin=False)


@router.message(AdminLogsState.waiting_for_admin)
async def handle_admin_search(message: types.Message, state: FSMContext):
    await _handle_search_input(message, state, require_admin=True)


@router.callback_query(F.data.startswith("logs:category:"))
async def category_callback(call: types.CallbackQuery, state: FSMContext):
    if not await _require_admin_callback(call):
        return

    category_value = call.data.split(":", 2)[2]
    try:
        category = LogCategory(category_value)
    except ValueError:
        return await call.answer("Неизвестная категория", show_alert=True)

    await state.update_data(category=category.value, page=1, demote_pending=False)
    await _send_logs_callback(call, state)


@router.callback_query(F.data.startswith("logs:demote:"))
async def demote_prompt(call: types.CallbackQuery, state: FSMContext):
    if not await _require_admin_callback(call):
        return

    if not call.from_user or call.from_user.id != ROOT_ADMIN_ID:
        return await call.answer("Недостаточно прав", show_alert=True)

    target_raw = call.data.split(":", 2)[2]
    try:
        target_id = int(target_raw)
    except ValueError:
        return await call.answer("Некорректный идентификатор", show_alert=True)

    data = await state.get_data()
    if not data.get("search_is_admin") or data.get("telegram_id") != target_id:
        return await call.answer("Выберите администратора перед действием", show_alert=True)

    await state.update_data(demote_pending=True)
    text, _, _ = await _prepare_logs_view(state, call.from_user.id)
    warning_text = f"{text}\n\n⚠️ Подтвердите разжалование администратора."
    await call.message.edit_text(
        warning_text,
        parse_mode="HTML",
        reply_markup=admin_logs_demote_confirm_kb(target_id),
    )
    await call.answer()


@router.callback_query(F.data == "logs:demote_cancel")
async def demote_cancel(call: types.CallbackQuery, state: FSMContext):
    if not await _require_admin_callback(call):
        return

    await state.update_data(demote_pending=False)
    await _send_logs_callback(call, state)
    await call.answer("Действие отменено")


@router.callback_query(F.data.startswith("logs:demote_confirm:"))
async def demote_confirm(call: types.CallbackQuery, state: FSMContext):
    if not await _require_admin_callback(call):
        return

    if not call.from_user or call.from_user.id != ROOT_ADMIN_ID:
        return await call.answer("Недостаточно прав", show_alert=True)

    target_raw = call.data.split(":", 2)[2]
    try:
        target_id = int(target_raw)
    except ValueError:
        return await call.answer("Некорректный идентификатор", show_alert=True)

    success = await _demote_admin(target_id, call.from_user.id, call.bot)
    if not success:
        await state.update_data(demote_pending=False, search_is_admin=False)
        await _send_logs_callback(call, state)
        return await call.answer("Администратор не найден или уже разжалован", show_alert=True)

    await state.update_data(demote_pending=False, search_is_admin=False)
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
        search_is_admin=is_target_admin,
        demote_pending=False,
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
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=markup)


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
    markup = admin_logs_filters_inline(
        category,
        show_demote=_can_show_demote(viewer_id, data),
        demote_target=data.get("telegram_id"),
    )
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


def _can_show_demote(viewer_id: int, data: dict) -> bool:
    if viewer_id != ROOT_ADMIN_ID:
        return False
    if not data.get("search_is_admin"):
        return False
    target_id = data.get("telegram_id")
    if not target_id or target_id == ROOT_ADMIN_ID or target_id == viewer_id:
        return False
    if data.get("demote_pending"):
        return False
    return True


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
    if getattr(user, "username", None):
        parts.append(str(user.username))
    if getattr(user, "tg_username", None):
        parts.append(f"@{user.tg_username}")
    if getattr(user, "tg_id", None):
        parts.append(str(user.tg_id))
    return " / ".join(parts) if parts else str(getattr(user, "id", ""))


async def _demote_admin(target_id: int, moderator_id: int, bot: Bot) -> bool:
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
        is_admin_now = await is_admin(target_id)
        await bot.send_message(
            target_id,
            "⚠️ Вы лишены прав администратора.",
            reply_markup=main_menu(is_admin=is_admin_now),
        )
    except Exception:  # pragma: no cover - network errors
        logger.exception("Не удалось уведомить пользователя %s о разжаловании", target_id)

    return True


_CATEGORY_TITLES = {
    LogCategory.TOPUPS: "Пополнения",
    LogCategory.SPENDINGS: "Траты",
    LogCategory.PURCHASES: "Покупки",
    LogCategory.PROMOCODES: "Промокоды",
    LogCategory.ADMIN_ACTIONS: "Админ-действия",
}