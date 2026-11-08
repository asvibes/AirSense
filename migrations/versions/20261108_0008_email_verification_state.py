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
    users = sa.table(
        "users",
        sa.column("is_active", sa.Boolean),
        sa.column("email_verified_at", sa.DateTime(timezone=True)),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )
    op.execute(
        sa.update(users)
        .where(
            users.c.is_active.is_(True),
            users.c.email_verified_at.is_(None),
        )
        .values(email_verified_at=users.c.created_at)
    )


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_column("email_verified_at")
