"""add ban appeal submitted flag

Revision ID: f1b0a943f5aa
Revises: a3f457ceaa2f
Create Date: 2025-02-14 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f1b0a943f5aa"
down_revision: Union[str, Sequence[str], None] = "a3f457ceaa2f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "ban_appeal_submitted",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "ban_appeal_submitted")