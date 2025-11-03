"""Add telegram_id field to users"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "1a2b3c4d5e6f"

down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('telegram_id', sa.BigInteger(), nullable=True))


def downgrade():
    op.drop_column('users', 'telegram_id')
