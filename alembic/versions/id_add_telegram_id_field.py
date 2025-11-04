"""Add telegram_id field to users"""

from alembic import op
import sqlalchemy as sa

# ✅ Правильные Alembic-идентификаторы
revision = "8f2c8b9a3c2b"
down_revision = None  # Если появятся новые миграции — он изменится
branch_labels = None
depends_on = None


def upgrade():
    # добавляем столбец telegram_id если его нет
    op.add_column(
        "users",
        sa.Column("telegram_id", sa.BigInteger(), nullable=True, unique=True)
    )


def downgrade():
    op.drop_column("users", "telegram_id")
