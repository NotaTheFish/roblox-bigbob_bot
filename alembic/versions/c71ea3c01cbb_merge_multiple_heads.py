"""merge multiple heads

Revision ID: c71ea3c01cbb
Revises: 28529b12488b, 9a4b7b6f4c3c
Create Date: 2025-11-21 17:49:35.323267

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c71ea3c01cbb'
down_revision: Union[str, Sequence[str], None] = ('28529b12488b', '9a4b7b6f4c3c')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
