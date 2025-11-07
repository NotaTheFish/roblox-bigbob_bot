"""add cascade to logs server fk

Revision ID: b8301f953511
Revises: 4e2f3d18d8c4
Create Date: 2025-11-07 18:44:29.818131

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b8301f953511"
down_revision: Union[str, Sequence[str], None] = "4e2f3d18d8c4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _get_logs_server_fk_name(bind) -> str | None:
    inspector = sa.inspect(bind)
    for fk in inspector.get_foreign_keys("logs"):
        if fk.get("referred_table") == "servers" and fk.get("constrained_columns") == [
            "server_id"
        ]:
            return fk.get("name")
    return None


def upgrade() -> None:
    bind = op.get_bind()
    fk_name = _get_logs_server_fk_name(bind)

    with op.batch_alter_table("logs", recreate="always") as batch_op:
        if fk_name:
            batch_op.drop_constraint(fk_name, type_="foreignkey")
        batch_op.create_foreign_key(
            fk_name or "logs_server_id_fkey",
            "servers",
            ["server_id"],
            ["id"],
            ondelete="CASCADE",
        )


def downgrade() -> None:
    bind = op.get_bind()
    fk_name = _get_logs_server_fk_name(bind)

    with op.batch_alter_table("logs", recreate="always") as batch_op:
        if fk_name:
            batch_op.drop_constraint(fk_name, type_="foreignkey")
        batch_op.create_foreign_key(
            fk_name or "logs_server_id_fkey",
            "servers",
            ["server_id"],
            ["id"],
        )