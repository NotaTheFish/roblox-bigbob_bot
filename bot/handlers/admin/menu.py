from __future__ import annotations

import logging

from aiogram import F, Router, types
from aiogram.filters import Command, Filter, StateFilter
from aiogram.fsm.context import FSMContext
from sqlalchemy import select

from bot.config import ROOT_ADMIN_ID
from bot.db import Admin, async_session
from bot.keyboards.admin_keyboards import admin_main_menu_kb
from bot.keyboards.main_menu import main_menu
from bot.states.server_states import ServerManageState
from bot.services.admin_access import is_admin
from bot.services.user_blocking import unblock_blocked_admins


router = Router(name="admin_menu")
logger = logging.getLogger(__name__)


class OutsideServerManageState(Filter):
    async def __call__(self, message: types.Message, state: FSMContext) -> bool:
        current_state = await state.get_state()
        if not current_state:
            return True
        return not current_state.startswith(f"{ServerManageState.__name__}:")


# Команда для входа в админ панель
async def _send_admin_panel(message: types.Message, state: FSMContext | None = None):
    fsm_state = await state.get_state() if state else None
    user_id = message.from_user.id if message.from_user else None
    logger.info(
        "_send_admin_panel called",
        extra={"user_id": user_id, "fsm_state": fsm_state},
    )

    if not message.from_user:
        logger.info(
            "Message has no from_user, aborting admin panel send",
            extra={"fsm_state": fsm_state},
        )
        return

    logger.info(
        "Checking admin access",
        extra={"user_id": user_id, "fsm_state": fsm_state},
    )
    has_access = await is_admin(user_id)
    logger.info(
        "Admin access check completed",
        extra={"user_id": user_id, "access": has_access, "fsm_state": fsm_state},
    )

    if not has_access:
        logger.info(
            "Access denied to admin panel",
            extra={"user_id": user_id, "fsm_state": fsm_state},
        )
        return await message.answer("⛔ У вас нет доступа")

    await message.answer(
        "👑 <b>Админ-панель</b>\nВыберите раздел:",
        reply_markup=admin_main_menu_kb()
    )
    logger.info(
        "Admin menu sent",
        extra={"user_id": user_id, "fsm_state": fsm_state},
    )


@router.message(Command("admin"))
async def admin_panel(message: types.Message, state: FSMContext):
    await _send_admin_panel(message, state)


@router.message(F.text == "🛠 Режим админа")
async def admin_panel_button(message: types.Message, state: FSMContext):
    await _send_admin_panel(message, state)


@router.message(Command("unblock_admins"))
async def unblock_admins_command(message: types.Message) -> None:
    if not message.from_user:
        return

    if message.from_user.id != ROOT_ADMIN_ID:
        return await message.answer("⛔ У вас нет доступа")

    async with async_session() as session:
        operator_admin = await session.scalar(
            select(Admin).where(Admin.telegram_id == message.from_user.id)
        )
        restored_admins = await unblock_blocked_admins(
            session,
            operator_admin=operator_admin,
            reason="Ручная разблокировка админов",
            interface="command.unblock_admins",
            operator_username=message.from_user.username,
        )

    if not restored_admins:
        await message.answer("🚫 Заблокированные администраторы не найдены.")
        return

    await message.answer(
        "✅ Доступ восстановлен для админов: {}".format(
            ", ".join(str(user.tg_id) for user in restored_admins)
        )
    )


# Обработка кнопок админ-панели
@router.message(OutsideServerManageState(), F.text == "↩️ Назад")
async def admin_back_to_panel(message: types.Message, state: FSMContext):
    if not message.from_user:
        return

    if not await is_admin(message.from_user.id):
        return await message.answer("⛔ У вас нет доступа")

    await state.clear()
    await message.answer(
        "👑 <b>Админ-панель</b>\nВыберите раздел:",
        reply_markup=admin_main_menu_kb(),
    )


@router.message(F.text == "↩️ В меню")
async def admin_exit_to_main(message: types.Message, state: FSMContext):
    if not message.from_user:
        return

    user_id = message.from_user.id

    is_user_admin = await is_admin(user_id)
    if not is_user_admin:
        return await message.answer("⛔ У вас нет доступа")

    await state.clear()
    await message.answer(
        "🏠 Вы вернулись в главное меню.",
        reply_markup=main_menu(is_admin=is_user_admin),
    )


@router.callback_query(
    StateFilter(None),
    F.data.func(lambda data: isinstance(data, str) and data.endswith("_back")),
)
async def admin_inline_back(call: types.CallbackQuery, state: FSMContext):
    data = call.data or ""
    if data.startswith("servers_"):
        return await call.answer()

    if not call.from_user:
        return await call.answer()

    if not await is_admin(call.from_user.id):
        return await call.answer("⛔ У вас нет доступа", show_alert=True)

    await state.clear()
    if call.message:
        await call.message.answer(
            "👑 <b>Админ-панель</b>\nВыберите раздел:",
            reply_markup=admin_main_menu_kb(),
        )

    await call.answer()
