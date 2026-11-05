from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.db import get_session
from app.models.audit import AuditLog
from app.models.reading import Reading
from app.timestamps import normalize_utc
from helpers import AirSenseTestCase


class IngestionTests(AirSenseTestCase):
    def test_room_accepts_multiple_ventilation_sources(self):
        room = self.create_room(
            "Sunroom", ["Window", "Air conditioner", "Exhaust fan"]
        )
        self.assertEqual(
            room["ventilation_sources"],
            ["Window", "Air conditioner", "Exhaust fan"],
        )
        listed = self.client.get(f"/api/homes/{self.home_id}/rooms").get_json()
        self.assertEqual(
            listed["rooms"][0]["ventilation_sources"],
            ["Window", "Air conditioner", "Exhaust fan"],
        )

    def test_not_specified_cannot_be_combined_with_other_sources(self):
        response = self.request_json(
            "POST",
            f"/api/homes/{self.home_id}/rooms",
            {
                "name": "Unspecified room",
                "ventilation_sources": ["Not specified", "Window"],
            },
        )
        self.assertEqual(response.status_code, 400)

    def test_room_accepts_a_trimmed_custom_ventilation_source(self):
        response = self.request_json(
            "POST",
            f"/api/homes/{self.home_id}/rooms",
            {
                "name": "Garden room",
                "ventilation_sources": ["Window", "Other:  Balcony door  "],
            },
        )
        self.assertEqual(response.status_code, 201, response.get_json())
        self.assertEqual(
            response.get_json()["room"]["ventilation_sources"],
            ["Window", "Other: Balcony door"],
        )

    def test_custom_ventilation_source_must_be_described_and_bounded(self):
        for index, source in enumerate(["Other:   ", f"Other: {'x' * 61}"]):
            with self.subTest(source=source):
                response = self.request_json(
                    "POST",
                    f"/api/homes/{self.home_id}/rooms",
                    {
                        "name": f"Invalid source room {index}",
                        "ventilation_sources": [source],
                    },
                )
                self.assertEqual(response.status_code, 400)

    def test_provisioned_sensor_ingests_and_exposes_history(self):
        room = self.create_room()
        provisioned = self.request_json(
            "POST",
            f"/api/homes/{self.home_id}/sensors",
            {
                "name": "Living room sensor",
                "room_id": room["id"],
                "reporting_interval_seconds": 300,
            },
        )
        self.assertEqual(provisioned.status_code, 201, provisioned.get_json())
        details = provisioned.get_json()
        sensor_id = details["sensor"]["id"]
        key = details["device_key"]
        self.assertTrue(key)

        sensor_list = self.client.get(f"/api/homes/{self.home_id}/sensors").get_json()
        self.assertNotIn("key_hash", sensor_list["sensors"][0])
        self.assertNotIn(key, str(sensor_list))

        reading = self.client.post(
            f"/api/sensors/{sensor_id}/readings",
            json={
                "room": room["name"],
                "metric": "CO2",
                "unit": "ppm",
                "value": 720,
                "measured_at": datetime.now(timezone.utc).isoformat(),
                "received_at": "2000-01-01T00:00:00Z",
            },
            headers={"X-Device-Key": key},
        )
        self.assertEqual(reading.status_code, 201, reading.get_json())
        self.assertIsNotNone(reading.get_json()["received_at"])
        self.assertNotEqual(
            reading.get_json()["received_at"], "2000-01-01T00:00:00Z"
        )

        history = self.client.get(
            f"/api/homes/{self.home_id}/history?room_id={room['id']}&metric=CO2"
        )
        self.assertEqual(history.status_code, 200, history.get_json())
        self.assertEqual(len(history.get_json()["readings"]), 1)
        self.assertEqual(history.get_json()["readings"][0]["value"], 720)
        self.assertEqual(
            history.get_json()["readings"][0]["received_at"],
            reading.get_json()["received_at"],
        )

        invalid_key = self.client.post(
            f"/api/sensors/{sensor_id}/readings",
            json={"room": room["name"], "value": 700},
            headers={"X-Device-Key": "not-the-device-key"},
        )
        self.assertEqual(invalid_key.status_code, 401)

        unknown_sensor = self.client.post(
            "/api/sensors/missing-sensor/readings",
            json={"room": room["name"], "value": 700},
            headers={"X-Device-Key": key},
        )
        self.assertEqual(unknown_sensor.status_code, 401)

        with self.app.app_context():
            events = list(
                get_session().scalars(
                    select(AuditLog).where(
                        AuditLog.event_type == "sensor.authentication_failed"
                    )
                )
            )
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].home_id, self.home_id)
        self.assertEqual(events[0].entity_id, sensor_id)
        self.assertEqual(
            events[0].details_json,
            '{"reason":"invalid_or_inactive_credentials"}',
        )
        self.assertNotIn(key, str(events))
        self.assertNotIn("not-the-device-key", str(events))

    def test_client_cannot_spoof_received_at_and_measured_at_remains_independent(self):
        room = self.create_room()
        measured_at = datetime.now(timezone.utc) - timedelta(minutes=5)
        request_started_at = datetime.now(timezone.utc)
        response = self.request_json(
            "POST",
            f"/api/homes/{self.home_id}/demo/readings",
            {
                "room_id": room["id"],
                "value": 700,
                "measured_at": measured_at.isoformat(),
                "received_at": "2000-01-01T00:00:00Z",
            },
        )
        request_finished_at = datetime.now(timezone.utc)

        self.assertEqual(response.status_code, 201, response.get_json())
        result = response.get_json()
        received_at = datetime.fromisoformat(
            result["received_at"].replace("Z", "+00:00")
        )
        self.assertGreaterEqual(received_at, request_started_at)
        self.assertLessEqual(received_at, request_finished_at)
        self.assertNotEqual(result["received_at"], "2000-01-01T00:00:00Z")
        self.assertEqual(
            datetime.fromisoformat(result["measured_at"].replace("Z", "+00:00")),
            measured_at,
        )

        with self.app.app_context():
            stored = get_session().get(Reading, result["reading_id"])
            self.assertIsNotNone(stored)
            self.assertEqual(normalize_utc(stored.received_at), received_at)
            self.assertEqual(normalize_utc(stored.measured_at), measured_at)
