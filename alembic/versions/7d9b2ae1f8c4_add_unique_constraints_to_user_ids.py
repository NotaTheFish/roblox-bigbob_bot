"""add unique constraints for user identifiers

Revision ID: 7d9b2ae1f8c4
Revises: 4208b3098946
Create Date: 2025-12-09 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "7d9b2ae1f8c4"
down_revision: Union[str, Sequence[str], None] = "4208b3098946"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_CHECK_DUPLICATES_QUERY = """
SELECT {column} AS value, array_agg(id ORDER BY id) AS ids
FROM users
WHERE {column} IS NOT NULL
GROUP BY {column}
HAVING count(*) > 1
"""


def _assert_no_duplicates(conn, column_name: str) -> None:
    duplicate_rows = conn.execute(sa.text(_CHECK_DUPLICATES_QUERY.format(column=column_name)))
    duplicates = duplicate_rows.fetchall()

    if duplicates:
        formatted = ", ".join(f"{row.value} -> {row.ids}" for row in duplicates)
        raise RuntimeError(
            "Cannot add a UNIQUE constraint to users.{column} because duplicates exist: {details}".format(
                column=column_name,
                details=formatted,
            )
        )


def _has_unique_telegram(conn) -> bool:
    inspector = sa.inspect(conn)

    telegram_uniques = [
        constraint["column_names"]
        for constraint in inspector.get_unique_constraints("users")
    ]

    telegram_unique_indexes = [
        index["column_names"]
        for index in inspector.get_indexes("users")
        if index.get("unique")
    ]

    return ["telegram_id"] in telegram_uniques or ["telegram_id"] in telegram_unique_indexes


def upgrade() -> None:
    conn = op.get_bind()

    _assert_no_duplicates(conn, "telegram_id")
    _assert_no_duplicates(conn, "roblox_id")

    op.create_index(
        "uq_users_roblox_id_not_null",
        "users",
        ["roblox_id"],
        unique=True,
        postgresql_where=sa.text("roblox_id IS NOT NULL"),
    )

    if not _has_unique_telegram(conn):
        op.create_unique_constraint("uq_users_telegram_id", "users", ["telegram_id"])


def downgrade() -> None:
    conn = op.get_bind()

    inspector = sa.inspect(conn)
    index_names = {index["name"] for index in inspector.get_indexes("users")}
    if "uq_users_roblox_id_not_null" in index_names:
        op.drop_index("uq_users_roblox_id_not_null", table_name="users")

    unique_constraint_names = {constraint["name"] for constraint in inspector.get_unique_constraints("users")}
    if "uq_users_telegram_id" in unique_constraint_names:
        op.drop_constraint("uq_users_telegram_id", "users", type_="unique")