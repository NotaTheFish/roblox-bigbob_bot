"""Fix metadata / meta column names — universal safe migration"""

from alembic import op
import sqlalchemy as sa

# If you want you can set real revision IDs here
revision = "fix_meta_metadata_all"
down_revision = None
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


def safe_rename(table, old, new):
    try:
        op.execute(f'ALTER TABLE "{table}" RENAME COLUMN "{old}" TO "{new}";')
    except Exception:
        pass


def upgrade():
    # meta -> metadata, if exists
    for table in tables:
        safe_rename(table, "meta", "metadata")

    # metadata -> metadata_json, if exists
    for table in tables:
        safe_rename(table, "metadata", "metadata_json")


def downgrade():
    # rollback: metadata_json -> metadata (if exists)
    for table in tables:
        safe_rename(table, "metadata_json", "metadata")

    # metadata -> meta (if exists)
    for table in tables:
        safe_rename(table, "metadata", "meta")
