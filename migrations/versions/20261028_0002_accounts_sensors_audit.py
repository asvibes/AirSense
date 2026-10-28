"""Add user membership, sensor provisioning, and audit records.

Revision ID: 20261028_0002
Revises: 20261027_0001
"""
from alembic import op
import sqlalchemy as sa


revision = "20261028_0002"
down_revision = "20261027_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "rooms",
        sa.Column("ventilation", sa.String(80), nullable=False, server_default="Not specified"),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(254), nullable=False, unique=True),
        sa.Column("display_name", sa.String(120), nullable=False),
        sa.Column("password_hash", sa.String(256), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "home_memberships",
        sa.Column("home_id", sa.String(64), sa.ForeignKey("homes.id"), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_home_memberships_home_id", "home_memberships", ["home_id"])
    op.create_index("ix_home_memberships_user_id", "home_memberships", ["user_id"])
    op.create_table(
        "home_invitations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("home_id", sa.String(64), sa.ForeignKey("homes.id"), nullable=False),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("role", sa.String(16), nullable=False, server_default="member"),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "sensors",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("home_id", sa.String(64), sa.ForeignKey("homes.id"), nullable=False),
        sa.Column("room_id", sa.String(64), sa.ForeignKey("rooms.id"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("key_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("reporting_interval_seconds", sa.Integer(), nullable=False, server_default="300"),
        sa.Column("last_seen_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('active', 'revoked')", name="ck_sensors_status"),
        sa.CheckConstraint(
            "reporting_interval_seconds BETWEEN 30 AND 86400",
            name="ck_sensors_reporting_interval",
        ),
    )
    op.create_index("ix_sensors_home_room", "sensors", ["home_id", "room_id"])
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("home_id", sa.String(64), sa.ForeignKey("homes.id"), nullable=False),
        sa.Column("actor_user_id", sa.String(36), sa.ForeignKey("users.id")),
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("entity_type", sa.String(40), nullable=False),
        sa.Column("entity_id", sa.String(64)),
        sa.Column("details_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_audit_home_created", "audit_logs", ["home_id", "created_at"])
    with op.batch_alter_table("air_readings") as batch_op:
        batch_op.add_column(sa.Column("sensor_id", sa.String(36)))
        batch_op.create_foreign_key(
            "fk_air_readings_sensor_id_sensors", "sensors", ["sensor_id"], ["id"]
        )
    op.execute(
        "INSERT INTO metrics (code, name, unit) "
        "SELECT 'CO2', 'Carbon dioxide', 'ppm' "
        "WHERE NOT EXISTS (SELECT 1 FROM metrics WHERE code = 'CO2')"
    )


def downgrade() -> None:
    op.drop_column("rooms", "ventilation")
    with op.batch_alter_table("air_readings") as batch_op:
        batch_op.drop_constraint(
            "fk_air_readings_sensor_id_sensors", type_="foreignkey"
        )
        batch_op.drop_column("sensor_id")
    op.drop_index("ix_audit_home_created", table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_index("ix_sensors_home_room", table_name="sensors")
    op.drop_table("sensors")
    op.drop_table("home_invitations")
    op.drop_index("ix_home_memberships_user_id", table_name="home_memberships")
    op.drop_index("ix_home_memberships_home_id", table_name="home_memberships")
    op.drop_table("home_memberships")
    op.drop_table("users")
