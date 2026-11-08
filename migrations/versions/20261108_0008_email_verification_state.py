"""Separate email verification state from account activation."""

from alembic import op
import sqlalchemy as sa


revision = "20261108_0008"
down_revision = "20261108_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("email_verified_at", sa.DateTime(timezone=True)))
    op.execute(
        sa.text(
            "UPDATE users SET email_verified_at = created_at "
            "WHERE is_active = 1 AND email_verified_at IS NULL"
        )
    )


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_column("email_verified_at")
