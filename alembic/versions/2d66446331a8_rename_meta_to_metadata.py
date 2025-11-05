"""Fix metadata / meta column names — universal safe migration"""

from alembic import op
import sqlalchemy as sa

revision = "2d66446331a84fbe8e3b0f90a9210a8d"
down_revision = "1f14fc542827"
branch_labels = None
depends_on = None


tables = [
    "game_progress",
    "promocodes",
    "servers",
    "products",
    "purchases",
    "payments",
    "withdrawals",
    "promocode_redemptions",
    "referrals",
    "referral_rewards",
    "topup_requests",
]


def _column_set(table_name):
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    try:
        columns = inspector.get_columns(table_name)
    except sa.exc.NoSuchTableError:
        return set()
    return {column["name"] for column in columns}


def safe_rename(table, old, new):
    columns = _column_set(table)

    if old not in columns or new in columns:
        return

    op.execute(sa.text(f'ALTER TABLE "{table}" RENAME COLUMN "{old}" TO "{new}"'))


def upgrade():
    for table in tables:
        safe_rename(table, "meta", "metadata")


def downgrade():
    for table in tables:
        safe_rename(table, "metadata", "meta")
