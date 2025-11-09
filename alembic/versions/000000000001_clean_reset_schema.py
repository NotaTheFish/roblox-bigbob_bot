"""Init schema without dropping alembic_version"""

from alembic import op

revision = "000000000001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ✅ Удаляем только таблицы public, но не трогаем alembic_version
    op.execute("""
        DO $$ DECLARE
            r RECORD;
        BEGIN
            FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = 'public') LOOP
                EXECUTE 'DROP TABLE IF EXISTS public.' || quote_ident(r.tablename) || ' CASCADE';
            END LOOP;
        END $$;
    """)
