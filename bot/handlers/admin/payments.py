from __future__ import annotations

from aiogram import F, Router, types
from sqlalchemy import select

from bot.db import (
    Admin,
    LogEntry,
    Payment,
    TopUpRequest,
    User,
    async_session,
)
from bot.utils.achievement_checker import check_achievements


router = Router(name="admin_payments")


async def is_admin(uid: int) -> bool:
    async with async_session() as session:
        result = await session.execute(select(Admin).where(Admin.telegram_id == uid))
        return result.scalar_one_or_none() is not None


@router.callback_query(F.data.startswith("topup_ok"))
async def approve_topup(call: types.CallbackQuery) -> None:
    if not call.from_user:
        return await call.answer("Нет доступа", show_alert=True)

    if not await is_admin(call.from_user.id):
        return await call.answer("Нет доступа", show_alert=True)

    req_id = int(call.data.split(":")[1])

    async with async_session() as session:
        request = await session.get(TopUpRequest, req_id)
        if not request or request.status != "pending":
            return await call.answer("❌ Заявка не найдена", show_alert=True)

        user = await session.get(User, request.user_id)
        if not user:
            request.status = "denied"
            await session.commit()
            return await call.answer("❌ Пользователь не найден", show_alert=True)

        # Create payment log
        payment = Payment(
            provider="admin_manual",
            provider_payment_id=request.request_id,
            user_id=user.id,
            telegram_id=user.tg_id,
            amount=request.amount,
            currency=request.currency,
            status="completed",
            metadata_json={"topup_request_id": request.id},
        )
        session.add(payment)
        await session.flush()

        # Update balance
        user.balance += request.amount
        request.status = "approved"
        request.payment_id = payment.id

        session.add(
            LogEntry(
                user_id=user.id,
                telegram_id=user.tg_id,
                request_id=payment.request_id,
                event_type="topup_approved",
                message=f"Пополнение на {request.amount} {request.currency}",
                data={"topup_request_id": request.id},
            )
        )

        await session.commit()

        # Check achievements
        await check_achievements(user)

    try:
        await call.bot.send_message(
            request.telegram_id,
            f"✅ Ваш баланс пополнен на {request.amount} {request.currency.upper()}!",
        )
    except Exception:
        pass

    await call.message.edit_text(f"✅ Заявка #{req_id} выполнена")
    await call.answer("✅ Готово")


@router.callback_query(F.data.startswith("topup_no"))
async def deny_topup(call: types.CallbackQuery) -> None:
    if not call.from_user:
        return await call.answer("Нет доступа", show_alert=True)

    if not await is_admin(call.from_user.id):
        return await call.answer("Нет доступа", show_alert=True)

    req_id = int(call.data.split(":")[1])

    async with async_session() as session:
        request = await session.get(TopUpRequest, req_id)
        if request:
            request.status = "denied"
            session.add(
                LogEntry(
                    user_id=request.user_id,
                    telegram_id=request.telegram_id,
                    request_id=request.request_id,
                    event_type="topup_denied",
                    message="Заявка на пополнение отклонена",
                    data={"topup_request_id": request.id},
                )
            )
            await session.commit()

    await call.message.edit_text(f"❌ Заявка #{req_id} отклонена")

    try:
        await call.bot.send_message(
            request.telegram_id,
            f"❌ Ваша заявка #{req_id} отклонена",
        )
    except Exception:
        pass

    await call.answer("✅ Отклонено")
