"""Allow product purchase achievements to store slugs

Revision ID: 779d95b1a3b4
Revises: 3d487062b1cc, cce6f0285e2d
Create Date: 2025-03-15 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "779d95b1a3b4"
down_revision: Union[str, Sequence[str], None] = ("3d487062b1cc", "cce6f0285e2d")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("achievements") as batch_op:
        batch_op.alter_column(
            "condition_value",
            existing_type=sa.Integer(),
            type_=sa.String(length=255),
            existing_nullable=True,
            postgresql_using="condition_value::text",
        )


def downgrade() -> None:
    with op.batch_alter_table("achievements") as batch_op:
        batch_op.alter_column(
            "condition_value",
            existing_type=sa.String(length=255),
            type_=sa.Integer(),
            existing_nullable=True,
            postgresql_using=(
                "CASE WHEN condition_value ~ '^[0-9]+$'"
                " THEN condition_value::integer ELSE NULL END"
            ),
        )