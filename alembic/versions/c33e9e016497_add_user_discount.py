"""add_user_discount

Revision ID: c33e9e016497
Revises: 36b40edbd2df
Create Date: 2025-01-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c33e9e016497"
down_revision: Union[str, Sequence[str], None] = "36b40edbd2df"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(
            sa.Column("discount", sa.Float(), nullable=False, server_default="0")
        )

    op.execute("UPDATE users SET discount = 0 WHERE discount IS NULL")


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_column("discount")