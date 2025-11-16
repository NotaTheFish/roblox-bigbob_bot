"""merge multiple heads

Revision ID: f2839f5ea78b
Revises: 3c1ddeca1d47, d8a0f84c1a3d
Create Date: 2025-11-16 15:51:01.272289

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f2839f5ea78b'
down_revision: Union[str, Sequence[str], None] = ('3c1ddeca1d47', 'd8a0f84c1a3d')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
