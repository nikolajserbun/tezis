"""replace generation quotas with a weekly Neuron allowance

Subscription plans now grant a fixed number of Neurons every 7 days; free
accounts keep a one-off lifetime budget. Generation counters are gone.

Revision ID: d5e7f9a1b2c3
Revises: b7c9d1e4f6a8
Create Date: 2026-11-28 12:00:00.000000

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d5e7f9a1b2c3"
down_revision: str | None = "b7c9d1e4f6a8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("products", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "neurons_per_week",
                sa.Float(),
                nullable=False,
                server_default=sa.text("0"),
            )
        )
    # Existing tariffs keep their tier allowance; digital products get zero.
    op.execute(
        """
        UPDATE products
        SET neurons_per_week = CASE
            WHEN slug LIKE 'start-%' THEN 500
            WHEN slug LIKE 'pro-%' THEN 1000
            WHEN slug LIKE 'studio-%' THEN 2500
            ELSE 0
        END
        """
    )
    with op.batch_alter_table("products", schema=None) as batch_op:
        batch_op.drop_column("generations_per_month")

    with op.batch_alter_table("subscriptions", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "neurons_per_week",
                sa.Float(),
                nullable=False,
                server_default=sa.text("0"),
            )
        )
    op.execute(
        """
        UPDATE subscriptions
        SET neurons_per_week = COALESCE(
            (SELECT p.neurons_per_week FROM products p
             WHERE p.id = subscriptions.product_id),
            0
        )
        """
    )
    with op.batch_alter_table("subscriptions", schema=None) as batch_op:
        batch_op.drop_column("generations_used")
        batch_op.drop_column("generations_limit")

    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("generations_bonus")

    op.execute("DELETE FROM settings WHERE key = 'free_generations'")


def downgrade() -> None:
    with op.batch_alter_table("products", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "generations_per_month",
                sa.Integer(),
                nullable=True,
            )
        )
        batch_op.drop_column("neurons_per_week")

    with op.batch_alter_table("subscriptions", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "generations_limit",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("0"),
            )
        )
        batch_op.add_column(
            sa.Column(
                "generations_used",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("0"),
            )
        )
        batch_op.drop_column("neurons_per_week")

    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "generations_bonus",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("0"),
            )
        )

    # Generation counters from the old quota system cannot be reconstructed.
    op.execute(
        """
        INSERT INTO settings (key, value, updated_at)
        SELECT 'free_generations', '5', CURRENT_TIMESTAMP
        WHERE NOT EXISTS (
            SELECT 1 FROM settings WHERE key = 'free_generations'
        )
        """
    )
