import sqlalchemy as sa
from sqlalchemy import event
from sqlalchemy.orm import sessionmaker

from db import Achievement, Base, User


def test_selected_achievement_is_set_to_null_on_delete():
    engine = sa.create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def enable_sqlite_foreign_keys(dbapi_connection, _):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)

    Session = sessionmaker(bind=engine)
    with Session() as session:
        achievement = Achievement(
            name="Temporary",
            reward=10,
            condition_type="none",
            is_visible=True,
        )
        user = User(
            bot_user_id="bot_user_1",
            tg_id=123,
            selected_achievement=achievement,
        )

        session.add_all([achievement, user])
        session.commit()

        session.delete(achievement)
        session.commit()
        session.refresh(user)

        assert user.selected_achievement_id is None
        assert user.selected_achievement is None