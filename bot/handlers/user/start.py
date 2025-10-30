from bot.db import SessionLocal, User

async def check_blocked(message):
    with SessionLocal() as s:
        u = s.query(User).filter_by(tg_id=message.from_user.id).first()
        if u and u.is_blocked:
            return True
    return False
