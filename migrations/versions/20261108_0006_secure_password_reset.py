"""Add secure password reset state and session invalidation version."""

from alembic import op
import sqlalchemy as sa


revision = "20261108_0006"
down_revision = "20261107_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(
            sa.Column("session_version", sa.Integer(), nullable=False, server_default="0")
        )
    with op.batch_alter_table("email_challenges") as batch:
        batch.add_column(sa.Column("reset_token_hash", sa.String(length=64)))
        batch.add_column(sa.Column("reset_token_expires_at", sa.DateTime(timezone=True)))
        batch.add_column(sa.Column("reset_token_used_at", sa.DateTime(timezone=True)))
        batch.create_unique_constraint(
            "uq_email_challenges_reset_token_hash",
            ["reset_token_hash"],
        )


def downgrade() -> None:
    with op.batch_alter_table("email_challenges") as batch:
        batch.drop_constraint("uq_email_challenges_reset_token_hash", type_="unique")
        batch.drop_column("reset_token_used_at")
        batch.drop_column("reset_token_expires_at")
        batch.drop_column("reset_token_hash")
    with op.batch_alter_table("users") as batch:
        batch.drop_column("session_version")
