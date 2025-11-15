"""Seed default TON→nuts rate setting

Revision ID: 2d6da8b27afc
Revises: f1b0a943f5aa
Create Date: 2025-02-14 00:00:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import orm


# revision identifiers, used by Alembic.
revision: str = "2d6da8b27afc"
down_revision: Union[str, Sequence[str], None] = "f1b0a943f5aa"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TON_RATE_KEY = "ton_to_nuts_rate"
DEFAULT_TON_RATE = "210.0"

settings_table = sa.table(
    "settings",
    sa.column("id", sa.Integer()),
    sa.column("key", sa.String(length=255)),
    sa.column("value", sa.JSON()),
    sa.column("description", sa.Text()),
)


def upgrade() -> None:
    bind = op.get_bind()
    session = orm.Session(bind=bind)

    payload = {"value": DEFAULT_TON_RATE}

    try:
        existing = session.execute(
            sa.select(settings_table.c.id).where(settings_table.c.key == TON_RATE_KEY)
        ).first()

        if existing:
            session.execute(
                settings_table.update()
                .where(settings_table.c.key == TON_RATE_KEY)
                .values(value=payload)
            )
        else:
            session.execute(
                settings_table.insert().values(
                    key=TON_RATE_KEY,
                    value=payload,
                    description="TON→nuts exchange rate used for TON payments",
                )
            )

        session.commit()
    finally:
        session.close()


def downgrade() -> None:
    # Data migrations are not easily reversible without losing operator-provided values.
    pass