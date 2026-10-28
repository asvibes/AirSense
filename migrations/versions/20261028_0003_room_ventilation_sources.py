"""Support multiple ventilation sources per room.

Revision ID: 20261028_0003
Revises: 20261028_0002
"""
from alembic import op
import sqlalchemy as sa


revision = "20261028_0003"
down_revision = "20261028_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "rooms",
        sa.Column(
            "ventilation_sources",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
    )
    rooms = sa.table(
        "rooms",
        sa.column("id", sa.String(64)),
        sa.column("ventilation", sa.String(80)),
        sa.column("ventilation_sources", sa.JSON()),
    )
    connection = op.get_bind()
    rows = connection.execute(sa.select(rooms.c.id, rooms.c.ventilation)).all()
    for row in rows:
        sources = [
            source.strip()
            for source in (row.ventilation or "").split(",")
            if source.strip()
        ] or ["Not specified"]
        connection.execute(
            rooms.update()
            .where(rooms.c.id == row.id)
            .values(ventilation_sources=sources)
        )


def downgrade() -> None:
    op.drop_column("rooms", "ventilation_sources")
