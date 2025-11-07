"""add full name to admin requests"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d9a829c3be43"
down_revision = "b8301f953511"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("admin_requests", sa.Column("full_name", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("admin_requests", "full_name")