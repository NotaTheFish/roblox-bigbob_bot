"""Add missing achievement visibility columns with safeguards

Revision ID: f1564e7c5c62
Revises: 8c1aaf0b8d8b
Create Date: 2025-02-08 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f1564e7c5c62"
down_revision: Union[str, Sequence[str], None] = "8c1aaf0b8d8b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE achievements "
        "ADD COLUMN IF NOT EXISTS is_hidden BOOLEAN NOT NULL DEFAULT false"
    )
    op.execute(
        "ALTER TABLE achievements "
        "ADD COLUMN IF NOT EXISTS manual_grant_only BOOLEAN NOT NULL DEFAULT false"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE achievements DROP COLUMN IF EXISTS manual_grant_only")
    op.execute("ALTER TABLE achievements DROP COLUMN IF EXISTS is_hidden")