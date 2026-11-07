"""Store one-time email verification and password reset challenges.

Revision ID: 20261107_0005
Revises: 20261105_0004
"""
from alembic import op
import sqlalchemy as sa


revision = "20261107_0005"
down_revision = "20261105_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "email_challenges",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id")),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("purpose", sa.String(length=32), nullable=False),
        sa.Column("otp_hash", sa.String(length=64), nullable=False),
        sa.Column(
    "created_at",
    sa.DateTime(timezone=True),
    nullable=False,
    server_default=sa.func.now(),
),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_sent_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_email_challenges_email", "email_challenges", ["email"])
    op.create_index("ix_email_challenges_purpose", "email_challenges", ["purpose"])


def downgrade() -> None:
    op.drop_index("ix_email_challenges_purpose", table_name="email_challenges")
    op.drop_index("ix_email_challenges_email", table_name="email_challenges")
    op.drop_table("email_challenges")
