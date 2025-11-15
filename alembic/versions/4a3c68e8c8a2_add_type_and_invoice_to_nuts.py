"""add type and invoice reference to nuts transactions

Revision ID: 4a3c68e8c8a2
Revises: f1b0a943f5aa
Create Date: 2025-02-21 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "4a3c68e8c8a2"
down_revision: Union[str, Sequence[str], None] = "f1b0a943f5aa"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "nuts_transactions",
        sa.Column(
            "type",
            sa.String(length=64),
            nullable=False,
            server_default="unknown",
        ),
    )
    op.add_column(
        "nuts_transactions",
        sa.Column("related_invoice", sa.Integer(), nullable=True),
    )
    op.create_index(
        "ix_nuts_transactions_related_invoice",
        "nuts_transactions",
        ["related_invoice"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_nuts_transactions_related_invoice",
        "nuts_transactions",
        "invoices",
        ["related_invoice"],
        ["id"],
    )

    op.execute(
        """
        UPDATE nuts_transactions
        SET type = COALESCE("metadata"->>'source', 'unknown')
        """
    )
    op.execute(
        """
        UPDATE nuts_transactions
        SET related_invoice = CAST("metadata"->>'invoice_id' AS INTEGER)
        WHERE "metadata" ? 'invoice_id' AND ("metadata"->>'invoice_id') ~ '^[0-9]+$'
        """
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_nuts_transactions_related_invoice",
        "nuts_transactions",
        type_="foreignkey",
    )
    op.drop_index(
        "ix_nuts_transactions_related_invoice",
        table_name="nuts_transactions",
    )
    op.drop_column("nuts_transactions", "related_invoice")
    op.drop_column("nuts_transactions", "type")