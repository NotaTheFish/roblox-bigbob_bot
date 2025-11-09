# wipe_db.py
from db.models import Base
from bot.db import sync_engine


def wipe() -> None:
    with sync_engine.begin() as conn:
        Base.metadata.drop_all(bind=conn)
        Base.metadata.create_all(bind=conn)


if __name__ == "__main__":
    wipe()
    print("✅ DATABASE DROPPED AND RECREATED")
