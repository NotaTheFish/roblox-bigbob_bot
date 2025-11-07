"""Add url and closed message columns to servers"""

from alembic import op
import sqlalchemy as sa


revision = "4e2f3d18d8c4"
down_revision = "3b6c62ccf4a2"
branch_labels = None
depends_on = None


DEFAULT_CLOSED_MESSAGE = "Сервер закрыт"


def upgrade() -> None:
    op.add_column("servers", sa.Column("url", sa.String(), nullable=True))
    op.add_column(
        "servers",
        sa.Column(
            "closed_message",
            sa.String(),
            nullable=True,
            server_default=DEFAULT_CLOSED_MESSAGE,
        ),
    )



def downgrade() -> None:
    op.drop_column("servers", "closed_message")
    op.drop_column("servers", "url")