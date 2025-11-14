"""add cascade to promocode redemptions

Revision ID: 45ebed097f52
Revises: 36b35051bf03
Create Date: 2025-11-14 15:31:19.024176

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


def _constraint_exists(bind, table_name: str, constraint_name: str) -> bool:
    inspector = sa.inspect(bind)
    return any(
        fk.get("name") == constraint_name
        for fk in inspector.get_foreign_keys(table_name)
    )


# revision identifiers, used by Alembic.
revision: str = '45ebed097f52'
down_revision: Union[str, Sequence[str], None] = '36b35051bf03'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    constraint_name = "promocode_redemptions_promocode_id_fkey"

    with op.batch_alter_table("promocode_redemptions", schema=None) as batch_op:
        if _constraint_exists(bind, "promocode_redemptions", constraint_name):
            batch_op.drop_constraint(
                constraint_name,
                type_="foreignkey",
            )
        batch_op.create_foreign_key(
            constraint_name,
            "promocodes",
            ["promocode_id"],
            ["id"],
            ondelete="CASCADE",
        )


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    constraint_name = "promocode_redemptions_promocode_id_fkey"

    with op.batch_alter_table("promocode_redemptions", schema=None) as batch_op:
        if _constraint_exists(bind, "promocode_redemptions", constraint_name):
            batch_op.drop_constraint(
                constraint_name,
                type_="foreignkey",
            )
        batch_op.create_foreign_key(
            constraint_name,
            "promocodes",
            ["promocode_id"],
            ["id"],
        )