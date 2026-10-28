import unittest
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.db import get_session
from app.models.audit import AuditLog
from app.models.reading import Reading
from app.services.ingestion.validate import validate_reading
from app.sources.simulator import build_simulated_reading
from helpers import AirSenseTestCase


class SimulatorPayloadTests(unittest.TestCase):
    def test_scenario_payloads_match_ingestion_contract(self):
        measured_at = "2026-10-28T10:00:00+00:00"
        expected_values = {
            "high": 1800,
            "elevated": 1250,
            "rapid": 1600,
            "clear": 600,
        }

        for scenario, expected_value in expected_values.items():
            with self.subTest(scenario=scenario):
                payload = build_simulated_reading(
                    room="Living room",
                    scenario=scenario,
                    measured_at=measured_at,
                )

                self.assertEqual(
                    set(payload), {"room", "metric", "unit", "value", "measured_at"}
                )
                self.assertEqual(payload["value"], expected_value)
                self.assertEqual(payload["measured_at"], measured_at)
                self.assertEqual(validate_reading(payload)["room"], "Living room")

    def test_manual_value_is_supported_for_existing_demo_clients(self):
        payload = build_simulated_reading(
            room="Kitchen",
            value=725,
            metric="CO2",
            unit="ppm",
        )

        self.assertEqual(
            payload,
            {"room": "Kitchen", "metric": "CO2", "unit": "ppm", "value": 725},
        )

    def test_rapid_rise_label_and_invalid_scenarios_are_handled(self):
        self.assertEqual(
            build_simulated_reading(room="Office", scenario="Rapid Rise")["value"],
            1600,
        )
        with self.assertRaisesRegex(ValueError, "scenario must be"):
            build_simulated_reading(room="Office", scenario="unknown")
        with self.assertRaisesRegex(ValueError, "either scenario or value"):
            build_simulated_reading(room="Office", scenario="high", value=1800)


class SimulatorRouteTests(AirSenseTestCase):
    config_overrides = {
        "HIGH_THRESHOLD": 1500,
        "ELEVATED_THRESHOLD": 1000,
        "ELEVATED_DURATION_SECONDS": 120,
        "RAPID_RISE_PER_MINUTE": 500,
        "ALL_CLEAR_DURATION_SECONDS": 120,
        "MAX_READING_GAP_SECONDS": 120,
    }

    def setUp(self):
        super().setUp()
        self.room = self.create_room("Bedroom")
        self.start = datetime.now(timezone.utc) - timedelta(minutes=10)

    def submit(self, *, scenario=None, value=None, seconds=0, room_id=None):
        payload = {
            "room_id": room_id or self.room["id"],
            "measured_at": (self.start + timedelta(seconds=seconds)).isoformat(),
        }
        if scenario is not None:
            payload["scenario"] = scenario
        if value is not None:
            payload["value"] = value
        return self.request_json(
            "POST",
            f"/api/homes/{self.home_id}/demo/readings",
            payload,
        )

    def stored_reading(self, reading_id):
        with self.app.app_context():
            return get_session().scalar(
                select(Reading).where(Reading.id == reading_id)
            )

    def test_high_and_elevated_scenarios_use_simulated_ingestion_once(self):
        high = self.submit(scenario="high")
        self.assertEqual(high.status_code, 201, high.get_json())
        self.assertEqual(high.get_json()["created"][0]["level"], "high")

        high_reading = self.stored_reading(high.get_json()["reading_id"])
        self.assertEqual(high_reading.source, "simulated")
        self.assertIsNone(high_reading.sensor_id)
        self.assertEqual(high_reading.room_id, self.room["id"])

        elevated_first = self.submit(scenario="elevated", seconds=30)
        elevated_second = self.submit(scenario="elevated", seconds=150)
        self.assertEqual(elevated_first.status_code, 201)
        self.assertEqual(elevated_first.get_json()["created"], [])
        self.assertEqual(elevated_second.status_code, 201)
        self.assertIn(
            "elevated",
            [alert["level"] for alert in elevated_second.get_json()["created"]],
        )

        with self.app.app_context():
            events = list(
                get_session().scalars(
                    select(AuditLog).where(
                        AuditLog.entity_id == str(high.get_json()["reading_id"])
                    )
                )
            )
        self.assertEqual([event.event_type for event in events], ["reading.ingested"])

    def test_rapid_rise_scenario_uses_prior_sample_and_has_no_sensor(self):
        baseline = self.submit(value=500)
        rapid = self.submit(scenario="Rapid Rise", seconds=30)

        self.assertEqual(baseline.status_code, 201, baseline.get_json())
        self.assertEqual(rapid.status_code, 201, rapid.get_json())
        self.assertIn(
            "rapid_rise",
            [alert["level"] for alert in rapid.get_json()["created"]],
        )
        reading = self.stored_reading(rapid.get_json()["reading_id"])
        self.assertEqual(reading.source, "simulated")
        self.assertIsNone(reading.sensor_id)

    def test_clear_scenario_advances_alert_clear_duration(self):
        high = self.submit(scenario="high")
        first_clear = self.submit(scenario="clear", seconds=30)
        sustained_clear = self.submit(scenario="clear", seconds=150)

        self.assertEqual(high.status_code, 201, high.get_json())
        self.assertEqual(first_clear.status_code, 201, first_clear.get_json())
        self.assertEqual(first_clear.get_json()["cleared"], [])
        self.assertEqual(sustained_clear.status_code, 201, sustained_clear.get_json())
        self.assertEqual(len(sustained_clear.get_json()["cleared"]), 1)

    def test_unknown_scenario_invalid_value_and_unknown_room_are_rejected(self):
        invalid_scenario = self.submit(scenario="not-a-scenario")
        invalid_value = self.submit(value=True, seconds=30)
        unknown_room = self.submit(
            scenario="high",
            seconds=60,
            room_id="missing-room",
        )

        self.assertEqual(invalid_scenario.status_code, 400)
        self.assertIn("scenario must be", invalid_scenario.get_json()["error"])
        self.assertEqual(invalid_value.status_code, 400)
        self.assertIn("finite non-negative", invalid_value.get_json()["error"])
        self.assertEqual(unknown_room.status_code, 404)

    def test_legacy_manual_reading_payload_remains_supported(self):
        response = self.submit(value=725)

        self.assertEqual(response.status_code, 201, response.get_json())
        reading = self.stored_reading(response.get_json()["reading_id"])
        self.assertEqual(reading.value, 725)
        self.assertEqual(reading.source, "simulated")
        self.assertIsNone(reading.sensor_id)


if __name__ == "__main__":
    unittest.main()
