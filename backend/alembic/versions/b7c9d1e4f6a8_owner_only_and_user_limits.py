"""owner-only admin access and per-user generation/Neuron limits

Revision ID: b7c9d1e4f6a8
Revises: 8d41f0b7c2e6
Create Date: 2026-11-26 01:10:00.000000

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b7c9d1e4f6a8"
down_revision: str | None = "8d41f0b7c2e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "generations_bonus",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("0"),
            )
        )
        batch_op.add_column(
            sa.Column(
                "neurons_bonus",
                sa.Float(),
                nullable=False,
                server_default=sa.text("0"),
            )
        )
        batch_op.add_column(sa.Column("neurons_limit_override", sa.Float(), nullable=True))

    # Only the account matching OWNER_TG_ID may administer the product.
    op.execute("UPDATE users SET role = 'user' WHERE role IN ('manager', 'admin')")


def downgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("neurons_limit_override")
        batch_op.drop_column("neurons_bonus")
        batch_op.drop_column("generations_bonus")
    # Demoted manager/admin roles are not restored: access stays owner-only.
