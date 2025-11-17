"""add server position ordering

Revision ID: 5a52c3c28494
Revises: f1b0a943f5aa
Create Date: 2025-03-17 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "5a52c3c28494"
down_revision: Union[str, Sequence[str], None] = "f1b0a943f5aa"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("servers", sa.Column("position", sa.Integer(), nullable=True))

    conn = op.get_bind()
    result = conn.execute(sa.text("SELECT id FROM servers ORDER BY id")).fetchall()
    for idx, (server_id,) in enumerate(result, start=1):
        conn.execute(
            sa.text("UPDATE servers SET position = :pos WHERE id = :sid"),
            {"pos": idx, "sid": server_id},
        )

    op.alter_column("servers", "position", existing_type=sa.Integer(), nullable=False)
    op.create_unique_constraint("uq_servers_position", "servers", ["position"])


def downgrade() -> None:
    op.drop_constraint("uq_servers_position", "servers", type_="unique")
    op.drop_column("servers", "position")