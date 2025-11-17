"""add bot nickname fields

Revision ID: 5cadd636709b
Revises: 59da393544d7
Create Date: 2025-11-17 14:00:22.812123

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "5cadd636709b"
down_revision: Union[str, Sequence[str], None] = "59da393544d7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("bot_nickname", sa.String(length=255), nullable=True))
    op.add_column(
        "users",
        sa.Column("nickname_changed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "nickname_changed_at")
    op.drop_column("users", "bot_nickname")