from __future__ import annotations

from contextlib import suppress

from decimal import Decimal, InvalidOperation

from aiogram import F, Router, types
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select

from bot.db import (
    LogEntry,
    Payment,
    TopUpRequest,
    User,
    async_session,
)
from backend.services.nuts import add_nuts
from bot.utils.achievement_checker import check_achievements
from bot.utils.helpers import get_admin_telegram_ids
from bot.services.settings import get_ton_rate, set_ton_rate


TOPUP_STATUS_LABELS: dict[str, str] = {
    "pending": "⏳ В ожидании",
    "approved": "✅ Одобренные",
    "denied": "❌ Отклонённые",
}


def build_topup_keyboard(
    active_status: str | None = None,
    requests: list[TopUpRequest] | None = None,
) -> types.InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    for status, label in TOPUP_STATUS_LABELS.items():
        prefix = "• " if status == active_status else ""
        builder.row(
            types.InlineKeyboardButton(
                text=f"{prefix}{label}",
                callback_data=f"topup_filter:{status}",
            )
        )

    if active_status == "pending" and requests:
        for request in requests:
            builder.row(
                types.InlineKeyboardButton(
                    text=f"✅ #{request.id}", callback_data=f"topup_ok:{request.id}"
                ),
                types.InlineKeyboardButton(
                    text=f"❌ #{request.id}", callback_data=f"topup_no:{request.id}"
                ),
            )

    return builder.as_markup()


router = Router(name="admin_payments")


async def is_admin(uid: int) -> bool:
    admin_ids = await get_admin_telegram_ids(include_root=True)
    return uid in admin_ids


@router.message(F.text == "Пополнение")
async def admin_topups_menu(message: types.Message) -> None:
    if not message.from_user:
        return

    if not await is_admin(message.from_user.id):
        return

    await message.answer(
        "💳 <b>Пополнения</b>\nВыберите статус заявок для просмотра:",
        parse_mode="HTML",
        reply_markup=build_topup_keyboard(),
    )


@router.message(Command(commands=["tonrate", "set_ton_rate"]))
async def admin_set_ton_rate(message: types.Message) -> None:
    """Allow admins to update the TON→nuts exchange rate from Telegram."""

    if not message.from_user:
        return

    if not await is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет доступа")
        return

    raw_args = (message.text or "").split(maxsplit=1)
    if len(raw_args) < 2:
        await message.answer("Укажите курс, например: /tonrate 210.5")
        return

    rate_input = raw_args[1].strip().replace(",", ".")
    try:
        rate = Decimal(rate_input)
    except InvalidOperation:
        await message.answer("Введите корректное число, например: /tonrate 210.5")
        return

    if rate <= 0:
        await message.answer("Курс должен быть больше нуля")
        return

    async with async_session() as session:
        previous_rate = await get_ton_rate(session)
        await set_ton_rate(
            session,
            rate=rate,
            description=f"Updated via /tonrate by {message.from_user.id}",
        )
        await session.commit()

    prev_text = f"{previous_rate}" if previous_rate is not None else "не задан"
    await message.answer(
        "✅ Курс TON обновлён.\n"
        f"Было: {prev_text}\n"
        f"Стало: {rate}"
    )


async def _fetch_topups_with_users(
    status: str,
) -> list[tuple[TopUpRequest, User | None]]:
    async with async_session() as session:
        rows = await session.execute(
            select(TopUpRequest, User)
                .join(User, TopUpRequest.user_id == User.id, isouter=True)
                .where(TopUpRequest.status == status)
                .order_by(TopUpRequest.created_at.desc())
                .limit(10)
        )
        return rows.all()


@router.callback_query(F.data.startswith("topup_filter:"))
async def filter_topups(call: types.CallbackQuery) -> None:
    if not call.from_user:
        return await call.answer("Нет доступа", show_alert=True)

    if not await is_admin(call.from_user.id):
        return await call.answer("Нет доступа", show_alert=True)

    status = call.data.split(":", maxsplit=1)[1]
    if status not in TOPUP_STATUS_LABELS:
        return await call.answer("Неизвестный статус", show_alert=True)

    rows = await _fetch_topups_with_users(status)

    if rows:
        lines: list[str] = []
        for request, user in rows:
            username = (
                f"@{user.tg_username}"
                if user and user.tg_username
                else (user.username if user and user.username else f"ID {request.telegram_id}")
            )
            created_at = (
                request.created_at.strftime("%d.%m.%Y %H:%M")
                if request.created_at
                else "—"
            )
            currency = (request.currency or "RUB").upper()
            lines.append(
                "\n".join(
                    [
                        f"#{request.id} — {request.amount} {currency}",
                        f"Пользователь: {username}",
                        f"Request ID: {request.request_id or '—'}",
                        f"Создано: {created_at}",
                    ]
                )
            )

        text = (
            f"💳 <b>{TOPUP_STATUS_LABELS[status]}</b>\n"
            f"Показаны последние {len(rows)} заявок.\n\n"
            + "\n\n".join(lines)
        )
    else:
        text = (
            f"💳 <b>{TOPUP_STATUS_LABELS[status]}</b>\n"
            "Заявок не найдено."
        )

    markup = build_topup_keyboard(status, [request for request, _ in rows])

    if call.message:
        with suppress(TelegramBadRequest):
            await call.message.edit_text(
                text,
                parse_mode="HTML",
                reply_markup=markup,
            )

    await call.answer("Обновлено")


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
        await add_nuts(
            session,
            user=user,
            amount=request.amount,
            source="admin_topup",
            reason="Подтверждение пополнения",
            metadata={"topup_request_id": request.id},
        )
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
