"""Add user_id to user_achievements"""

from alembic import op
import sqlalchemy as sa


revision = "3b6c62ccf4a2"
down_revision = "2d66446331a84fbe8e3b0f90a9210a8d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_achievements",
        sa.Column("user_id", sa.Integer(), nullable=True),
    )
    op.execute(
        """
        UPDATE user_achievements
        SET user_id = (
            SELECT users.id FROM users WHERE users.telegram_id = user_achievements.tg_id
        )
        """
    )
    op.alter_column(
        "user_achievements",
        "user_id",
        existing_type=sa.Integer(),
        nullable=False,
    )
    op.create_index(
        op.f("ix_user_achievements_user_id"),
        "user_achievements",
        ["user_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_user_achievements_user_id_users",
        "user_achievements",
        "users",
        ["user_id"],
        ["id"],
        ondelete=None,
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_user_achievements_user_id_users",
        "user_achievements",
        type_="foreignkey",
    )
    op.drop_index(
        op.f("ix_user_achievements_user_id"),
        table_name="user_achievements",
    )
    op.drop_column("user_achievements", "user_id")