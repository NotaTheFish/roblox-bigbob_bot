"""add ban notification and appeal state fields

Revision ID: b9f74c424d88
Revises: f1b0a943f5aa
Create Date: 2025-02-15 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b9f74c424d88"
down_revision: Union[str, Sequence[str], None] = "f1b0a943f5aa"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("ban_notified_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column(
            "appeal_open",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "users",
        sa.Column("appeal_submitted_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "appeal_submitted_at")
    op.drop_column("users", "appeal_open")
    op.drop_column("users", "ban_notified_at")