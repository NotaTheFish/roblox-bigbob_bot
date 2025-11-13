# wipe_db.py
import os

from sqlalchemy import create_engine

from db.models import Base


def wipe() -> None:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL not found")

    engine = create_engine(database_url)
    with engine.begin() as conn:
        Base.metadata.drop_all(bind=conn)
        Base.metadata.create_all(bind=conn)


if __name__ == "__main__":
    wipe()
    print("✅ DATABASE DROPPED AND RECREATED")
