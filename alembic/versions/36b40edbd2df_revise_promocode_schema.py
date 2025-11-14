"""Restore original promocode schema.

Revision ID: 1ca9271b7ba4
Revises: c33e9e016497
Create Date: 2025-11-14 10:49:54.759636

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "1ca9271b7ba4"
down_revision: Union[str, Sequence[str], None] = "c33e9e016497"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _get_promocode_columns() -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {column["name"] for column in inspector.get_columns("promocodes")}


def upgrade() -> None:
    """Bring promocodes back to their original structure."""

    columns = _get_promocode_columns()
    legacy_columns = {"type", "uses_count", "created_by"}
    if not (columns & legacy_columns):
        # Database already matches the desired schema.
        return

    with op.batch_alter_table("promocodes") as batch:
        if "reward_type" not in columns:
            batch.add_column(sa.Column("reward_type", sa.String(length=32), nullable=True))
        if "reward_amount" not in columns:
            batch.add_column(sa.Column("reward_amount", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("value_text", sa.String(length=255), nullable=True))

    op.execute("UPDATE promocodes SET value_text = CAST(value AS TEXT)")
    op.execute("UPDATE promocodes SET reward_amount = CAST(value AS INTEGER)")
    op.execute(
        """
        UPDATE promocodes
        SET reward_type = CASE
            WHEN reward_type IS NOT NULL THEN reward_type
            WHEN type = 'nuts' THEN 'nuts'
            WHEN type IS NOT NULL THEN type
            ELSE 'balance'
        END
        """
    )

    with op.batch_alter_table("promocodes") as batch:
        batch.drop_column("value")
        batch.alter_column(
            "value_text",
            new_column_name="value",
            existing_type=sa.String(length=255),
            nullable=True,
        )
        if "created_by" in columns:
            batch.drop_column("created_by")
        if "uses_count" in columns:
            batch.alter_column(
                "uses_count",
                new_column_name="uses",
                existing_type=sa.Integer(),
                nullable=True,
                server_default=None,
            )
        if "type" in columns:
            batch.alter_column(
                "type",
                new_column_name="promo_type",
                existing_type=sa.String(length=32),
                nullable=False,
                server_default=None,
            )

    op.execute("UPDATE promocodes SET uses = COALESCE(uses, 0)")
    op.execute("UPDATE promocodes SET reward_amount = COALESCE(reward_amount, 0)")
    op.execute("UPDATE promocodes SET reward_type = COALESCE(reward_type, 'balance')")

    with op.batch_alter_table("promocodes") as batch:
        batch.alter_column(
            "uses",
            existing_type=sa.Integer(),
            nullable=False,
            server_default="0",
        )
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
        batch.alter_column(
            "max_uses",
            existing_type=sa.Integer(),
            nullable=True,
            server_default=None,
        )


def downgrade() -> None:
    """Reintroduce the removed columns."""

    with op.batch_alter_table("promocodes") as batch:
        batch.alter_column(
            "max_uses",
            existing_type=sa.Integer(),
            nullable=False,
            server_default="0",
        )
        batch.alter_column(
            "reward_type",
            existing_type=sa.String(length=32),
            nullable=False,
            server_default="nuts",
        )
        batch.alter_column(
            "reward_amount",
            existing_type=sa.Integer(),
            nullable=False,
            server_default="0",
        )
        batch.alter_column(
            "uses",
            existing_type=sa.Integer(),
            nullable=False,
            server_default="0",
        )
        batch.alter_column(
            "promo_type",
            new_column_name="type",
            existing_type=sa.String(length=32),
            nullable=False,
            server_default="nuts",
        )
        batch.alter_column(
            "uses",
            new_column_name="uses_count",
            existing_type=sa.Integer(),
            nullable=False,
            server_default="0",
        )
        batch.add_column(sa.Column("created_by", sa.BigInteger(), nullable=True))
        batch.add_column(sa.Column("value_numeric", sa.Float(), nullable=True))

    op.execute("UPDATE promocodes SET value_numeric = CAST(value AS DOUBLE PRECISION)")

    with op.batch_alter_table("promocodes") as batch:
        batch.drop_column("value")
        batch.alter_column(
            "value_numeric",
            new_column_name="value",
            existing_type=sa.Float(),
            nullable=False,
            server_default="0",
        )