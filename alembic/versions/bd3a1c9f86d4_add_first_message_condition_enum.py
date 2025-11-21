"""Add first_message_sent achievement condition enum value

Revision ID: bd3a1c9f86d4
Revises: ('779d95b1a3b4', 'c71ea3c01cbb')
Create Date: 2025-11-24 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "bd3a1c9f86d4"
down_revision: Union[str, Sequence[str], None] = ("779d95b1a3b4", "c71ea3c01cbb")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


NEW_CONDITION_VALUE = "first_message_sent"


def upgrade() -> None:
    op.execute(
        f"ALTER TYPE achievement_condition_type ADD VALUE IF NOT EXISTS '{NEW_CONDITION_VALUE}'"
    )


def downgrade() -> None:
    # Enum value removal requires recreating the type; skipping downgrade.
    pass