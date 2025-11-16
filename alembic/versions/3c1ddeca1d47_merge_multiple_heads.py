"""merge multiple heads

Revision ID: 3c1ddeca1d47
Revises: 0e2fb9608c58, 3d487062b1cc
Create Date: 2025-11-16 15:34:19.365350

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3c1ddeca1d47'
down_revision: Union[str, Sequence[str], None] = ('0e2fb9608c58', '3d487062b1cc')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
