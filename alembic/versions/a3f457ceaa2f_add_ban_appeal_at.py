"""add ban appeal timestamp to users

Revision ID: a3f457ceaa2f
Revises: c7b9d8af9e63
Create Date: 2025-02-14 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a3f457ceaa2f"
down_revision: Union[str, Sequence[str], None] = "c7b9d8af9e63"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("ban_appeal_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "ban_appeal_at")