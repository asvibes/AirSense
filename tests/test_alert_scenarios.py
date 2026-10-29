import re
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_session
from app.models.alert import Alert
from app.main import create_app
from helpers import AirSenseTestCase


class AlertLifecycleTests(AirSenseTestCase):
    config_overrides = {
        "HIGH_THRESHOLD": 1500,
        "ELEVATED_THRESHOLD": 1000,
        "ELEVATED_DURATION_SECONDS": 120,
        "RAPID_RISE_PER_MINUTE": 500,
        "ALL_CLEAR_DURATION_SECONDS": 120,
        "MAX_READING_GAP_SECONDS": 60,
    }

    def setUp(self):
        super().setUp()
        self.start = datetime.now(timezone.utc) - timedelta(minutes=10)
        self.client.get("/alerts")

    def record(
        self,
        value,
        seconds=0,
        *,
        room="Bedroom",
        home_id=None,
        metric="CO2",
    ):
        home_id = home_id or self.home_id
        existing_rooms = self.client.get(f"/api/homes/{home_id}/rooms").get_json()["rooms"]
        if not any(item["name"] == room for item in existing_rooms):
            created = self.request_json(
                "POST",
                f"/api/homes/{home_id}/rooms",
                {"name": room, "ventilation": "Not specified"},
            )
            if created.status_code != 201:
                self.fail(f"Unable to create test room: {created.get_json()}")
        measured_at = self.start + timedelta(seconds=seconds)
        return self.client.post(
            "/api/readings",
            json={
                "home_id": home_id,
                "room": room,
                "metric": metric,
                "unit": "ppm",
                "value": value,
                "source": "simulated",
                "measured_at": measured_at.isoformat(),
            },
            headers={"X-CSRF-Token": self.csrf},
        )

    def test_high_reading_opens_once_and_duplicate_crossings_are_suppressed(self):
        first = self.record(1600)
        second = self.record(1700, seconds=30)

        self.assertEqual(first.status_code, 201)
        self.assertEqual(
            [alert["level"] for alert in first.json["created"]], ["high"]
        )
        self.assertIn(
            "above the guideline level used by AirSense",
            first.json["created"][0]["detail"],
        )
        self.assertEqual(second.status_code, 201)
        self.assertEqual(second.json["created"], [])
        alerts = self.client.get("/api/alerts").json["alerts"]
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["status"], "active")

    def test_database_index_rejects_duplicate_open_alert(self):
        created = self.record(1600).json["created"][0]

        with self.app.app_context():
            session: Session = get_session()
            duplicate = Alert(
                home_id=created["home_id"],
                room_id=created["room_id"],
                metric_code=created["metric"],
                level=created["level"],
                status="active",
                trigger_value=1600,
                threshold_value=1500,
                latest_value=1600,
                threshold_unit="ppm",
                clear_duration_seconds=120,
                created_at=self.start,
                detail="Duplicate",
            )
            session.add(duplicate)
            with self.assertRaises(IntegrityError):
                session.commit()
            session.rollback()

    def test_elevated_alert_requires_sustained_readings(self):
        first = self.record(1100)
        before_duration = self.record(1200, seconds=60)
        after_duration = self.record(1250, seconds=120)

        self.assertEqual(first.json["created"], [])
        self.assertEqual(before_duration.json["created"], [])
        self.assertEqual(
            [alert["level"] for alert in after_duration.json["created"]],
            ["elevated"],
        )

    def test_elevated_timer_resets_when_reading_gap_exceeds_policy(self):
        self.record(1100)
        after_gap = self.record(1200, seconds=180)

        self.assertEqual(after_gap.json["created"], [])

    def test_rapid_rise_alert_uses_rate_and_deduplicates(self):
        self.record(500)
        first = self.record(800, seconds=30)
        second = self.record(1200, seconds=60)

        self.assertEqual(
            [alert["level"] for alert in first.json["created"]], ["rapid_rise"]
        )
        self.assertEqual(second.json["created"], [])
        self.assertGreaterEqual(first.json["rapid_rise_per_minute"], 500)

    def test_rapid_rise_is_not_inferred_across_a_stale_sample_gap(self):
        self.record(500)
        after_gap = self.record(1400, seconds=180)

        self.assertIsNone(after_gap.json["rapid_rise_per_minute"])
        self.assertNotIn(
            "rapid_rise", [alert["level"] for alert in after_gap.json["created"]]
        )

    def test_acknowledgement_records_member_and_is_idempotent(self):
        alert_id = self.record(1600).json["created"][0]["id"]

        first = self.client.post(
            f"/api/alerts/{alert_id}/acknowledge",
            json={"acknowledged_by": "Ari"},
            headers={"X-CSRF-Token": self.csrf},
        )
        second = self.client.post(
            f"/api/alerts/{alert_id}/acknowledge",
            json={"acknowledged_by": "Sam"},
            headers={"X-CSRF-Token": self.csrf},
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json["alert"]["status"], "acknowledged")
        self.assertEqual(first.json["alert"]["acknowledged_by"], "AirSense Owner")
        self.assertIsNotNone(first.json["alert"]["acknowledged_at"])
        self.assertEqual(second.json["alert"]["acknowledged_by"], "AirSense Owner")

    def test_all_clear_waits_for_configured_below_threshold_duration(self):
        alert_id = self.record(1600).json["created"][0]["id"]
        first_below = self.record(1200, seconds=30)
        second_below = self.record(1200, seconds=90)
        sustained_below = self.record(1200, seconds=150)

        self.assertEqual(first_below.json["cleared"], [])
        self.assertEqual(second_below.json["cleared"], [])
        self.assertEqual(
            [alert["id"] for alert in sustained_below.json["cleared"]],
            [alert_id],
        )
        alert = next(
            item
            for item in self.client.get("/api/alerts").json["alerts"]
            if item["id"] == alert_id
        )
        self.assertEqual(alert["status"], "all_clear")
        self.assertIsNotNone(alert["all_clear_at"])

    def test_all_clear_timer_resets_after_a_gap(self):
        self.record(1600)
        self.record(1200, seconds=30)
        after_gap = self.record(1200, seconds=120)

        self.assertEqual(after_gap.json["cleared"], [])

    def test_new_breach_after_all_clear_opens_a_new_alert(self):
        first_id = self.record(1600).json["created"][0]["id"]
        self.record(1200, seconds=30)
        self.record(1200, seconds=90)
        self.record(1200, seconds=150)

        breach = self.record(1600, seconds=270)

        self.assertEqual(len(breach.json["created"]), 1)
        self.assertNotEqual(breach.json["created"][0]["id"], first_id)
        self.assertEqual(breach.json["created"][0]["status"], "active")

    def test_duplicate_prevention_is_scoped_by_home_room_metric_and_level(self):
        self.record(1600)
        other_home_id = self.request_json(
            "POST", "/api/homes", {"name": "Second home"}
        ).get_json()["home"]["id"]
        other_home = self.record(1600, seconds=30, home_id=other_home_id)
        other_room = self.record(1600, seconds=60, room="Kitchen")
        other_metric = self.record(1600, seconds=90, metric="VOC")

        self.assertEqual(len(other_home.json["created"]), 1)
        self.assertEqual(len(other_room.json["created"]), 1)
        self.assertEqual(len(other_metric.json["created"]), 1)

    def test_all_clear_alert_cannot_be_acknowledged_and_unknown_alert_is_404(self):
        alert_id = self.record(1600).json["created"][0]["id"]
        self.record(1200, seconds=30)
        self.record(1200, seconds=90)
        self.record(1200, seconds=150)
        response = self.client.post(
            f"/api/alerts/{alert_id}/acknowledge",
            json={"acknowledged_by": "Ari"},
            headers={"X-CSRF-Token": self.csrf},
        )
        self.assertEqual(response.status_code, 409)
        missing = self.client.post(
            "/api/alerts/999/acknowledge",
            json={"acknowledged_by": "Ari"},
            headers={"X-CSRF-Token": self.csrf},
        )
        self.assertEqual(missing.status_code, 404)

    def test_invalid_or_out_of_order_readings_are_rejected(self):
        self.assertEqual(self.record(-1).status_code, 400)
        self.assertEqual(self.record(900).status_code, 201)
        duplicate = self.record(950)
        self.assertEqual(duplicate.status_code, 400)

    def test_alert_page_and_health_endpoint(self):
        self.record(1600)
        page = self.client.get("/alerts")

        self.assertEqual(page.status_code, 200)
        self.assertIn(b"High", page.data)
        self.assertNotIn(b"SUBJECT CONSTRAINTS", page.data)
        self.assertIn(b"certified carbon monoxide alarm", page.data)
        self.assertIn(b"DALTON files are not included", page.data)
        self.assertIn(b"dalton-csv-file", page.data)
        self.assertIn(b"demo-room-select", page.data)
        self.assertNotIn(b"DALTON replay is not connected", page.data)
        self.assertIn(b"dashboard.js", page.data)
        script = self.client.get("/static/js/dashboard.js")
        self.assertEqual(script.status_code, 200)
        self.assertIn(b"fetch(", script.data)
        script_text = script.get_data(as_text=True)
        click_listener = re.search(
            r'document\.addEventListener\("click", event => \{\s*'
            r'const target = event\.target\.closest\("([^"]+)"\);',
            script_text,
        )
        self.assertIsNotNone(click_listener)
        selectors = click_listener.group(1).split(", ")
        self.assertIn("#run-dalton-replay", selectors)
        self.assertIn("#run-custom-reading", selectors)
        self.assertIn(
            'if (target.id === "run-dalton-replay") runAction(runDaltonReplay);',
            script_text,
        )
        self.assertIn(
            'if (target.id === "run-custom-reading") runAction(runCustomReading);',
            script_text,
        )
        template = Path(__file__).resolve().parents[1] / "app" / "templates" / "alerts.html"
        self.assertRegex(
            template.read_text(encoding="utf-8"),
            r'id="dalton-csv-file" type="file" accept="[^"]*\.txt',
        )
        script.close()
        self.assertEqual(self.client.get("/api/health").json, {"status": "ok"})

    def test_dashboard_returns_latest_reading_and_trend_per_room_metric(self):
        self.record(900, seconds=0)
        self.record(1100, seconds=30)

        response = self.client.get(f"/api/dashboard?home_id={self.home_id}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json["readings"]), 1)
        reading = response.json["readings"][0]
        self.assertEqual(reading["room"], "Bedroom")
        self.assertEqual(reading["metric"], "CO2")
        self.assertEqual(reading["value"], 1100)
        self.assertEqual(reading["previous_value"], 900)
        self.assertEqual(reading["trend"], "rising")
        self.assertEqual(reading["unit"], "ppm")
        self.assertEqual(reading["source"], "simulated")
        self.assertEqual(
            self.client.get("/api/dashboard?home_id=another-home").status_code, 404
        )

    def test_browser_forms_use_html_routes_and_redirect(self):
        self.create_room("Kitchen")
        response = self.client.post(
            "/readings",
            data={
                "room": "Kitchen",
                "co2_ppm": "1650",
                "csrf_token": self.csrf,
            },
        )
        self.assertEqual(response.status_code, 302)
        page = self.client.get("/alerts")
        self.assertIn(b"Recent alerts", page.data)
        acknowledged = self.client.post(
            f"/alerts/{self.client.get('/api/alerts').json['alerts'][0]['id']}/acknowledge",
            data={"csrf_token": self.csrf, "acknowledged_by": "Ari"},
        )
        self.assertEqual(acknowledged.status_code, 302)

    def test_room_metric_policy_can_be_configured_via_api(self):
        self.create_room("Kitchen")
        response = self.client.post(
            "/api/policies",
            json={
                "room": "Kitchen",
                "metric": "CO2",
                "unit": "ppm",
                "high_threshold": 2000,
                "elevated_threshold": 1200,
                "elevated_duration_seconds": 90,
                "rapid_rise_per_minute": 300,
                "all_clear_duration_seconds": 180,
                "max_reading_gap_seconds": 60,
            },
            headers={"X-CSRF-Token": self.csrf},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json["policy"]["all_clear_duration_seconds"], 180
        )
        self.assertEqual(
            self.record(1900, room="Kitchen").json["created"], []
        )
        breach = self.record(2100, seconds=180, room="Kitchen")
        self.assertEqual(
            [alert["level"] for alert in breach.json["created"]], ["high"]
        )

    def test_production_token_allows_ui_shell_and_restricts_api_routes(self):
        protected = create_app(
            {
                "TESTING": True,
                "DATABASE_URL": f"sqlite:///{(Path(self.temp_dir.name) / 'protected.sqlite3').as_posix()}",
                "AUTO_CREATE_SCHEMA": True,
                "REQUIRE_API_TOKEN": True,
                "API_TOKEN": "a" * 32,
            }
        ).test_client()

        self.assertEqual(protected.get("/api/alerts").status_code, 401)
        page = protected.get("/alerts")
        self.assertEqual(page.status_code, 302)
        self.assertEqual(
            protected.post("/api/readings", json={"room": "Bedroom"}).status_code,
            401,
        )
        accepted = protected.get(
            "/api/alerts", headers={"Authorization": f"Bearer {'a' * 32}"}
        )
        self.assertEqual(accepted.status_code, 401)
        authorized = protected.get(
            "/api/alerts", headers={"Authorization": "a" * 32}
        )
        self.assertEqual(
            authorized.get_json()["error"], "Authentication is required."
        )


if __name__ == "__main__":
    unittest.main()
from helpers import AirSenseTestCase


class AlertScenarioTests(AirSenseTestCase):
    def test_simulator_reading_opens_and_acknowledges_high_alert(self):
        room = self.create_room("Bedroom")
        reading = self.request_json(
            "POST",
            f"/api/homes/{self.home_id}/demo/readings",
            {"room_id": room["id"], "metric": "CO2", "unit": "ppm", "value": 1800},
        )
        self.assertEqual(reading.status_code, 201, reading.get_json())
        dashboard = self.client.get(f"/api/homes/{self.home_id}/dashboard")
        alert = next(
            item for item in dashboard.get_json()["alerts"] if item["status"] == "active"
        )
        self.assertEqual(alert["level"], "high")

        response = self.request_json(
            "POST", f"/api/alerts/{alert['id']}/acknowledge", {}
        )
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(response.get_json()["alert"]["status"], "acknowledged")
