"""Init clean schema"""

from alembic import op

revision = "000000000001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Drop public schema only if exists
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = 'public') THEN
                EXECUTE 'DROP SCHEMA public CASCADE';
            END IF;
        END $$;
    """)

    # Recreate schema
    op.execute("CREATE SCHEMA IF NOT EXISTS public;")


def downgrade():
    op.execute("DROP SCHEMA public CASCADE;")
    op.execute("CREATE SCHEMA public;")

