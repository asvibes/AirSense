import csv
import io
import re
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import MetaData, inspect, select, text

from app.db import get_session
from app.main import create_app
from app.models.alert import Alert
from app.models.audit import AuditLog
from app.models.home import Home
from app.models.reading import Reading
from app.models.room import Room
from app.models.sensor import Sensor
from app.models.user import HomeMembership, User


class DatabaseWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        database = Path(self.temp_dir.name) / "airsense-workflow.sqlite3"
        self.app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "workflow-test-secret",
                "DATABASE_URL": f"sqlite:///{database.as_posix()}",
                "AUTO_CREATE_SCHEMA": True,
                "MAX_LIVE_READING_AGE_SECONDS": 24 * 60 * 60,
                "HIGH_THRESHOLD": 1000,
                "ELEVATED_THRESHOLD": 800,
                "ELEVATED_DURATION_SECONDS": 300,
                "RAPID_RISE_PER_MINUTE": 100000,
                "ALL_CLEAR_DURATION_SECONDS": 1,
                "MAX_READING_GAP_SECONDS": 600,
            }
        )
        self.client = self.app.test_client()
        self.client.get("/register")
        self.csrf = self._csrf(self.client)

    def tearDown(self):
        self.app.extensions["airsense_engine"].dispose()
        self.temp_dir.cleanup()

    @staticmethod
    def _csrf(client):
        with client.session_transaction() as browser_session:
            return browser_session["csrf_token"]

    def _request(self, method, path, payload=None, *, client=None, headers=None):
        request_headers = {"X-CSRF-Token": self.csrf}
        request_headers.update(headers or {})
        return (client or self.client).open(
            path,
            method=method,
            json=payload,
            headers=request_headers,
        )

    def _assert_utc(self, value):
        self.assertRegex(value, re.compile(r"(Z|\+00:00)$"))
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        self.assertEqual(parsed.utcoffset(), timedelta(0))

    def test_complete_user_to_alert_database_workflow(self):
        registered = self._request(
            "POST",
            "/api/auth/register",
            {
                "email": "workflow@example.test",
                "display_name": "Workflow User",
                "password": "secure-password-123",
            },
        )
        self.assertEqual(registered.status_code, 201, registered.get_json())
        user_id = registered.get_json()["user"]["id"]
        self.csrf = self._csrf(self.client)

        created_home = self._request(
            "POST", "/api/homes", {"name": "Workflow Home"}
        )
        self.assertEqual(created_home.status_code, 201, created_home.get_json())
        home_id = created_home.get_json()["home"]["id"]

        created_room = self._request(
            "POST",
            f"/api/homes/{home_id}/rooms",
            {
                "name": "Workflow Room",
                "ventilation_sources": ["Window"],
            },
        )
        self.assertEqual(created_room.status_code, 201, created_room.get_json())
        room_id = created_room.get_json()["room"]["id"]

        thresholds = self._request(
            "PUT",
            f"/api/homes/{home_id}/thresholds",
            {
                "thresholds": [
                    {
                        "room_id": room_id,
                        "high_threshold": 1000,
                        "elevated_threshold": 800,
                        "elevated_duration_seconds": 300,
                        "rapid_rise_per_minute": 100000,
                        "all_clear_duration_seconds": 1,
                        "max_reading_gap_seconds": 600,
                    }
                ]
            },
        )
        self.assertEqual(thresholds.status_code, 200, thresholds.get_json())
        self.assertEqual(
            thresholds.get_json()["thresholds"][0]["high_threshold"], 1000
        )

        provisioned = self._request(
            "POST",
            f"/api/homes/{home_id}/sensors",
            {"name": "Workflow Sensor", "room_id": room_id},
        )
        self.assertEqual(provisioned.status_code, 201, provisioned.get_json())
        sensor_id = provisioned.get_json()["sensor"]["id"]
        device_key = provisioned.get_json()["device_key"]

        anonymous = self.app.test_client()
        self.assertEqual(
            anonymous.get(f"/api/homes/{home_id}/rooms").status_code, 401
        )
        unauthorized_device = self.client.post(
            f"/api/sensors/{sensor_id}/readings",
            json={
                "room": "Workflow Room",
                "value": 500,
                "measured_at": datetime.now(timezone.utc).isoformat(),
            },
            headers={"X-Device-Key": "not-the-device-key"},
        )
        self.assertEqual(unauthorized_device.status_code, 401)

        base_time = datetime.now(timezone.utc) - timedelta(seconds=30)

        def submit(value, seconds):
            return self.client.post(
                f"/api/sensors/{sensor_id}/readings",
                json={
                    "room": "Workflow Room",
                    "metric": "CO2",
                    "unit": "ppm",
                    "value": value,
                    "measured_at": (base_time + timedelta(seconds=seconds)).isoformat(),
                },
                headers={"X-Device-Key": device_key},
            )

        baseline = submit(500, 0)
        self.assertEqual(baseline.status_code, 201, baseline.get_json())
        self.assertEqual(baseline.get_json()["created"], [])
        crossing = submit(1200, 1)
        self.assertEqual(crossing.status_code, 201, crossing.get_json())
        self.assertEqual(
            [alert["level"] for alert in crossing.get_json()["created"]], ["high"]
        )
        duplicate_crossing = submit(1300, 2)
        self.assertEqual(duplicate_crossing.status_code, 201)
        self.assertEqual(duplicate_crossing.get_json()["created"], [])

        with self.app.app_context():
            session = get_session()
            stored_readings = list(
                session.scalars(
                    select(Reading)
                    .where(Reading.home_id == home_id)
                    .order_by(Reading.measured_at, Reading.id)
                )
            )
            self.assertEqual(len(stored_readings), 3)
            self.assertEqual(
                [(reading.value, reading.source) for reading in stored_readings],
                [(500, "device"), (1200, "device"), (1300, "device")],
            )
            self.assertTrue(
                all(
                    reading.home_id == home_id
                    and reading.room_id == room_id
                    and reading.sensor_id == sensor_id
                    for reading in stored_readings
                )
            )
            self.assertEqual(
                session.get(Sensor, sensor_id).room_id,
                session.get(Room, room_id).id,
            )
            self.assertEqual(
                session.get(Room, room_id).home_id,
                session.get(Home, home_id).id,
            )

        alert_id = crossing.get_json()["created"][0]["id"]
        acknowledge = self._request(
            "POST", f"/api/alerts/{alert_id}/acknowledge", {}
        )
        self.assertEqual(acknowledge.status_code, 200, acknowledge.get_json())
        self.assertEqual(acknowledge.get_json()["alert"]["status"], "acknowledged")
        duplicate_acknowledge = self._request(
            "POST", f"/api/alerts/{alert_id}/acknowledge", {}
        )
        self.assertEqual(duplicate_acknowledge.status_code, 200)

        first_normal = submit(500, 3)
        self.assertEqual(first_normal.status_code, 201, first_normal.get_json())
        self.assertEqual(first_normal.get_json()["cleared"], [])
        all_clear = submit(500, 5)
        self.assertEqual(all_clear.status_code, 201, all_clear.get_json())
        self.assertEqual(
            [alert["id"] for alert in all_clear.get_json()["cleared"]], [alert_id]
        )

        with self.app.app_context():
            session = get_session()
            alerts = list(
                session.scalars(select(Alert).where(Alert.home_id == home_id))
            )
            self.assertEqual(len(alerts), 1)
            self.assertEqual(alerts[0].status, "all_clear")
            self.assertEqual(alerts[0].acknowledged_by, "Workflow User")

            workflow_user = session.get(User, user_id)
            membership = session.get(HomeMembership, (home_id, user_id))
            self.assertIsNotNone(workflow_user)
            self.assertEqual(membership.role, "owner")

        history = self.client.get(
            f"/api/homes/{home_id}/history?room_id={room_id}&metric=CO2"
        )
        self.assertEqual(history.status_code, 200, history.get_json())
        historical_readings = history.get_json()["readings"]
        self.assertEqual([row["value"] for row in historical_readings], [500, 1200, 1300, 500, 500])
        for row in historical_readings:
            self._assert_utc(row["measured_at"])

        export = self.client.get(
            f"/api/homes/{home_id}/history.csv?room_id={room_id}&metric=CO2"
        )
        self.assertEqual(export.status_code, 200)
        self.assertEqual(export.mimetype, "text/csv")
        csv_rows = list(csv.DictReader(io.StringIO(export.get_data(as_text=True))))
        self.assertEqual(len(csv_rows), 5)
        for row in csv_rows:
            self._assert_utc(row["measured_at"])

        invalid_reading = self.client.post(
            f"/api/sensors/{sensor_id}/readings",
            json={
                "room": "Workflow Room",
                "metric": "CO2",
                "unit": "ppm",
                "value": -1,
                "measured_at": (base_time + timedelta(seconds=6)).isoformat(),
            },
            headers={"X-Device-Key": device_key},
        )
        self.assertEqual(invalid_reading.status_code, 400)

        activity = self.client.get(f"/api/homes/{home_id}/activity")
        self.assertEqual(activity.status_code, 200, activity.get_json())
        events = activity.get_json()["events"]
        event_types = [event["event_type"] for event in events]
        self.assertEqual(event_types.count("alert.created"), 1)
        self.assertEqual(event_types.count("alert.acknowledged"), 1)
        self.assertEqual(event_types.count("alert.all_clear"), 1)
        self.assertEqual(event_types.count("reading.ingested"), 5)
        self.assertEqual(event_types.count("reading.rejected"), 1)
        self.assertEqual(event_types.count("sensor.provisioned"), 1)
        self.assertNotIn(device_key, str(events))
        for event in events:
            self._assert_utc(event["created_at"])

        with self.app.extensions["airsense_engine"].connect() as connection:
            metadata = MetaData()
            metadata.reflect(bind=connection)
            for table in metadata.tables.values():
                for foreign_key in table.foreign_keys:
                    child_column = foreign_key.parent
                    parent_column = foreign_key.column
                    orphan = connection.execute(
                        select(child_column)
                        .select_from(
                            table.outerjoin(
                                parent_column.table,
                                child_column == parent_column,
                            )
                        )
                        .where(
                            child_column.is_not(None),
                            parent_column.is_(None),
                        )
                        .limit(1)
                    ).scalar_one_or_none()
                    self.assertIsNone(
                        orphan,
                        f"orphaned foreign key {table.name}.{child_column.name}",
                    )
            if inspect(connection).dialect.name == "sqlite":
                self.assertEqual(
                    connection.execute(text("PRAGMA integrity_check")).scalar_one(),
                    "ok",
                )
                self.assertEqual(
                    connection.execute(text("PRAGMA foreign_keys")).scalar_one(),
                    1,
                )
