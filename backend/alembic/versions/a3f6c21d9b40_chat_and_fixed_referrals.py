"""chat messages and fixed referral bonus

Revision ID: a3f6c21d9b40
Revises: 62190869ec3b
Create Date: 2026-11-25 21:10:00.000000

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a3f6c21d9b40"
down_revision: str | None = "62190869ec3b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "chat_messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("sources", sa.JSON(), nullable=False),
        sa.Column("demo_mode", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("chat_messages", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_chat_messages_created_at"), ["created_at"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_chat_messages_user_id"), ["user_id"], unique=False
        )

    with op.batch_alter_table("referral_earnings", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("referee_id", sa.Uuid(), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "source",
                sa.String(length=20),
                server_default="order",
                nullable=False,
            )
        )
        batch_op.alter_column(
            "order_id", existing_type=sa.Uuid(), nullable=True
        )
        batch_op.create_foreign_key(
            "fk_referral_earnings_referee",
            "users",
            ["referee_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch_op.create_unique_constraint(
            "uq_referral_earning_referee", ["referee_id"]
        )
        batch_op.alter_column("source", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("referral_earnings", schema=None) as batch_op:
        batch_op.drop_constraint("uq_referral_earning_referee", type_="unique")
        batch_op.drop_constraint("fk_referral_earnings_referee", type_="foreignkey")
        batch_op.drop_column("source")
        batch_op.drop_column("referee_id")
        batch_op.alter_column(
            "order_id", existing_type=sa.Uuid(), nullable=False
        )
    op.drop_table("chat_messages")
