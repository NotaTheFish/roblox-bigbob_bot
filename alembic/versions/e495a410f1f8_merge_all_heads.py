"""merge all heads

Revision ID: e495a410f1f8
Revises: 2d6da8b27afc, 3a8be54c8497, 4a3c68e8c8a2
Create Date: 2025-11-15 16:57:36.384616

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e495a410f1f8'
down_revision: Union[str, Sequence[str], None] = ('2d6da8b27afc', '3a8be54c8497', '4a3c68e8c8a2')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
