from __future__ import annotations

from aiogram import types, Dispatcher
from sqlalchemy import select

from bot.bot_instance import bot
from bot.db import async_session, TopUpRequest, User, Admin
from bot.utils.achievement_checker import check_achievements


async def is_admin(uid: int) -> bool:
    async with async_session() as session:
        result = await session.execute(select(Admin).where(Admin.telegram_id == uid))
        return result.scalar_one_or_none() is not None


async def approve_topup(call: types.CallbackQuery) -> None:
    if not call.from_user:
        return await call.answer("Нет доступа", show_alert=True)

    if not await is_admin(call.from_user.id):
        return await call.answer("Нет доступа", show_alert=True)

    req_id = int(call.data.split(":")[1])
    user_id = None
    amount = None

    async with async_session() as session:
        request_result = await session.execute(select(TopUpRequest).where(TopUpRequest.id == req_id))
        request = request_result.scalar_one_or_none()
        if not request or request.status != "pending":
            return await call.answer("❌ Заявка не найдена", show_alert=True)

        user_result = await session.execute(select(User).where(User.tg_id == request.user_id))
        user = user_result.scalar_one_or_none()
        if not user:
            request.status = "denied"
            await session.commit()
            return await call.answer("❌ Пользователь не найден", show_alert=True)

        user.balance += request.amount
        request.status = "approved"
        user_id = request.user_id
        amount = request.amount
        await session.commit()

        # Чекаем ачивки после обновления — передадим ID
        await check_achievements(user)

    if user_id is not None and amount is not None:
        try:
            await bot.send_message(user_id, f"✅ Ваш баланс пополнен на {amount} монет!")
        except Exception:
            pass

    await call.message.edit_text(f"✅ Заявка #{req_id} выполнена")
    await call.answer("✅ Готово")


async def deny_topup(call: types.CallbackQuery) -> None:
    if not call.from_user:
        return await call.answer("Нет доступа", show_alert=True)

    if not await is_admin(call.from_user.id):
        return await call.answer("Нет доступа", show_alert=True)

    req_id = int(call.data.split(":")[1])
    user_id = None

    async with async_session() as session:
        request_result = await session.execute(select(TopUpRequest).where(TopUpRequest.id == req_id))
        request = request_result.scalar_one_or_none()
        if request:
            request.status = "denied"
            user_id = request.user_id
            await session.commit()

    await call.message.edit_text(f"❌ Заявка #{req_id} отклонена")

    if user_id is not None:
        try:
            await bot.send_message(user_id, f"❌ Ваша заявка #{req_id} отклонена")
        except Exception:
            pass

    await call.answer("✅ Отклонено")


def register_admin_payments(dp: Dispatcher) -> None:
    dp.register_callback_query_handler(approve_topup, lambda c: c.data.startswith("topup_ok"))
    dp.register_callback_query_handler(deny_topup, lambda c: c.data.startswith("topup_no"))
