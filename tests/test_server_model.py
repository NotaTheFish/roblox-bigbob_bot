import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from db import Base
from db.models import SERVER_DEFAULT_CLOSED_MESSAGE, Server


def test_server_has_url_and_closed_message_default():
    engine = sa.create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)

    inspector = sa.inspect(engine)
    column_names = {column["name"] for column in inspector.get_columns("servers")}
    assert "url" in column_names
    assert "closed_message" in column_names

    Session = sessionmaker(bind=engine)
    with Session() as session:
        server = Server(name="Test Server", slug="test-server")
        session.add(server)
        session.commit()
        session.refresh(server)

        assert server.url is None
        assert server.closed_message == SERVER_DEFAULT_CLOSED_MESSAGE