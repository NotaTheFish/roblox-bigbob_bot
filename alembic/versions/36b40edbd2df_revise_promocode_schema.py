"""revise_promocode_schema

Revision ID: 36b40edbd2df
Revises: a1bb258f4246
Create Date: 2025-11-14 01:25:25.711982

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "36b40edbd2df"
down_revision: Union[str, Sequence[str], None] = "a1bb258f4246"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    with op.batch_alter_table("promocodes") as batch:
        batch.alter_column(
            "promo_type",
            new_column_name="type",
            existing_type=sa.String(length=32),
            nullable=False,
        )
        batch.add_column(sa.Column("created_by", sa.BigInteger(), nullable=True))
        batch.add_column(sa.Column("value_numeric", sa.Float(), nullable=True))
        batch.alter_column(
            "uses",
            new_column_name="uses_count",
            existing_type=sa.Integer(),
            nullable=True,
        )

    op.execute(
        "UPDATE promocodes SET type = 'nuts' WHERE type = 'money' OR type IS NULL"
    )

    op.execute(
        "UPDATE promocodes SET value_numeric = COALESCE(reward_amount, CAST(NULLIF(value, '') AS DOUBLE PRECISION))"
    )
    op.execute("UPDATE promocodes SET value_numeric = 0 WHERE value_numeric IS NULL")
    op.execute("UPDATE promocodes SET uses_count = COALESCE(uses_count, 0)")
    op.execute("UPDATE promocodes SET max_uses = COALESCE(max_uses, 0)")

    with op.batch_alter_table("promocodes") as batch:
        batch.drop_column("value")
        batch.alter_column(
            "value_numeric",
            new_column_name="value",
            existing_type=sa.Float(),
            nullable=False,
            server_default="0",
        )
        batch.drop_column("reward_amount")
        batch.drop_column("reward_type")
        batch.alter_column(
            "max_uses",
            existing_type=sa.Integer(),
            nullable=False,
            server_default="0",
        )
        batch.alter_column(
            "uses_count",
            existing_type=sa.Integer(),
            nullable=False,
            server_default="0",
        )
        batch.alter_column(
            "type",
            existing_type=sa.String(length=32),
            nullable=False,
            server_default="nuts",
        )


def downgrade() -> None:
    """Downgrade schema."""

    with op.batch_alter_table("promocodes") as batch:
        batch.add_column(sa.Column("reward_type", sa.String(length=32), nullable=True))
        batch.add_column(sa.Column("reward_amount", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("value_text", sa.String(length=255), nullable=True))

    op.execute("UPDATE promocodes SET reward_amount = CAST(value AS INTEGER)")
    op.execute(
        "UPDATE promocodes SET reward_type = CASE WHEN type = 'nuts' THEN 'balance' ELSE type END"
    )
    op.execute("UPDATE promocodes SET value_text = CAST(value AS TEXT)")

    with op.batch_alter_table("promocodes") as batch:
        batch.drop_column("value")
        batch.alter_column(
            "value_text",
            new_column_name="value",
            existing_type=sa.String(length=255),
            nullable=True,
        )
        batch.drop_column("created_by")
        batch.alter_column(
            "uses_count",
            new_column_name="uses",
            existing_type=sa.Integer(),
            nullable=True,
        )
        batch.alter_column(
            "max_uses",
            existing_type=sa.Integer(),
            nullable=True,
            server_default=None,
        )
        batch.alter_column(
            "type",
            new_column_name="promo_type",
            existing_type=sa.String(length=32),
            nullable=False,
            server_default="money",
        )

    op.execute("UPDATE promocodes SET promo_type = 'money' WHERE promo_type = 'nuts'")

    with op.batch_alter_table("promocodes") as batch:
        batch.alter_column(
            "reward_amount",
            existing_type=sa.Integer(),
            nullable=False,
            server_default="0",
        )
        batch.alter_column(
            "reward_type",
            existing_type=sa.String(length=32),
            nullable=False,
            server_default="balance",
        )