from __future__ import annotations

from aiogram import F, Router, types
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from sqlalchemy import select

from bot.db import Admin, async_session
from bot.keyboards.admin_keyboards import admin_main_menu_kb
from bot.keyboards.main_menu import main_menu


router = Router(name="admin_menu")


# Проверка администратора
async def is_admin(uid: int) -> bool:
    async with async_session() as session:
        return bool(await session.scalar(select(Admin).where(Admin.telegram_id == uid)))


# Команда для входа в админ панель
async def _send_admin_panel(message: types.Message):
    if not message.from_user:
        return

    if not await is_admin(message.from_user.id):
        return await message.answer("⛔ У вас нет доступа")

    await message.answer(
        "👑 <b>Админ-панель</b>\nВыберите раздел:",
        reply_markup=admin_main_menu_kb()
    )


@router.message(Command("admin"))
async def admin_panel(message: types.Message):
    await _send_admin_panel(message)


@router.message(F.text == "🛠 Режим админа")
async def admin_panel_button(message: types.Message):
    await _send_admin_panel(message)


# Обработка кнопок админ-панели
@router.message(F.text == "↩️ Назад")
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
