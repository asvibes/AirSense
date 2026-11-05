import csv
import unittest
from datetime import datetime, timedelta, timezone

from app.db import get_session
from app.models.reading import Reading
from app.timestamps import format_utc
from helpers import AirSenseTestCase


class TimestampFormattingTests(unittest.TestCase):
    def test_format_utc_converts_timezone_aware_datetime(self):
        value = datetime.fromisoformat("2026-11-05T15:40:00+05:30")

        self.assertEqual(format_utc(value), "2026-11-05T10:10:00Z")

    def test_format_utc_treats_naive_datetime_as_utc(self):
        value = datetime(2026, 11, 5, 10, 10)

        self.assertEqual(format_utc(value), "2026-11-05T10:10:00Z")


class ApiTimestampTests(AirSenseTestCase):
    def assert_utc_timestamp(self, value):
        self.assertTrue(value.endswith("Z"), value)
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        self.assertEqual(parsed.utcoffset(), timedelta(0))

    def test_database_backed_api_timestamps_are_explicitly_utc(self):
        room = self.create_room("Timestamp room")
        measured_at = datetime.now(timezone.utc) - timedelta(seconds=10)
        reading = self.request_json(
            "POST",
            f"/api/homes/{self.home_id}/demo/readings",
            {
                "room_id": room["id"],
                "value": 1600,
                "measured_at": measured_at.isoformat(),
            },
        )
        self.assertEqual(reading.status_code, 201, reading.get_json())
        self.assert_utc_timestamp(reading.get_json()["measured_at"])
        self.assert_utc_timestamp(reading.get_json()["received_at"])
        self.assert_utc_timestamp(reading.get_json()["created"][0]["created_at"])

        rooms = self.client.get(f"/api/homes/{self.home_id}/rooms").get_json()
        self.assert_utc_timestamp(rooms["rooms"][0]["readings"][0]["measured_at"])
        self.assert_utc_timestamp(rooms["rooms"][0]["readings"][0]["received_at"])

        history = self.client.get(
            f"/api/homes/{self.home_id}/history?room_id={room['id']}"
        ).get_json()
        self.assert_utc_timestamp(history["readings"][0]["measured_at"])
        self.assert_utc_timestamp(history["readings"][0]["received_at"])
        self.assert_utc_timestamp(history["range"]["from"])
        self.assert_utc_timestamp(history["range"]["to"])

        csv_response = self.client.get(
            f"/api/homes/{self.home_id}/history.csv?room_id={room['id']}"
        )
        self.assertEqual(csv_response.status_code, 200)
        csv_rows = list(csv.DictReader(csv_response.data.decode().splitlines()))
        self.assertIn("received_at", csv_rows[0])
        self.assertEqual(csv_rows[0]["received_at"], reading.get_json()["received_at"])

        members = self.client.get(
            f"/api/homes/{self.home_id}/members"
        ).get_json()
        self.assert_utc_timestamp(members["members"][0]["joined_at"])

        invitation = self.request_json(
            "POST",
            f"/api/homes/{self.home_id}/invitations",
            {"email": "timestamp@example.test"},
        )
        self.assertEqual(invitation.status_code, 201, invitation.get_json())
        self.assert_utc_timestamp(invitation.get_json()["invitation"]["expires_at"])

        events = self.client.get(
            f"/api/homes/{self.home_id}/activity"
        ).get_json()["events"]
        invitation_event = next(
            event for event in events if event["event_type"] == "member.invited"
        )
        self.assert_utc_timestamp(invitation_event["created_at"])
        self.assert_utc_timestamp(invitation_event["details"]["expires_at"])

        dashboard = self.client.get(
            f"/api/dashboard?home_id={self.home_id}"
        ).get_json()
        self.assert_utc_timestamp(dashboard["readings"][0]["measured_at"])
        self.assert_utc_timestamp(dashboard["readings"][0]["received_at"])

        sensor = self.request_json(
            "POST",
            f"/api/homes/{self.home_id}/sensors",
            {"name": "Timestamp sensor", "room_id": room["id"]},
        ).get_json()
        device_reading = self.client.post(
            f"/api/sensors/{sensor['sensor']['id']}/readings",
            json={
                "room": room["name"],
                "metric": "CO2",
                "unit": "ppm",
                "value": 700,
                "measured_at": datetime.now(timezone.utc).isoformat(),
            },
            headers={"X-Device-Key": sensor["device_key"]},
        )
        self.assertEqual(device_reading.status_code, 201, device_reading.get_json())
        self.assert_utc_timestamp(device_reading.get_json()["received_at"])

        sensors = self.client.get(
            f"/api/homes/{self.home_id}/sensors"
        ).get_json()["sensors"]
        self.assert_utc_timestamp(sensors[0]["last_seen_at"])

    def test_legacy_reading_without_received_at_serializes_as_null(self):
        room = self.create_room("Legacy timestamp room")
        measured_at = datetime.now(timezone.utc) - timedelta(seconds=10)
        with self.app.app_context():
            session = get_session()
            reading = Reading(
                home_id=self.home_id,
                room_id=room["id"],
                metric_code="CO2",
                value=650,
                source="simulated",
                measured_at=measured_at,
                received_at=None,
            )
            session.add(reading)
            session.commit()

        rooms = self.client.get(f"/api/homes/{self.home_id}/rooms").get_json()
        self.assertIsNone(rooms["rooms"][0]["readings"][0]["received_at"])

        dashboard = self.client.get(
            f"/api/homes/{self.home_id}/dashboard"
        ).get_json()
        self.assertIsNone(dashboard["readings"][0]["received_at"])

        history_response = self.client.get(
            f"/api/homes/{self.home_id}/history?room_id={room['id']}"
        )
        self.assertIsNone(
            history_response.get_json()["readings"][0]["received_at"]
        )

        csv_response = self.client.get(
            f"/api/homes/{self.home_id}/history.csv?room_id={room['id']}"
        )
        csv_row = next(csv.DictReader(csv_response.data.decode().splitlines()))
        self.assertEqual(csv_row["received_at"], "")
