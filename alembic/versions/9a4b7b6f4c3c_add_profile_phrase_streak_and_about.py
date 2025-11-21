"""Add profile phrase streak condition and about text timestamp"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9a4b7b6f4c3c"
down_revision: Union[str, Sequence[str], None] = "7c6f869bb4a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


NEW_CONDITION_VALUE = "profile_phrase_streak"


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("about_text_updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        f"ALTER TYPE achievement_condition_type ADD VALUE IF NOT EXISTS '{NEW_CONDITION_VALUE}'"
    )


def downgrade() -> None:
    op.drop_column("users", "about_text_updated_at")
    # Enum value removal is not supported without recreating the type; skipping downgrade.
    pass