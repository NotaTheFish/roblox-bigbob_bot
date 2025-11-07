"""set cascade delete on logs server fk

Revision ID: 2dc41feab276
Revises: b8301f953511
Create Date: 2025-11-07 20:44:32.580607

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2dc41feab276'
down_revision: Union[str, Sequence[str], None] = 'b8301f953511'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("logs") as batch_op:
        batch_op.drop_constraint("logs_server_id_fkey", type_="foreignkey")
        batch_op.create_foreign_key(
            "logs_server_id_fkey",
            "servers",
            ["server_id"],
            ["id"],
            ondelete="CASCADE",
        )


def downgrade() -> None:
    with op.batch_alter_table("logs") as batch_op:
        batch_op.drop_constraint("logs_server_id_fkey", type_="foreignkey")
        batch_op.create_foreign_key(
            "logs_server_id_fkey",
            "servers",
            ["server_id"],
            ["id"],
        )