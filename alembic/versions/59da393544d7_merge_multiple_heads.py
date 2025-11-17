"""merge multiple heads

Revision ID: 59da393544d7
Revises: 5a52c3c28494, cce6f0285e2d
Create Date: 2025-11-17 14:05:18.573317

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '59da393544d7'
down_revision: Union[str, Sequence[str], None] = ('5a52c3c28494', 'cce6f0285e2d')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
