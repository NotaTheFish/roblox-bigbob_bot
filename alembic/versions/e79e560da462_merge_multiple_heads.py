"""merge multiple heads

Revision ID: e79e560da462
Revises: 2f3c98d0497c, 7e3afcbb2a1c
Create Date: 2025-11-23 14:23:06.519455

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e79e560da462'
down_revision: Union[str, Sequence[str], None] = ('2f3c98d0497c', '7e3afcbb2a1c')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
