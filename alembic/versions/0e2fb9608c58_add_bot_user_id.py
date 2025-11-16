"""add bot user id column"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from db.constants import BOT_USER_ID_PREFIX, BOT_USER_ID_SEQUENCE

# revision identifiers, used by Alembic.
revision: str = "0e2fb9608c58"
down_revision: Union[str, Sequence[str], None] = "e495a410f1f8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_BOT_USER_ID_DEFAULT = sa.text(
    f"'{BOT_USER_ID_PREFIX}' || nextval('{BOT_USER_ID_SEQUENCE}'::regclass)"
)


def upgrade() -> None:
    op.execute(
        sa.text(
            f"CREATE SEQUENCE IF NOT EXISTS {BOT_USER_ID_SEQUENCE} START WITH 100001"
        )
    )
    op.add_column(
        "users",
        sa.Column(
            "bot_user_id",
            sa.String(length=32),
            nullable=True,
            server_default=_BOT_USER_ID_DEFAULT,
        ),
    )
    op.execute(
        sa.text(
            f"ALTER SEQUENCE {BOT_USER_ID_SEQUENCE} OWNED BY users.bot_user_id"
        )
    )
    op.create_index(
        "ix_users_bot_user_id",
        "users",
        ["bot_user_id"],
        unique=True,
    )
    op.execute(
        sa.text(
            "UPDATE users SET bot_user_id = "
            f"'{BOT_USER_ID_PREFIX}' || nextval('{BOT_USER_ID_SEQUENCE}'::regclass) "
            "WHERE bot_user_id IS NULL"
        )
    )
    op.alter_column("users", "bot_user_id", nullable=False)


def downgrade() -> None:
    op.drop_index("ix_users_bot_user_id", table_name="users")
    op.drop_column("users", "bot_user_id")
    op.execute(sa.text(f"DROP SEQUENCE IF EXISTS {BOT_USER_ID_SEQUENCE}"))