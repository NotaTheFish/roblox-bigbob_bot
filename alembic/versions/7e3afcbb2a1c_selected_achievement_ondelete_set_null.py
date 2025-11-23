"""Set selected achievement foreign key to ON DELETE SET NULL"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "7e3afcbb2a1c"
down_revision: Union[str, Sequence[str], None] = "0e2fb9608c58"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "UPDATE users SET selected_achievement_id = NULL "
        "WHERE selected_achievement_id IS NOT NULL "
        "AND selected_achievement_id NOT IN (SELECT id FROM achievements)"
    )
    op.drop_constraint(
        "users_selected_achievement_id_fkey", "users", type_="foreignkey"
    )
    op.create_foreign_key(
        "users_selected_achievement_id_fkey",
        "users",
        "achievements",
        ["selected_achievement_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "users_selected_achievement_id_fkey", "users", type_="foreignkey"
    )
    op.create_foreign_key(
        "users_selected_achievement_id_fkey",
        "users",
        "achievements",
        ["selected_achievement_id"],
        ["id"],
    )