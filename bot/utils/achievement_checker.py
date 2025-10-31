from bot.db import SessionLocal, User, UserAchievement, Achievement

def check_achievements(user):
    with SessionLocal() as s:
        owned = {a.achievement_id for a in s.query(UserAchievement).filter_by(tg_id=user.tg_id).all()}
        all_ach = s.query(Achievement).all()

        for ach in all_ach:
            if ach.id in owned:
                continue

            if ach.name == "Начало игры":
                give(s, user, ach)

            if ach.name == "Первый донат" and user.balance >= 100:
                give(s, user, ach)

            if ach.name == "Магнат" and user.balance >= 10000:
                give(s, user, ach)


def give(s, user, ach):
    s.add(UserAchievement(tg_id=user.tg_id, achievement_id=ach.id))
    db_user = s.query(User).filter_by(tg_id=user.tg_id).first()
    if db_user:
        db_user.balance += ach.reward
    s.commit()
