"""Add type to promocodes

Revision ID: 1e19634dfd34
Revises: c33e9e016497
Create Date: 2025-11-14 10:33:47.569913
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1e19634dfd34'
down_revision: Union[str, Sequence[str], None] = 'c33e9e016497'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # === Add new columns ===
    op.add_column(
        'promocodes',
        sa.Column('type', sa.String(length=32), nullable=True, server_default='nuts'),
    )
    op.add_column('promocodes', sa.Column('uses_count', sa.Integer(), nullable=False))
    op.add_column('promocodes', sa.Column('created_by', sa.BigInteger(), nullable=True))

    # === Fix problematic type change with explicit USING ===
    op.execute(
        '''
        ALTER TABLE promocodes
        ALTER COLUMN value TYPE double precision
        USING value::double precision;
        '''
    )

    # === Rest of modifications ===
    op.alter_column('promocodes', 'max_uses',
                    existing_type=sa.INTEGER(),
                    nullable=False)

    op.drop_column('promocodes', 'uses')
    op.drop_column('promocodes', 'reward_type')
    op.drop_column('promocodes', 'promo_type')
    op.drop_column('promocodes', 'reward_amount')


def downgrade() -> None:
    """Downgrade schema."""
    # === Restore dropped columns ===
    op.add_column('promocodes', sa.Column('reward_amount', sa.INTEGER(), autoincrement=False, nullable=False))
    op.add_column('promocodes', sa.Column('promo_type', sa.VARCHAR(length=32), autoincrement=False, nullable=False))
    op.add_column('promocodes', sa.Column('reward_type', sa.VARCHAR(length=32), autoincrement=False, nullable=False))
    op.add_column('promocodes', sa.Column('uses', sa.INTEGER(), autoincrement=False, nullable=False))

    # === Revert type change ===
    op.alter_column('promocodes', 'max_uses',
                    existing_type=sa.INTEGER(),
                    nullable=True)

    op.execute(
        '''
        ALTER TABLE promocodes
        ALTER COLUMN value TYPE varchar(255)
        USING value::varchar(255);
        '''
    )

    op.drop_column('promocodes', 'created_by')
    op.drop_column('promocodes', 'uses_count')
    op.drop_column('promocodes', 'type')
