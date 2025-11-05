from __future__ import annotations

from aiogram import F, Router, types
from aiogram.filters import Command
from sqlalchemy import select

from bot.db import Admin, async_session
from bot.keyboards.admin_keyboards import admin_main_menu_kb


router = Router(name="admin_menu")


# Проверка администратора
async def is_admin(uid: int) -> bool:
    async with async_session() as session:
        return bool(await session.scalar(select(Admin).where(Admin.telegram_id == uid)))


# Команда для входа в админ панель
@router.message(Command("admin"))
async def admin_panel(message: types.Message):
    if not message.from_user:
        return

    if not await is_admin(message.from_user.id):
        return await message.answer("⛔ У вас нет доступа")

    await message.answer(
        "👑 <b>Админ-панель</b>\nВыберите раздел:",
        reply_markup=admin_main_menu_kb()
    )


# Обработка кнопок админ-панели
@router.callback_query(F.data.in_({"admin_logs", "back_to_menu"}))
async def admin_menu_callbacks(call: types.CallbackQuery):
    if not call.from_user:
        return await call.answer("⛔ Нет доступа", show_alert=True)

    if not await is_admin(call.from_user.id):
        return await call.answer("⛔ Нет доступа", show_alert=True)

    if call.data == "back_to_menu":
        await call.message.edit_text(
            "👑 <b>Админ-панель</b>\nВыберите раздел:",
            reply_markup=admin_main_menu_kb(),
        )
    elif call.data == "admin_logs":
        await call.message.edit_text(
            "📜 Раздел логов появится позже.",
            reply_markup=admin_main_menu_kb(),
        )

    await call.answer()
