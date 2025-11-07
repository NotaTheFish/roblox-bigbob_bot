from __future__ import annotations

from aiogram import F, Router, types
from sqlalchemy import select

from bot.db import Admin, async_session
from bot.keyboards.admin_keyboards import admin_main_menu_kb


router = Router(name="admin_logs")


async def is_admin(uid: int) -> bool:
    async with async_session() as session:
        return bool(await session.scalar(select(Admin).where(Admin.telegram_id == uid)))


@router.message(F.text == "📜 Логи")
async def show_logs_placeholder(message: types.Message):
    if not message.from_user:
        return

    if not await is_admin(message.from_user.id):
        return

    await message.answer(
        "📜 Раздел логов появится позже.",
        reply_markup=admin_main_menu_kb(),
    )