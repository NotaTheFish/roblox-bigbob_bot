"""add revoked and unblocked to banned roblox accounts

Revision ID: 4208b3098946
Revises: 3d8fb9a9d9a5
Create Date: 2025-11-28 15:07:06.753140

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4208b3098946'
down_revision: Union[str, Sequence[str], None] = '3d8fb9a9d9a5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("banned_roblox_accounts", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("unblocked_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "revoked_by",
                sa.Integer(),
                sa.ForeignKey("admins.id"),
                nullable=True,
            )
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("banned_roblox_accounts", schema=None) as batch_op:
        batch_op.drop_column("revoked_by")
        batch_op.drop_column("unblocked_at")