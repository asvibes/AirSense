import json
import tempfile
import unittest
from pathlib import Path

from app.main import create_app


class AlertLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        database = Path(self.temp_dir.name) / "airsense-test.sqlite3"
        self.app = create_app({"TESTING": True, "DATABASE": str(database)})
        self.client = self.app.test_client()

    def record(self, room="Bedroom", co2=1300, threshold=1000):
        return self.client.post(
            "/api/readings",
            data=json.dumps(
                {"room": room, "co2_ppm": co2, "threshold_ppm": threshold}
            ),
            content_type="application/json",
        )

    def test_high_reading_opens_alert_and_normal_reading_does_not(self):
        response = self.record(co2=1000)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["action"], "none")
        self.assertIsNone(response.json["alert"])

        response = self.record(co2=1300)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json["action"], "open")
        self.assertEqual(response.json["alert"]["status"], "active")
        self.assertEqual(response.json["alert"]["trigger_co2_ppm"], 1300)

    def test_acknowledgement_is_idempotent_and_preserves_original_member(self):
        alert_id = self.record().json["alert"]["id"]

        first = self.client.post(
            f"/api/alerts/{alert_id}/acknowledge",
            json={"acknowledged_by": "Ari"},
        )
        second = self.client.post(
            f"/api/alerts/{alert_id}/acknowledge",
            json={"acknowledged_by": "Sam"},
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json["alert"]["status"], "acknowledged")
        self.assertIsNotNone(first.json["alert"]["acknowledged_at"])
        self.assertEqual(second.json["alert"]["acknowledged_by"], "Ari")

    def test_high_readings_update_one_alert_without_resetting_acknowledgement(self):
        alert_id = self.record().json["alert"]["id"]
        self.client.post(
            f"/api/alerts/{alert_id}/acknowledge",
            json={"acknowledged_by": "Ari"},
        )

        response = self.record(co2=1500)
        alerts = self.client.get("/api/alerts").json["alerts"]

        self.assertEqual(response.json["action"], "update")
        self.assertEqual(response.json["alert"]["id"], alert_id)
        self.assertEqual(response.json["alert"]["status"], "acknowledged")
        self.assertEqual(response.json["alert"]["latest_co2_ppm"], 1500)
        self.assertEqual(len(alerts), 1)

    def test_open_alert_uses_its_original_threshold(self):
        self.record(co2=1300, threshold=1000)

        response = self.record(co2=1050, threshold=2000)

        self.assertEqual(response.json["action"], "update")
        self.assertEqual(response.json["alert"]["threshold_ppm"], 1000)
        self.assertEqual(response.json["alert"]["status"], "active")

    def test_reading_at_threshold_clears_acknowledged_alert(self):
        alert_id = self.record().json["alert"]["id"]
        self.client.post(
            f"/api/alerts/{alert_id}/acknowledge",
            json={"acknowledged_by": "Ari"},
        )

        response = self.record(co2=1000)

        self.assertEqual(response.json["action"], "clear")
        self.assertEqual(response.json["alert"]["status"], "cleared")
        self.assertEqual(response.json["alert"]["latest_co2_ppm"], 1000)
        self.assertIsNotNone(response.json["alert"]["cleared_at"])

    def test_new_breach_after_all_clear_starts_a_new_alert(self):
        first_id = self.record().json["alert"]["id"]
        self.record(co2=800)

        response = self.record(co2=1400)
        alerts = self.client.get("/api/alerts").json["alerts"]

        self.assertEqual(response.json["action"], "open")
        self.assertNotEqual(response.json["alert"]["id"], first_id)
        self.assertEqual(response.json["alert"]["status"], "active")
        self.assertEqual(len(alerts), 2)

    def test_cleared_alert_cannot_be_acknowledged(self):
        alert_id = self.record().json["alert"]["id"]
        self.record(co2=800)

        response = self.client.post(
            f"/api/alerts/{alert_id}/acknowledge",
            json={"acknowledged_by": "Ari"},
        )

        self.assertEqual(response.status_code, 409)
        self.assertIn("cannot be acknowledged", response.json["error"])

    def test_missing_alert_returns_not_found(self):
        response = self.client.post(
            "/api/alerts/999/acknowledge",
            json={"acknowledged_by": "Ari"},
        )
        self.assertEqual(response.status_code, 404)

    def test_invalid_readings_are_rejected(self):
        for values in (
            {"room": "", "co2_ppm": 1500, "threshold_ppm": 1000},
            {"room": "Bedroom", "co2_ppm": -1, "threshold_ppm": 1000},
            {"room": "Bedroom", "co2_ppm": 1500, "threshold_ppm": 0},
            {"room": "Bedroom", "co2_ppm": "NaN", "threshold_ppm": 1000},
        ):
            with self.subTest(values=values):
                response = self.client.post("/api/readings", json=values)
                self.assertEqual(response.status_code, 400)

        self.assertEqual(self.client.get("/api/alerts").json["alerts"], [])

    def test_alert_page_exposes_all_clear_state(self):
        self.record()
        self.record(co2=800)

        response = self.client.get("/alerts")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"All clear", response.data)
        self.assertIn(b"Returned below threshold", response.data)

    def test_html_forms_use_browser_routes_and_redirect(self):
        response = self.client.post(
            "/readings",
            data={"room": "Kitchen", "co2_ppm": "1200", "threshold_ppm": "1000"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.startswith("/alerts?notice="))

        page = self.client.get("/alerts")
        self.assertIn(b'action="/alerts/1/acknowledge"', page.data)
        response = self.client.post(
            "/alerts/1/acknowledge", data={"acknowledged_by": "Ari"}
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.startswith("/alerts?notice="))


if __name__ == "__main__":
    unittest.main()