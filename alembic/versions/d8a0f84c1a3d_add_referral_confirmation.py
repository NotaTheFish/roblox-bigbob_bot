"""Add confirmed flag to referrals

Revision ID: d8a0f84c1a3d
Revises: b9f74c424d88
Create Date: 2025-11-17 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d8a0f84c1a3d"
down_revision: Union[str, Sequence[str], None] = "b9f74c424d88"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "referrals",
        sa.Column(
            "confirmed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.alter_column("referrals", "confirmed", server_default=None)


def downgrade() -> None:
    op.drop_column("referrals", "confirmed")