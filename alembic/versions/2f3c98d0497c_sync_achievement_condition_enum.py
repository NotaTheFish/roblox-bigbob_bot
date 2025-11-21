"""Ensure achievement condition enum and column use ENUM"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "2f3c98d0497c"
down_revision: Union[str, Sequence[str], None] = "a1f4c8da42af"
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
    "first_message_sent",
    "profile_phrase_streak",
    "secret_word",
)

CONDITION_ENUM = postgresql.ENUM(
    *CONDITION_VALUES, name="achievement_condition_type", create_type=False
)


def upgrade() -> None:
    bind = op.get_bind()

    # создаём enum если нет
    postgresql.ENUM(*CONDITION_VALUES, name="achievement_condition_type").create(
        bind, checkfirst=True
    )

    # добавляем все значения
    for value in CONDITION_VALUES:
        op.execute(
            f"ALTER TYPE achievement_condition_type ADD VALUE IF NOT EXISTS '{value}'"
        )

    # УБИРАЕМ DEFAULT перед изменением типа
    op.execute("ALTER TABLE achievements ALTER COLUMN condition_type DROP DEFAULT")

    # изменяем тип на ENUM
    op.alter_column(
        "achievements",
        "condition_type",
        existing_type=sa.String(length=64),
        type_=CONDITION_ENUM,
        nullable=False,
        postgresql_using="condition_type::achievement_condition_type",
    )

    # ставим корректный default уже ПОСЛЕ изменения типа
    op.execute(
        "ALTER TABLE achievements ALTER COLUMN condition_type SET DEFAULT 'none'::achievement_condition_type"
    )


def downgrade() -> None:
    op.alter_column(
        "achievements",
        "condition_type",
        existing_type=CONDITION_ENUM,
        type_=sa.String(length=64),
        nullable=False,
        server_default="none",
        postgresql_using="condition_type::text",
    )