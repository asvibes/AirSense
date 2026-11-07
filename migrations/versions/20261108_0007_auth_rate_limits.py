"""Add persistent authentication rate-limit buckets."""

from alembic import op
import sqlalchemy as sa


revision = "20261108_0007"
down_revision = "20261108_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rate_limit_buckets",
        sa.Column("key", sa.String(length=255), primary_key=True),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_table("rate_limit_buckets")
