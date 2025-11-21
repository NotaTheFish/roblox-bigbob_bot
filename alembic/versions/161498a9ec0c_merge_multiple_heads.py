"""merge multiple heads

Revision ID: 161498a9ec0c
Revises: 779d95b1a3b4, c71ea3c01cbb
Create Date: 2025-11-21 18:26:22.521707

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '161498a9ec0c'
down_revision: Union[str, Sequence[str], None] = ('779d95b1a3b4', 'c71ea3c01cbb')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
