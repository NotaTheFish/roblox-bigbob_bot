"""update achievements schema

Revision ID: 8c1aaf0b8d8b
Revises: 5cadd636709b
Create Date: 2025-01-27 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "8c1aaf0b8d8b"
down_revision: Union[str, Sequence[str], None] = "5cadd636709b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


CONDITION_ENUM = sa.Enum(
    "none",
    "balance_at_least",
    "nuts_at_least",
    "product_purchase",
    "purchase_count_at_least",
    "payments_sum_at_least",
    "referral_count_at_least",
    name="achievement_condition_type",
)


def upgrade() -> None:
    bind = op.get_bind()
    CONDITION_ENUM.create(bind, checkfirst=True)

    with op.batch_alter_table("achievements") as batch_op:
        batch_op.alter_column(
            "condition_type",
            type_=CONDITION_ENUM,
            existing_type=sa.String(length=64),
            nullable=False,
            existing_nullable=False,
            server_default="none",
            existing_server_default="none",
        )
        batch_op.alter_column(
            "condition_value",
            type_=sa.Integer(),
            existing_type=sa.String(length=255),
            existing_nullable=True,
            postgresql_using=(
                "CASE WHEN condition_value ~ '^[0-9]+$'"
                " THEN condition_value::integer ELSE NULL END"
            ),
        )
        batch_op.add_column(
            sa.Column(
                "is_hidden",
                sa.Boolean(),
                nullable=False,
                server_default="false",
            )
        )
        batch_op.add_column(
            sa.Column(
                "manual_grant_only",
                sa.Boolean(),
                nullable=False,
                server_default="false",
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("achievements") as batch_op:
        batch_op.drop_column("manual_grant_only")
        batch_op.drop_column("is_hidden")
        batch_op.alter_column(
            "condition_value",
            type_=sa.String(length=255),
            existing_type=sa.Integer(),
            existing_nullable=True,
            postgresql_using="condition_value::text",
        )
        batch_op.alter_column(
            "condition_type",
            type_=sa.String(length=64),
            existing_type=CONDITION_ENUM,
            nullable=False,
            existing_nullable=False,
            server_default="none",
            existing_server_default="none",
        )

    bind = op.get_bind()
    CONDITION_ENUM.drop(bind, checkfirst=True)