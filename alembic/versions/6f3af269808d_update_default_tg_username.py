"""update default Telegram username placeholder

Revision ID: 6f3af269808d
Revises: f2839f5ea78b
Create Date: 2025-11-17 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "6f3af269808d"
down_revision: Union[str, Sequence[str], None] = "f2839f5ea78b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


OLD_USERNAME = "Инкогнито_дрочер"
NEW_USERNAME = "INKOGNITO_DROCHER"


def upgrade() -> None:
    """Replace the legacy Telegram username placeholder everywhere it may appear."""

    op.execute(
        sa.text(
            """
            UPDATE users
            SET tg_username = :new_username
            WHERE tg_username = :old_username
            """
        ).bindparams(new_username=NEW_USERNAME, old_username=OLD_USERNAME)
    )

    op.execute(
        sa.text(
            """
            UPDATE admin_requests
            SET username = :new_username
            WHERE username = :old_username
            """
        ).bindparams(new_username=NEW_USERNAME, old_username=OLD_USERNAME)
    )


def downgrade() -> None:
    """Restore the previous Telegram username placeholder."""

    op.execute(
        sa.text(
            """
            UPDATE users
            SET tg_username = :old_username
            WHERE tg_username = :new_username
            """
        ).bindparams(new_username=NEW_USERNAME, old_username=OLD_USERNAME)
    )

    op.execute(
        sa.text(
            """
            UPDATE admin_requests
            SET username = :old_username
            WHERE username = :new_username
            """
        ).bindparams(new_username=NEW_USERNAME, old_username=OLD_USERNAME)
    )