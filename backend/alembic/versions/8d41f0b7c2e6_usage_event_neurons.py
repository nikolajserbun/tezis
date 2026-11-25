"""track Neurons spent per usage event

Revision ID: 8d41f0b7c2e6
Revises: a3f6c21d9b40
Create Date: 2026-11-26 00:10:00.000000

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "8d41f0b7c2e6"
down_revision: str | None = "a3f6c21d9b40"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("usage_events", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "neurons", sa.Float(), nullable=False, server_default=sa.text("0")
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("usage_events", schema=None) as batch_op:
        batch_op.drop_column("neurons")
