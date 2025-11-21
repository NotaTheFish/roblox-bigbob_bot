"""Add secret word achievement condition

Revision ID: a1f4c8da42af
Revises: 9cb82f44d8bf
Create Date: 2025-11-22 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "a1f4c8da42af"
down_revision: Union[str, Sequence[str], None] = "9cb82f44d8bf"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TYPE achievement_condition_type ADD VALUE IF NOT EXISTS 'secret_word'"
    )


def downgrade() -> None:
    # Enum value removal is not supported without recreating the type; skipping downgrade.
    pass