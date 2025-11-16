from __future__ import annotations

from decimal import Decimal, InvalidOperation

from aiogram import Router, types
from aiogram.filters import Command

from bot.db import async_session
from bot.services.settings import get_ton_rate, set_ton_rate
from bot.utils.helpers import get_admin_telegram_ids


router = Router(name="admin_settings")


async def is_admin(uid: int) -> bool:
    admin_ids = await get_admin_telegram_ids(include_root=True)
    return uid in admin_ids


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