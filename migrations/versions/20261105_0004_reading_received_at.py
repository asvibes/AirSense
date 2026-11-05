"""Persist server-side reading receipt timestamps.

Revision ID: 20261105_0004
Revises: 20261028_0003
"""
from alembic import op
import sqlalchemy as sa


revision = "20261105_0004"
down_revision = "20261028_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "air_readings",
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("air_readings", "received_at")
