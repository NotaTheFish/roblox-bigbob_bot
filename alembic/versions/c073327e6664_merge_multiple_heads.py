"""merge multiple heads

Revision ID: c073327e6664
Revises: 2dc41feab276, d9a829c3be43
Create Date: 2025-11-07 23:45:05.748754

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c073327e6664'
down_revision: Union[str, Sequence[str], None] = ('2dc41feab276', 'd9a829c3be43')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
