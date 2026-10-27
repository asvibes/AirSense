"""Create portable AirSense alert lifecycle tables.

Revision ID: 20261027_0001
Revises:
"""
from alembic import op
import sqlalchemy as sa


revision = "20261027_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "homes",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
    )
    op.create_table(
        "rooms",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("home_id", sa.String(64), sa.ForeignKey("homes.id"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.UniqueConstraint("home_id", "name", name="uq_rooms_home_name"),
    )
    op.create_index(
        "uq_rooms_home_lower_name",
        "rooms",
        ["home_id", sa.text("lower(name)")],
        unique=True,
    )
    op.create_table(
        "metrics",
        sa.Column("code", sa.String(32), primary_key=True),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("unit", sa.String(24), nullable=False),
    )
    op.create_table(
        "threshold_policies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("home_id", sa.String(64), sa.ForeignKey("homes.id"), nullable=False),
        sa.Column("room_id", sa.String(64), sa.ForeignKey("rooms.id"), nullable=False),
        sa.Column("metric_code", sa.String(32), sa.ForeignKey("metrics.code"), nullable=False),
        sa.Column("high_threshold", sa.Float(), nullable=False),
        sa.Column("elevated_threshold", sa.Float(), nullable=False),
        sa.Column("elevated_duration_seconds", sa.Integer(), nullable=False),
        sa.Column("rapid_rise_per_minute", sa.Float(), nullable=False),
        sa.Column("all_clear_duration_seconds", sa.Integer(), nullable=False),
        sa.Column("max_reading_gap_seconds", sa.Integer(), nullable=False),
        sa.Column("elevated_since", sa.DateTime(timezone=True)),
        sa.UniqueConstraint(
            "home_id", "room_id", "metric_code", name="uq_threshold_policy_scope"
        ),
    )
    op.create_table(
        "air_readings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("home_id", sa.String(64), sa.ForeignKey("homes.id"), nullable=False),
        sa.Column("room_id", sa.String(64), sa.ForeignKey("rooms.id"), nullable=False),
        sa.Column("metric_code", sa.String(32), sa.ForeignKey("metrics.code"), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("source", sa.String(24), nullable=False),
        sa.Column("measured_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "home_id",
            "room_id",
            "metric_code",
            "measured_at",
            name="uq_readings_home_room_metric_time",
        ),
    )
    op.create_index(
        "ix_readings_home_room_metric_time",
        "air_readings",
        ["home_id", "room_id", "metric_code", "measured_at"],
    )
    op.create_table(
        "air_alerts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("home_id", sa.String(64), sa.ForeignKey("homes.id"), nullable=False),
        sa.Column("room_id", sa.String(64), sa.ForeignKey("rooms.id"), nullable=False),
        sa.Column("metric_code", sa.String(32), sa.ForeignKey("metrics.code"), nullable=False),
        sa.Column("level", sa.String(24), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("trigger_value", sa.Float(), nullable=False),
        sa.Column("threshold_value", sa.Float(), nullable=False),
        sa.Column("latest_value", sa.Float(), nullable=False),
        sa.Column("threshold_unit", sa.String(24), nullable=False),
        sa.Column("clear_duration_seconds", sa.Integer(), nullable=False),
        sa.Column("below_threshold_since", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True)),
        sa.Column("acknowledged_by", sa.String(120)),
        sa.Column("all_clear_at", sa.DateTime(timezone=True)),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "level IN ('high', 'elevated', 'rapid_rise')",
            name="ck_alerts_level",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'acknowledged', 'all_clear')",
            name="ck_alerts_status",
        ),
        sa.CheckConstraint(
            "(status = 'active' AND acknowledged_at IS NULL AND "
            "acknowledged_by IS NULL AND all_clear_at IS NULL) OR "
            "(status = 'acknowledged' AND acknowledged_at IS NOT NULL AND "
            "acknowledged_by IS NOT NULL AND all_clear_at IS NULL) OR "
            "(status = 'all_clear' AND all_clear_at IS NOT NULL AND "
            "((acknowledged_at IS NULL AND acknowledged_by IS NULL) OR "
            "(acknowledged_at IS NOT NULL AND acknowledged_by IS NOT NULL)))",
            name="ck_alerts_transition_metadata",
        ),
    )
    op.create_index(
        "uq_open_alert_home_room_metric_level",
        "air_alerts",
        ["home_id", "room_id", "metric_code", "level"],
        unique=True,
        postgresql_where=sa.text("status IN ('active', 'acknowledged')"),
        sqlite_where=sa.text("status IN ('active', 'acknowledged')"),
    )
    op.create_index(
        "ix_alerts_home_created_at", "air_alerts", ["home_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_alerts_home_created_at", table_name="air_alerts")
    op.drop_index("uq_open_alert_home_room_metric_level", table_name="air_alerts")
    op.drop_table("air_alerts")
    op.drop_index("ix_readings_home_room_metric_time", table_name="air_readings")
    op.drop_table("air_readings")
    op.drop_table("threshold_policies")
    op.drop_table("metrics")
    op.drop_index("uq_rooms_home_lower_name", table_name="rooms")
    op.drop_table("rooms")
    op.drop_table("homes")
