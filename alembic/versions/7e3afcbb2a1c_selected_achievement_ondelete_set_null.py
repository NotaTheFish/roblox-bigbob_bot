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
    # 1. Удаляем все constraints на колонку selected_achievement_id
    op.execute("""
        DO $$
        DECLARE
            r RECORD;
        BEGIN
            FOR r IN
                SELECT constraint_name
                FROM information_schema.key_column_usage
                WHERE table_name = 'users'
                  AND column_name = 'selected_achievement_id'
            LOOP
                EXECUTE 'ALTER TABLE users DROP CONSTRAINT ' || r.constraint_name;
            END LOOP;
        END$$;
    """)

    # 2. Создаём новый FK с правилом SET NULL
    op.create_foreign_key(
        "fk_users_selected_achievement_id",
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