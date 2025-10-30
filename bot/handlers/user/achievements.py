from aiogram import types, Dispatcher
from bot.db import SessionLocal, Achievement, UserAchievement

async def my_achievements(message: types.Message):
    uid = message.from_user.id

    with SessionLocal() as s:
        owned = {a.achievement_id for a in s.query(UserAchievement).filter_by(tg_id=uid).all()}
        achs = s.query(Achievement).all()

    text = "🏆 <b>Ваши достижения:</b>\n\n"

    for a in achs:
        if a.id in owned:
            text += f"✅ {a.name} — получено\n"
        else:
            text += f"❌ {a.name} — не получено\n"

    await message.answer(text, parse_mode="HTML")
