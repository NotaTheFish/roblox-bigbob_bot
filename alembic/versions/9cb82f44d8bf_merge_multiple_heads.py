"""merge multiple heads

Revision ID: 9cb82f44d8bf
Revises: 161498a9ec0c, bd3a1c9f86d4
Create Date: 2025-11-21 19:12:32.708000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9cb82f44d8bf'
down_revision: Union[str, Sequence[str], None] = ('161498a9ec0c', 'bd3a1c9f86d4')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
