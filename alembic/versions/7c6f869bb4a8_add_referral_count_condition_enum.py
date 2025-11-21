"""Ensure referral count achievement condition enum value exists"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7c6f869bb4a8"
down_revision: Union[str, Sequence[str], None] = "6f3af269808d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


CONDITION_VALUES = (
    "none",
    "balance_at_least",
    "nuts_at_least",
    "product_purchase",
    "purchase_count_at_least",
    "payments_sum_at_least",
    "referral_count_at_least",
    "time_in_game_at_least",
    "spent_sum_at_least",
    "promocode_redemption_count_at_least",
)


def upgrade() -> None:
    for value in CONDITION_VALUES:
        op.execute(
            f"ALTER TYPE achievement_condition_type ADD VALUE IF NOT EXISTS '{value}'"
        )


def downgrade() -> None:
    # Enum value removal is not supported without recreating the type; skipping downgrade.
    pass