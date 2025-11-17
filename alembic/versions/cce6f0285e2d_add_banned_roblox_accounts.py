"""add banned roblox accounts table

Revision ID: cce6f0285e2d
Revises: 6f3af269808d
Create Date: 2024-05-05 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "cce6f0285e2d"
down_revision = "6f3af269808d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "banned_roblox_accounts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("roblox_id", sa.String(length=255), nullable=True),
        sa.Column("username", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_banned_roblox_accounts_roblox_id",
        "banned_roblox_accounts",
        ["roblox_id"],
        unique=False,
    )
    op.create_index(
        "ix_banned_roblox_accounts_username",
        "banned_roblox_accounts",
        ["username"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_banned_roblox_accounts_username",
        table_name="banned_roblox_accounts",
    )
    op.drop_index(
        "ix_banned_roblox_accounts_roblox_id",
        table_name="banned_roblox_accounts",
    )
    op.drop_table("banned_roblox_accounts")