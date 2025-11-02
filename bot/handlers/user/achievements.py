from __future__ import annotations

from aiogram import types, Dispatcher
from sqlalchemy import select

from bot.db import Achievement, UserAchievement, async_session


async def my_achievements(message: types.Message):
    if not message.from_user:
        return

    uid = message.from_user.id

    async with async_session() as session:
        owned = set(
            await session.scalars(
                select(UserAchievement.achievement_id).where(UserAchievement.tg_id == uid)
            )
        )

        achievements = await session.scalars(select(Achievement))

    text = "🏆 <b>Ваши достижения:</b>\n\n"

    for a in achievements:
        if a.id in owned:
            text += f"✅ {a.name} — получено\n"
        else:
            text += f"❌ {a.name} — не получено\n"

    await message.answer(text, parse_mode="HTML")


def register_user_achievements(dp: Dispatcher):
    dp.register_message_handler(my_achievements, commands=["achievements"])
