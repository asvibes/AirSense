import sqlite3
from pathlib import Path

from flask import current_app, g


SCHEMA = """
CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    room_name TEXT NOT NULL COLLATE NOCASE,
    status TEXT NOT NULL CHECK (status IN ('active', 'acknowledged', 'cleared')),
    trigger_co2_ppm REAL NOT NULL CHECK (trigger_co2_ppm >= 0),
    threshold_ppm REAL NOT NULL CHECK (threshold_ppm > 0),
    latest_co2_ppm REAL NOT NULL CHECK (latest_co2_ppm >= 0),
    created_at TEXT NOT NULL,
    acknowledged_at TEXT,
    acknowledged_by TEXT,
    cleared_at TEXT,
    CHECK (
        (status = 'active' AND acknowledged_at IS NULL AND acknowledged_by IS NULL AND cleared_at IS NULL)
        OR (status = 'acknowledged' AND acknowledged_at IS NOT NULL AND acknowledged_by IS NOT NULL AND cleared_at IS NULL)
        OR (status = 'cleared' AND cleared_at IS NOT NULL)
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS one_open_alert_per_room
ON alerts (room_name COLLATE NOCASE)
WHERE status IN ('active', 'acknowledged');
"""


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        database = current_app.config["DATABASE"]
        if database != ":memory:":
            Path(database).parent.mkdir(parents=True, exist_ok=True)

        connection = sqlite3.connect(database, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        g.db = connection

    return g.db


def close_db(_error: BaseException | None = None) -> None:
    connection = g.pop("db", None)
    if connection is not None:
        connection.close()


def init_db(app) -> None:
    app.teardown_appcontext(close_db)
    with app.app_context():
        get_db().executescript(SCHEMA)