import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterator

from app.models.alert import Alert, AlertStatus
from app.services.alerts.all_clear import (
    InvalidAlertTransition,
    acknowledged_status,
    reading_action,
)


class AlertNotFound(LookupError):
    pass


@contextmanager
def _write_transaction(connection: sqlite3.Connection) -> Iterator[None]:
    connection.execute("BEGIN IMMEDIATE")
    try:
        yield
    except BaseException:
        connection.rollback()
        raise
    else:
        connection.commit()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def list_alerts(connection: sqlite3.Connection) -> list[dict]:
    rows = connection.execute(
        "SELECT * FROM alerts ORDER BY created_at DESC, id DESC"
    ).fetchall()
    return [Alert.from_row(row).to_dict() for row in rows]


def process_reading(
    connection: sqlite3.Connection,
    room_name: str,
    co2_ppm: float,
    threshold_ppm: float,
) -> tuple[dict | None, str]:
    now = _utc_now()

    with _write_transaction(connection):
        row = connection.execute(
            """
            SELECT * FROM alerts
            WHERE room_name = ? AND status IN ('active', 'acknowledged')
            ORDER BY id DESC
            LIMIT 1
            """,
            (room_name,),
        ).fetchone()
        alert = Alert.from_row(row) if row is not None else None
        action = reading_action(
            alert.status if alert is not None else None,
            co2_ppm,
            alert.threshold_ppm if alert is not None else threshold_ppm,
        )

        if action == "open":
            cursor = connection.execute(
                """
                INSERT INTO alerts (
                    room_name, status, trigger_co2_ppm, threshold_ppm,
                    latest_co2_ppm, created_at
                )
                VALUES (?, 'active', ?, ?, ?, ?)
                """,
                (room_name, co2_ppm, threshold_ppm, co2_ppm, now),
            )
            alert_id = cursor.lastrowid
        elif action == "update":
            connection.execute(
                "UPDATE alerts SET latest_co2_ppm = ? WHERE id = ?",
                (co2_ppm, alert.id),
            )
            alert_id = alert.id
        elif action == "clear":
            connection.execute(
                """
                UPDATE alerts
                SET status = 'cleared', latest_co2_ppm = ?, cleared_at = ?
                WHERE id = ?
                """,
                (co2_ppm, now, alert.id),
            )
            alert_id = alert.id
        else:
            alert_id = None

        updated = (
            connection.execute("SELECT * FROM alerts WHERE id = ?", (alert_id,)).fetchone()
            if alert_id is not None
            else None
        )

    return (Alert.from_row(updated).to_dict() if updated is not None else None, action)


def acknowledge_alert(
    connection: sqlite3.Connection,
    alert_id: int,
    acknowledged_by: str,
) -> dict:
    with _write_transaction(connection):
        row = connection.execute(
            "SELECT * FROM alerts WHERE id = ?", (alert_id,)
        ).fetchone()
        if row is None:
            raise AlertNotFound(f"Alert {alert_id} was not found.")

        alert = Alert.from_row(row)
        new_status = acknowledged_status(alert.status)
        if new_status is not alert.status:
            connection.execute(
                """
                UPDATE alerts
                SET status = 'acknowledged', acknowledged_at = ?, acknowledged_by = ?
                WHERE id = ?
                """,
                (_utc_now(), acknowledged_by, alert_id),
            )

        updated = connection.execute(
            "SELECT * FROM alerts WHERE id = ?", (alert_id,)
        ).fetchone()

    return Alert.from_row(updated).to_dict()
