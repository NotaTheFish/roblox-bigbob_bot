"""Add achievement visibility, conditions and history metadata."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "3d487062b1cc"
down_revision = "e495a410f1f8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "achievements",
        sa.Column(
            "condition_type",
            sa.String(length=64),
            nullable=False,
            server_default="none",
        ),
    )
    op.add_column(
        "achievements",
        sa.Column("condition_value", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "achievements",
        sa.Column("condition_threshold", sa.Integer(), nullable=True),
    )
    op.add_column(
        "achievements",
        sa.Column(
            "is_visible",
            sa.Boolean(),
            nullable=False,
            server_default="true",
        ),
    )
    op.add_column(
        "achievements",
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "achievements",
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
    )
    op.add_column(
        "achievements",
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.add_column(
        "user_achievements",
        sa.Column(
            "source",
            sa.String(length=32),
            nullable=False,
            server_default="auto",
        ),
    )
    op.add_column(
        "user_achievements",
        sa.Column("comment", sa.Text(), nullable=True),
    )
    op.add_column(
        "user_achievements",
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("user_achievements", "metadata")
    op.drop_column("user_achievements", "comment")
    op.drop_column("user_achievements", "source")

    op.drop_column("achievements", "updated_at")
    op.drop_column("achievements", "created_at")
    op.drop_column("achievements", "metadata")
    op.drop_column("achievements", "is_visible")
    op.drop_column("achievements", "condition_threshold")
    op.drop_column("achievements", "condition_value")
    op.drop_column("achievements", "condition_type")