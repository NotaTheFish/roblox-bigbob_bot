"""Add missing achievement condition enum values"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "1c2e6b0d7f9c"
down_revision: Union[str, Sequence[str], None] = "f1564e7c5c62"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


NEW_CONDITION_VALUES = (
    "time_in_game_at_least",
    "spent_sum_at_least",
    "promocode_redemption_count_at_least",
)


def upgrade() -> None:
    for value in NEW_CONDITION_VALUES:
        op.execute(
            f"ALTER TYPE achievement_condition_type ADD VALUE IF NOT EXISTS '{value}'"
        )


def downgrade() -> None:
    # Enum value removal is not supported without recreating the type; skipping downgrade.
    pass