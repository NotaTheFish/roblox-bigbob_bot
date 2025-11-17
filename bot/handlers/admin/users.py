from __future__ import annotations

import logging
import math
from datetime import datetime, timezone
from html import escape
from typing import Sequence

from aiogram import Bot, F, Router, types
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import func, select

from bot.config import ROOT_ADMIN_ID
from bot.db import Admin, LogEntry, User, async_session
from backend.services.nuts import add_nuts, subtract_nuts
from bot.keyboards.admin_keyboards import (
    admin_demote_confirm_kb,
    admin_main_menu_kb,
    admin_users_menu_kb,
)
from bot.keyboards.main_menu import main_menu
from bot.keyboards.ban_appeal import ban_appeal_keyboard
from bot.services.user_blocking import (
    AdminBlockConfirmationRequiredError,
    AdminBlockPermissionError,
    block_user as block_user_record,
    unblock_user as unblock_user_record,
)
from bot.services.user_search import (
    SearchRenderOptions,
    find_user_by_query,
    render_search_profile,
)
from bot.services.user_titles import normalize_titles
from bot.states.admin_states import (
    AdminUsersState,
    GiveMoneyState,
    GiveTitleState,
    RemoveMoneyState,
    RemoveTitleState,
)
from bot.texts.block import (
    BAN_NOTIFICATION_TEXT,
    UNBLOCK_NOTIFICATION_TEXT,
)
from bot.utils.achievement_checker import check_achievements
from db.constants import BOT_USER_ID_PREFIX


router = Router(name="admin_users")
logger = logging.getLogger(__name__)


BANLIST_PAGE_SIZE = 1


# -------- Проверка админа --------
async def is_admin(uid: int) -> bool:
    async with async_session() as session:
        return bool(await session.scalar(select(Admin).where(Admin.telegram_id == uid)))


def _is_root_admin(user: types.User | None) -> bool:
    return bool(user and user.id == ROOT_ADMIN_ID)


# -------- Кнопки карточки пользователя --------
def user_card_kb(user_id, is_blocked, *, show_demote: bool = False):
    builder = InlineKeyboardBuilder()
    builder.button(
        text="➕ Выдать валюту", callback_data=f"give_money:{user_id}"
    )
    builder.button(
        text="➖ Удержать валюту", callback_data=f"remove_money:{user_id}"
    )
    if is_blocked:
        builder.button(
            text="✅ Разблокировать", callback_data=f"unblock_user:{user_id}"
        )
    else:
        builder.button(
            text="🚫 Заблокировать", callback_data=f"block_user:{user_id}"
        )
    builder.button(text="🎖 Выдать титул", callback_data=f"give_title:{user_id}")
    builder.button(text="🗑 Удалить титул", callback_data=f"remove_title:{user_id}")
    builder.button(text="⬅️ Назад", callback_data="admin_users")
    if show_demote:
        builder.button(
            text="⚠️ Разжаловать администратора",
            callback_data=f"demote_admin:{user_id}",
        )
    layout = [2, 1, 2, 1]
    if show_demote:
        layout.append(1)
    builder.adjust(*layout)
    return builder.as_markup()


def _banlist_navigation_kb(
    *, user_id: int | None, current_page: int, total_pages: int
):
    builder = InlineKeyboardBuilder()
    has_buttons = False

    if total_pages > 1:
        if current_page > 0:
            builder.button(
                text="⬅️ Предыдущий", callback_data=f"banlist:page:{current_page - 1}"
            )
            has_buttons = True
        if current_page < total_pages - 1:
            builder.button(
                text="➡️ Следующий", callback_data=f"banlist:page:{current_page + 1}"
            )
            has_buttons = True
        builder.adjust(2)

    if user_id is not None:
        builder.button(text="✅ Разбанить", callback_data=f"banlist:unban:{user_id}")
        builder.adjust(1)
        has_buttons = True

    return builder.as_markup() if has_buttons else None


async def _load_banlist_page(page: int, page_size: int = BANLIST_PAGE_SIZE):
    async with async_session() as session:
        total_blocked = await session.scalar(
            select(func.count()).select_from(User).where(User.is_blocked.is_(True))
        )
        total_blocked = total_blocked or 0

        if not total_blocked:
            return total_blocked, [], 0

        total_pages = math.ceil(total_blocked / page_size)
        current_page = max(0, min(page, total_pages - 1))

        users = (
            await session.scalars(
                select(User)
                .where(User.is_blocked.is_(True))
                .order_by(User.ban_notified_at.desc().nullslast(), User.id.desc())
                .offset(current_page * page_size)
                .limit(page_size)
            )
        ).all()

    return total_blocked, users, current_page


async def _render_banlist_page(
    message: types.Message,
    state: FSMContext,
    page: int,
    *,
    as_edit: bool = False,
):
    total_blocked, users, current_page = await _load_banlist_page(page)

    if not total_blocked or not users:
        text = (
            "🚫 <b>Бан-лист пуст</b>\n"
            "На данный момент нет заблокированных пользователей."
        )
        reply_markup = None
    else:
        total_pages = math.ceil(total_blocked / BANLIST_PAGE_SIZE)
        user = users[0]
        profile_text = render_search_profile(
            user,
            SearchRenderOptions(
                heading=(
                    f"<b>🚫 Бан-лист</b> — страница {current_page + 1}/{total_pages}"
                ),
                include_private_fields=True,
            ),
        )
        text = f"{profile_text}\n\nВсего заблокировано: {total_blocked}"
        reply_markup = _banlist_navigation_kb(
            user_id=user.tg_id,
            current_page=current_page,
            total_pages=total_pages,
        )

    if as_edit:
        await message.edit_text(text, parse_mode="HTML", reply_markup=reply_markup)
    else:
        await message.answer(text, parse_mode="HTML", reply_markup=reply_markup)

    await state.update_data(banlist_page=current_page)


def _shorten_title_label(text: str, limit: int = 32) -> str:
    text = (text or "").strip()
    if not text:
        return "Без названия"
    if len(text) <= limit:
        return text
    return f"{text[: limit - 1]}…"


def _remove_title_selection_kb(titles: Sequence[str]):
    builder = InlineKeyboardBuilder()
    for idx, title in enumerate(titles):
        builder.button(
            text=_shorten_title_label(title),
            callback_data=f"remove_title_pick:{idx}",
        )
    builder.button(text="✖️ Отмена", callback_data="remove_title_cancel")
    builder.adjust(1)
    return builder.as_markup()


def _remove_title_confirm_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Подтвердить", callback_data="remove_title_confirm")
    builder.button(text="↩️ Назад", callback_data="remove_title_back")
    builder.button(text="✖️ Отмена", callback_data="remove_title_cancel")
    builder.adjust(2, 1)
    return builder.as_markup()


def _admin_block_confirmation_kb(user_id: int):
    builder = InlineKeyboardBuilder()
    builder.button(
        text="✅ Подтвердить блокировку",
        callback_data=f"confirm_block_admin:{user_id}",
    )
    builder.button(text="✖️ Отмена", callback_data="cancel_block_admin")
    builder.adjust(1)
    return builder.as_markup()


async def _prompt_admin_block_confirmation(call: types.CallbackQuery, user_id: int) -> None:
    text = (
        "⚠️ <b>Подтверждение блокировки администратора</b>\n"
        f"Пользователь <code>{user_id}</code> является администратором.\n"
        "Подтвердите блокировку перед продолжением."
    )

    if call.message:
        await call.message.answer(
            text,
            parse_mode="HTML",
            reply_markup=_admin_block_confirmation_kb(user_id),
        )
    elif call.from_user:
        await call.bot.send_message(
            call.from_user.id,
            text,
            parse_mode="HTML",
            reply_markup=_admin_block_confirmation_kb(user_id),
        )

    await call.answer("Требуется подтверждение", show_alert=True)


async def _process_block_user(
    call: types.CallbackQuery, user_id: int, *, confirmed: bool
) -> None:
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == user_id))
        if not user:
            return await call.answer("Пользователь не найден", show_alert=True)

        operator_admin = await session.scalar(
            select(Admin).where(Admin.telegram_id == call.from_user.id)
        )

        try:
            await block_user_record(
                session,
                user=user,
                operator_admin=operator_admin,
                confirmed=confirmed,
            )
        except AdminBlockPermissionError:
            return await call.answer(
                "❌ У вас нет прав банить администраторов", show_alert=True
            )
        except AdminBlockConfirmationRequiredError:
            await _prompt_admin_block_confirmation(call, user_id)
            return

        notified = False
        try:
            await call.bot.send_message(
                user_id,
                BAN_NOTIFICATION_TEXT,
                reply_markup=ban_appeal_keyboard(),
            )
            notified = True
        except Exception:  # pragma: no cover - ignore delivery errors
            logger.debug("Failed to notify user %s about block", user_id)

        if notified:
            user.ban_notified_at = datetime.now(timezone.utc)
            await session.commit()

    if call.message:
        await call.message.edit_text("✅ Пользователь заблокирован")
    else:
        await call.answer("✅ Пользователь заблокирован", show_alert=True)


async def _process_unblock_user(
    call: types.CallbackQuery, user_id: int, *, notify_operator: bool = True
) -> bool:
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == user_id))
        if not user:
            await call.answer("Пользователь не найден", show_alert=True)
            return False

        await unblock_user_record(session, user=user)

        try:
            await call.bot.send_message(
                user_id,
                UNBLOCK_NOTIFICATION_TEXT,
            )
        except Exception:  # pragma: no cover - ignore delivery errors
            logger.debug("Failed to notify user %s about unblock", user_id)

    if notify_operator:
        if call.message:
            await call.message.edit_text("✅ Пользователь разблокирован")
        else:
            await call.answer("✅ Пользователь разблокирован", show_alert=True)

    return True


async def _is_demotable_admin(user_id: int) -> bool:
    async with async_session() as session:
        admin = await session.scalar(select(Admin).where(Admin.telegram_id == user_id))
        return bool(admin and not admin.is_root)


async def _should_show_demote_button(operator_id: int | None, target_id: int) -> bool:
    if operator_id != ROOT_ADMIN_ID:
        return False
    if target_id == ROOT_ADMIN_ID:
        return False
    return await _is_demotable_admin(target_id)


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


# -------- /admin_users — список --------
async def _send_users_list(message: types.Message):
    async with async_session() as session:
        users = (
            await session.scalars(select(User).order_by(User.nuts_balance.desc()).limit(50))
        ).all()

    if not users:
        return await message.answer(
            "Пользователей пока нет.",
            reply_markup=admin_users_menu_kb(),
        )

    text = "👥 <b>ТОП 50 пользователей по орешкам</b>\n\n"
    for u in users:
        base_name = u.bot_nickname or u.username
        if not base_name and u.tg_username:
            base_name = f"@{u.tg_username}"
        display_name = escape(base_name or "—")
        text += (
            "• "
            f"TG ID: <code>{u.tg_id}</code> | "
            f"bot_user_id: <code>{escape(u.bot_user_id)}</code> | "
            f"ник: <code>{display_name}</code> — 🥜 {u.nuts_balance}\n"
        )

    text += (
        "\n🔎 Отправьте TG ID, ID бота "
        f"(например, {BOT_USER_ID_PREFIX}12345), ник в боте или username для поиска"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=admin_users_menu_kb())


@router.message(~StateFilter(GiveMoneyState.waiting_for_amount), F.text == "👥 Пользователи")
async def admin_users_entry(message: types.Message, state: FSMContext):
    if not message.from_user:
        return

    if not await is_admin(message.from_user.id):
        return

    await state.set_state(AdminUsersState.searching)
    await _send_users_list(message)


@router.message(StateFilter(AdminUsersState.searching), F.text == "🔁 Обновить список")
async def admin_users_list(message: types.Message):
    if not message.from_user:
        return

    if not await is_admin(message.from_user.id):
        return

    await _send_users_list(message)


@router.message(
    StateFilter(AdminUsersState.searching, AdminUsersState.banlist), F.text == "↩️ Назад"
)
async def admin_users_back(message: types.Message, state: FSMContext):
    if not message.from_user:
        return

    if not await is_admin(message.from_user.id):
        return

    await state.clear()
    await message.answer(
        "👑 <b>Админ-панель</b>\nВыберите раздел:",
        reply_markup=admin_main_menu_kb(),
    )


@router.message(
    StateFilter(AdminUsersState.searching, AdminUsersState.banlist),
    F.text == "🚫 Бан-лист",
)
async def admin_users_banlist(message: types.Message, state: FSMContext):
    if not message.from_user:
        return

    if not await is_admin(message.from_user.id):
        return

    await state.set_state(AdminUsersState.banlist)
    await _render_banlist_page(message, state, page=0)


# -------- Поиск пользователя --------
@router.message(
    StateFilter(AdminUsersState.searching),
    F.text,
    ~F.text.in_({"👥 Пользователи", "🔁 Обновить список", "↩️ Назад", "↩️ В меню"}),
)
async def admin_search_user(message: types.Message):
    if not message.from_user:
        return

    if not await is_admin(message.from_user.id):
        return  # <--- заменили raise SkipHandler()

    query = message.text.strip().lstrip("@")
    if not query:
        return await message.reply(
            (
                "Введите TG ID, ник в боте, username или ID бота "
                f"(например, {BOT_USER_ID_PREFIX}12345) для поиска"
            ),
            reply_markup=admin_users_menu_kb(),
        )

    user = await find_user_by_query(query, include_blocked=True)

    if not user:
        return await message.reply(
            "❌ Пользователь не найден",
            reply_markup=admin_users_menu_kb(),
        )

    profile_text = render_search_profile(
        user,
        SearchRenderOptions(
            heading="<b>👤 Пользователь найден</b>",
            include_private_fields=True,
        ),
    )

    show_demote = await _should_show_demote_button(message.from_user.id, user.tg_id)

    await message.reply(
        profile_text,
        parse_mode="HTML",
        reply_markup=user_card_kb(
            user.tg_id,
            user.is_blocked,
            show_demote=show_demote,
        ),
    )


# -------- Управление пользователем: блок/разблок/выдача -------
@router.callback_query(
    F.data.startswith("give_money")
    | F.data.startswith("remove_money")
    | F.data.startswith("block_user")
    | F.data.startswith("unblock_user")
    | F.data.startswith("give_title")
)
async def user_management_actions(call: types.CallbackQuery, state: FSMContext):
    if not call.from_user:
        return await call.answer("Нет доступа", show_alert=True)

    if not await is_admin(call.from_user.id):
        return await call.answer("Нет доступа", show_alert=True)

    action, user_id = call.data.split(":")
    user_id = int(user_id)

    # Выдача денег
    if action == "give_money":
        await call.message.answer(
            f"Введите сумму для пользователя <code>{user_id}</code>:", parse_mode="HTML"
        )
        await state.update_data(target_user_id=user_id)
        await state.set_state(GiveMoneyState.waiting_for_amount)
        return

    if action == "remove_money":
        await call.message.answer(
            f"Введите сумму удержания для пользователя <code>{user_id}</code>:",
            parse_mode="HTML",
        )
        await state.update_data(target_user_id=user_id)
        await state.set_state(RemoveMoneyState.waiting_for_amount)
        return

    if action == "give_title":
        await call.message.answer(
            f"Введите текст титула для пользователя <code>{user_id}</code>:",
            parse_mode="HTML",
        )
        await state.update_data(target_user_id=user_id)
        await state.set_state(GiveTitleState.waiting_for_title)
        return

    if action == "block_user":
        await _process_block_user(call, user_id, confirmed=False)
        return

    if action == "unblock_user":
        await _process_unblock_user(call, user_id)
        return


@router.callback_query(F.data.startswith("demote_admin:"))
async def demote_admin_prompt(call: types.CallbackQuery):
    if not call.from_user:
        return await call.answer("Нет доступа", show_alert=True)

    if not _is_root_admin(call.from_user):
        return await call.answer("Недостаточно прав", show_alert=True)

    target_raw = call.data.split(":", maxsplit=1)[1]
    try:
        target_id = int(target_raw)
    except ValueError:
        return await call.answer("Некорректный идентификатор", show_alert=True)

    if target_id == ROOT_ADMIN_ID:
        return await call.answer("Нельзя разжаловать root-админа", show_alert=True)

    if not await _is_demotable_admin(target_id):
        return await call.answer("Пользователь не является администратором", show_alert=True)

    text = (
        "⚠️ <b>Разжаловать администратора</b>\n"
        f"Подтвердите разжалование пользователя <code>{target_id}</code>."
    )

    if call.message:
        await call.message.answer(
            text,
            parse_mode="HTML",
            reply_markup=admin_demote_confirm_kb(target_id),
        )
    else:
        await call.bot.send_message(
            call.from_user.id,
            text,
            parse_mode="HTML",
            reply_markup=admin_demote_confirm_kb(target_id),
        )

    await call.answer()


@router.callback_query(F.data == "demote_admin_cancel")
async def demote_admin_cancel(call: types.CallbackQuery):
    if not call.from_user:
        return await call.answer("Нет доступа", show_alert=True)

    if not _is_root_admin(call.from_user):
        return await call.answer("Недостаточно прав", show_alert=True)

    if call.message:
        await call.message.edit_text("Действие отменено")

    await call.answer("Действие отменено")


@router.callback_query(F.data.startswith("demote_admin_confirm:"))
async def demote_admin_confirm(call: types.CallbackQuery):
    if not call.from_user:
        return await call.answer("Нет доступа", show_alert=True)

    if not _is_root_admin(call.from_user):
        return await call.answer("Недостаточно прав", show_alert=True)

    target_raw = call.data.split(":", maxsplit=1)[1]
    try:
        target_id = int(target_raw)
    except ValueError:
        return await call.answer("Некорректный идентификатор", show_alert=True)

    success = await _demote_admin(target_id, call.from_user.id, call.bot)

    if call.message:
        await call.message.edit_text(
            "✅ Администратор разжалован"
            if success
            else "❌ Не удалось разжаловать администратора",
        )

    await call.answer(
        "Администратор разжалован" if success else "Не удалось",
        show_alert=not success,
    )


@router.callback_query(F.data.startswith("banlist:page:"))
async def admin_banlist_paginate(call: types.CallbackQuery, state: FSMContext):
    if not call.from_user:
        return await call.answer("Нет доступа", show_alert=True)

    if not await is_admin(call.from_user.id):
        return await call.answer("Нет доступа", show_alert=True)

    current_state = await state.get_state()
    if current_state != AdminUsersState.banlist.state:
        return await call.answer("Откройте бан-лист заново", show_alert=True)

    try:
        _, _, page_raw = call.data.split(":", maxsplit=2)
        page = int(page_raw)
    except (ValueError, AttributeError):
        return await call.answer("Некорректный запрос", show_alert=True)

    if not call.message:
        return await call.answer("Сообщение недоступно", show_alert=True)

    await _render_banlist_page(call.message, state, page=page, as_edit=True)
    await call.answer()


@router.callback_query(F.data.startswith("banlist:unban:"))
async def admin_banlist_unban(call: types.CallbackQuery, state: FSMContext):
    if not call.from_user:
        return await call.answer("Нет доступа", show_alert=True)

    if not await is_admin(call.from_user.id):
        return await call.answer("Нет доступа", show_alert=True)

    current_state = await state.get_state()
    if current_state != AdminUsersState.banlist.state:
        return await call.answer("Откройте бан-лист заново", show_alert=True)

    try:
        _prefix, _action, user_id_raw = call.data.split(":", maxsplit=2)
        user_id = int(user_id_raw)
    except (ValueError, AttributeError):
        return await call.answer("Некорректный запрос", show_alert=True)

    success = await _process_unblock_user(call, user_id, notify_operator=False)
    if not success:
        return

    await call.answer("✅ Пользователь разблокирован", show_alert=True)

    data = await state.get_data()
    page = data.get("banlist_page", 0)

    if call.message:
        await _render_banlist_page(call.message, state, page=page, as_edit=True)


@router.callback_query(F.data.startswith("confirm_block_admin:"))
async def confirm_block_admin_block(call: types.CallbackQuery, state: FSMContext):
    if not call.from_user:
        return await call.answer("Нет доступа", show_alert=True)

    if not await is_admin(call.from_user.id):
        return await call.answer("Нет доступа", show_alert=True)

    try:
        _, user_id_raw = call.data.split(":", maxsplit=1)
        user_id = int(user_id_raw)
    except (ValueError, AttributeError):
        return await call.answer("Некорректный запрос", show_alert=True)

    await _process_block_user(call, user_id, confirmed=True)


@router.callback_query(F.data == "cancel_block_admin")
async def cancel_block_admin(call: types.CallbackQuery, state: FSMContext):
    if not call.from_user:
        return await call.answer("Нет доступа", show_alert=True)

    if not await is_admin(call.from_user.id):
        return await call.answer("Нет доступа", show_alert=True)

    if call.message:
        await call.message.edit_text("❌ Блокировка администратора отменена")

    await call.answer()


@router.callback_query(F.data.startswith("remove_title:"))
async def remove_title_start(call: types.CallbackQuery, state: FSMContext):
    if not call.from_user:
        return await call.answer("Нет доступа", show_alert=True)

    if not await is_admin(call.from_user.id):
        return await call.answer("Нет доступа", show_alert=True)

    try:
        _action, user_id_raw = call.data.split(":", maxsplit=1)
        user_id = int(user_id_raw)
    except (ValueError, AttributeError):
        return await call.answer("Некорректный запрос", show_alert=True)

    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == user_id))

    if not user:
        return await call.answer("Пользователь не найден", show_alert=True)

    titles = normalize_titles(user.titles)
    if not titles:
        return await call.answer("У пользователя нет титулов", show_alert=True)

    await state.set_state(RemoveTitleState.choosing_title)
    await state.update_data(target_user_id=user_id, title_options=titles)

    prompt = (
        "🗑 <b>Удаление титула</b>\n"
        f"Выберите титул для удаления у пользователя <code>{user_id}</code>:"
    )
    if call.message:
        await call.message.answer(
            prompt,
            parse_mode="HTML",
            reply_markup=_remove_title_selection_kb(titles),
        )
    await call.answer()


@router.callback_query(
    StateFilter(RemoveTitleState.choosing_title),
    F.data.startswith("remove_title_pick:"),
)
async def remove_title_pick(call: types.CallbackQuery, state: FSMContext):
    if not call.from_user:
        return await call.answer("Нет доступа", show_alert=True)

    if not await is_admin(call.from_user.id):
        return await call.answer("Нет доступа", show_alert=True)

    data = await state.get_data()
    titles: list[str] = data.get("title_options", [])
    try:
        _, idx_raw = call.data.split(":", maxsplit=1)
        idx = int(idx_raw)
    except (ValueError, AttributeError):
        return await call.answer("Некорректный выбор", show_alert=True)

    if idx < 0 or idx >= len(titles):
        return await call.answer("Некорректный выбор", show_alert=True)

    selected_title = titles[idx]
    await state.update_data(selected_title=selected_title)
    await state.set_state(RemoveTitleState.confirming)

    user_id = data.get("target_user_id")
    if not user_id:
        await state.clear()
        return await call.answer("Данные недоступны", show_alert=True)

    if call.message:
        await call.message.edit_text(
            (
                "⚠️ Подтверждение удаления\n"
                f"Удалить титул <b>{escape(selected_title)}</b> у пользователя "
                f"<code>{user_id}</code>?"
            ),
            parse_mode="HTML",
            reply_markup=_remove_title_confirm_kb(),
        )

    await call.answer()


@router.callback_query(
    StateFilter(RemoveTitleState.confirming), F.data == "remove_title_back"
)
async def remove_title_back(call: types.CallbackQuery, state: FSMContext):
    if not call.from_user:
        return await call.answer("Нет доступа", show_alert=True)

    if not await is_admin(call.from_user.id):
        return await call.answer("Нет доступа", show_alert=True)

    data = await state.get_data()
    titles: list[str] = data.get("title_options", [])
    user_id = data.get("target_user_id")
    if not titles or not user_id:
        await state.clear()
        if call.message:
            await call.message.edit_text("❌ Удаление титула отменено")
        return await call.answer()

    await state.update_data(selected_title=None)
    await state.set_state(RemoveTitleState.choosing_title)

    if call.message:
        await call.message.edit_text(
            (
                "🗑 <b>Удаление титула</b>\n"
                f"Выберите титул для удаления у пользователя <code>{user_id}</code>:"
            ),
            parse_mode="HTML",
            reply_markup=_remove_title_selection_kb(titles),
        )

    await call.answer()


@router.callback_query(
    StateFilter(RemoveTitleState.choosing_title, RemoveTitleState.confirming),
    F.data == "remove_title_cancel",
)
async def remove_title_cancel(call: types.CallbackQuery, state: FSMContext):
    if not call.from_user:
        return await call.answer("Нет доступа", show_alert=True)

    if not await is_admin(call.from_user.id):
        return await call.answer("Нет доступа", show_alert=True)

    await state.clear()
    if call.message:
        await call.message.edit_text("❌ Удаление титула отменено")
    await call.answer()


@router.callback_query(
    StateFilter(RemoveTitleState.confirming), F.data == "remove_title_confirm"
)
async def remove_title_confirm(call: types.CallbackQuery, state: FSMContext):
    if not call.from_user:
        return await call.answer("Нет доступа", show_alert=True)

    if not await is_admin(call.from_user.id):
        return await call.answer("Нет доступа", show_alert=True)

    data = await state.get_data()
    target_user_id = data.get("target_user_id")
    selected_title: str | None = data.get("selected_title")
    if not target_user_id or not selected_title:
        await state.clear()
        if call.message:
            await call.message.edit_text("❌ Данные удаления потеряны")
        return await call.answer()

    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == target_user_id))
        if not user:
            await state.clear()
            if call.message:
                await call.message.edit_text("❌ Пользователь не найден")
            return await call.answer()

        titles = normalize_titles(user.titles)
        if selected_title not in titles:
            await state.clear()
            if call.message:
                await call.message.edit_text("⚠️ Титул уже удалён")
            return await call.answer()

        titles = [t for t in titles if t != selected_title]
        user.titles = titles
        if user.selected_title == selected_title:
            user.selected_title = None

        await session.commit()

    logger.info(
        "Admin %s removed title '%s' from user %s",
        call.from_user.id,
        selected_title,
        target_user_id,
    )

    try:
        await call.bot.send_message(
            target_user_id,
            (
                "⚠️ Ваш титул <b>{title}</b> был удалён администратором."
            ).format(title=escape(selected_title)),
            parse_mode="HTML",
        )
    except Exception:  # pragma: no cover - ignore delivery errors
        logger.debug(
            "Failed to notify user %s about removed title %s",
            target_user_id,
            selected_title,
        )

    if call.message:
        await call.message.edit_text(
            (
                "✅ Титул <b>{title}</b> удалён у пользователя "
                "<code>{user_id}</code>"
            ).format(title=escape(selected_title), user_id=target_user_id),
            parse_mode="HTML",
        )

    await state.clear()
    await call.answer()


# -------- Процесс выдачи валюты --------
@router.message(StateFilter(GiveMoneyState.waiting_for_amount))
async def process_money_amount(message: types.Message, state: FSMContext):
    if not message.from_user:
        await state.clear()
        return

    if not await is_admin(message.from_user.id):
        return await message.reply("⛔ Нет доступа")

    try:
        amount = int(message.text)
        if amount <= 0 or amount > 1_000_000:
            return await message.reply("❌ Введите сумму от 1 до 1,000,000")
    except ValueError:
        return await message.reply("❌ Нужно число")

    data = await state.get_data()
    user_id = data.get("target_user_id")
    if not user_id:
        await state.clear()
        return await message.reply("Ошибка: ID пользователя потерян")

    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == user_id))
        if not user:
            await state.clear()
            return await message.reply("⛔ Пользователь не найден")

        await add_nuts(
            session,
            user=user,
            amount=amount,
            source="admin_grant",
            transaction_type="admin_grant",
            reason="Выдача валюты администратором",
        )
        await session.commit()

    await check_achievements(user)

    await message.reply(
        f"✅ Выдано <b>{amount}</b> монет пользователю <code>{user_id}</code>", parse_mode="HTML"
    )

    try:
        await message.bot.send_message(
            user_id, f"🎁 Вам выдано <b>{amount}</b> монет администратором!"
        )
    except Exception:
        pass

    if "target_user_id" in data:
        data.pop("target_user_id")
        await state.set_data(data)

    await state.clear()


@router.message(StateFilter(GiveTitleState.waiting_for_title))
async def process_give_title(message: types.Message, state: FSMContext):
    if not message.from_user:
        await state.clear()
        return

    if not await is_admin(message.from_user.id):
        return await message.reply("⛔ Нет доступа")

    title_text = (message.text or "").strip()
    if not title_text:
        return await message.reply("❌ Титул не может быть пустым")
    if len(title_text) > 255:
        return await message.reply("❌ Титул должен быть короче 255 символов")

    data = await state.get_data()
    target_user_id = data.get("target_user_id")
    if not target_user_id:
        await state.clear()
        return await message.reply("Ошибка: пользователь не выбран")

    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == target_user_id))
        if not user:
            await state.clear()
            return await message.reply("⛔ Пользователь не найден")

        titles = normalize_titles(user.titles)
        titles = [t for t in titles if t != title_text]
        titles.append(title_text)
        user.titles = titles
        if not user.selected_title:
            user.selected_title = title_text
        await session.commit()

    await message.reply(
        (
            f"✅ Титул <b>{title_text}</b> добавлен пользователю "
            f"<code>{target_user_id}</code>"
        ),
        parse_mode="HTML",
    )

    try:
        await message.bot.send_message(
            target_user_id,
            f"🏅 Вам присвоен новый титул: <b>{title_text}</b>",
            parse_mode="HTML",
        )
    except Exception:
        logger.warning("Не удалось уведомить пользователя %s о новом титуле", target_user_id)

    await state.clear()


@router.message(StateFilter(RemoveMoneyState.waiting_for_amount))
async def process_remove_amount(message: types.Message, state: FSMContext):
    if not message.from_user:
        await state.clear()
        return

    if not await is_admin(message.from_user.id):
        return await message.reply("⛔ Нет доступа")

    try:
        amount = int(message.text)
        if amount <= 0:
            return await message.reply("❌ Введите сумму больше 0")
    except ValueError:
        return await message.reply("❌ Нужно число")

    data = await state.get_data()
    target_user_id = data.get("target_user_id")
    if not target_user_id:
        await state.clear()
        return await message.reply("Ошибка: ID пользователя потерян")

    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == target_user_id))
        if not user:
            await state.clear()
            return await message.reply("⛔ Пользователь не найден")

        if (user.nuts_balance or 0) - amount < 0:
            return await message.reply(
                "❌ Нельзя удержать больше, чем есть на балансе пользователя"
            )

    await state.update_data(remove_amount=amount)
    await state.set_state(RemoveMoneyState.waiting_for_reason)
    await message.reply("Введите причину удержания:")


@router.message(StateFilter(RemoveMoneyState.waiting_for_reason))
async def process_remove_reason(message: types.Message, state: FSMContext):
    if not message.from_user:
        await state.clear()
        return

    if not await is_admin(message.from_user.id):
        return await message.reply("⛔ Нет доступа")

    data = await state.get_data()
    target_user_id = data.get("target_user_id")
    remove_amount = data.get("remove_amount")
    if not target_user_id or not remove_amount:
        await state.clear()
        return await message.reply("Ошибка: данные удержания потеряны")

    reason = message.text.strip()
    if not reason:
        return await message.reply("❌ Причина не может быть пустой")

    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == target_user_id))
        if not user:
            await state.clear()
            return await message.reply("⛔ Пользователь не найден")

        if (user.nuts_balance or 0) - remove_amount < 0:
            await state.clear()
            return await message.reply(
                "❌ Баланс пользователя изменился, удержание невозможно"
            )
        await subtract_nuts(
            session,
            user=user,
            amount=remove_amount,
            source="admin_debit",
            transaction_type="admin_debit",
            reason=reason,
        )
        await session.commit()

    logger.info(
        "Admin %s removed %s coins from user %s for reason: %s",
        message.from_user.id,
        remove_amount,
        target_user_id,
        reason,
    )

    try:
        await message.bot.send_message(
            target_user_id,
            (
                "⚠️ С вашего баланса удержано "
                f"<b>{remove_amount}</b> монет.\nПричина: {reason}"
            ),
            parse_mode="HTML",
        )
    except Exception:
        logger.warning("Не удалось отправить сообщение пользователю %s", target_user_id)

    await message.reply(
        (
            f"✅ Удержано <b>{remove_amount}</b> монет у пользователя "
            f"<code>{target_user_id}</code>.\nПричина: {reason}"
        ),
        parse_mode="HTML",
    )

    await state.clear()
