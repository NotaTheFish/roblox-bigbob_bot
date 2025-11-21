"""merge multiple heads

Revision ID: 28529b12488b
Revises: 1c2e6b0d7f9c, 7c6f869bb4a8
Create Date: 2025-11-21 16:39:52.027568

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '28529b12488b'
down_revision: Union[str, Sequence[str], None] = ('1c2e6b0d7f9c', '7c6f869bb4a8')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
