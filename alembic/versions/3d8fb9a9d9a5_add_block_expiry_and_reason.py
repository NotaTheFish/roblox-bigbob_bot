"""add block expiry and reason to users

Revision ID: 3d8fb9a9d9a5
Revises: e79e560da462
Create Date: 2025-11-29 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "3d8fb9a9d9a5"
down_revision: Union[str, Sequence[str], None] = "e79e560da462"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("blocked_until", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("block_reason", sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("block_reason")
        batch_op.drop_column("blocked_until")
