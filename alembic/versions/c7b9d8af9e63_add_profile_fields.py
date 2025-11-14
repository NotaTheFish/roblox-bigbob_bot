"""add profile fields to users

Revision ID: c7b9d8af9e63
Revises: 9d5ab0dd9f77
Create Date: 2024-06-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c7b9d8af9e63"
down_revision: Union[str, Sequence[str], None] = "9d5ab0dd9f77"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("about_text", sa.Text(), nullable=True))
    op.add_column(
        "users",
        sa.Column("selected_achievement_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_users_selected_achievement_id",
        "users",
        "achievements",
        ["selected_achievement_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_users_selected_achievement_id", "users", type_="foreignkey")
    op.drop_column("users", "selected_achievement_id")
    op.drop_column("users", "about_text")