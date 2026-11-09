from datetime import datetime, timedelta, timezone
from pathlib import Path
import unittest

from app.db import get_session
from app.models.sensor import Sensor
from helpers import AirSenseTestCase


class DashboardLiveUpdateIntegrationTests(AirSenseTestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]
        cls.template = (cls.root / "app" / "templates" / "alerts.html").read_text(
            encoding="utf-8"
        )
        cls.script = (cls.root / "app" / "static" / "js" / "dashboard.js").read_text(
            encoding="utf-8"
        )

    def create_sensor(self, room):
        response = self.request_json(
            "POST",
            f"/api/homes/{self.home_id}/sensors",
            {"name": "Freshness monitor", "room_id": room["id"]},
        )
        self.assertEqual(response.status_code, 201, response.get_json())
        return response.get_json()["sensor"]["id"]

    def set_sensor_last_seen(self, sensor_id, value):
        with self.app.app_context():
            session = get_session()
            sensor = session.get(Sensor, sensor_id)
            sensor.last_seen_at = value
            session.commit()

    def test_room_and_sensor_views_use_the_existing_freshness_state(self):
        room = self.create_room("Freshness room")
        sensor_id = self.create_sensor(room)

        initial = self.client.get(f"/api/homes/{self.home_id}/rooms").get_json()
        self.assertEqual(initial["rooms"][0]["sensors"][0]["state"], "never_seen")

        self.set_sensor_last_seen(sensor_id, datetime.now(timezone.utc))
        fresh = self.client.get(f"/api/homes/{self.home_id}/rooms").get_json()
        self.assertEqual(fresh["rooms"][0]["sensors"][0]["state"], "fresh")

        self.set_sensor_last_seen(
            sensor_id, datetime.now(timezone.utc) - timedelta(seconds=700)
        )
        stale_rooms = self.client.get(f"/api/homes/{self.home_id}/rooms").get_json()
        stale_sensors = self.client.get(f"/api/homes/{self.home_id}/sensors").get_json()
        self.assertEqual(stale_rooms["rooms"][0]["sensors"][0]["state"], "stale")
        self.assertEqual(stale_sensors["sensors"][0]["state"], "stale")

    def test_dashboard_endpoint_reflects_alert_changes_for_live_refresh(self):
        room = self.create_room("Alert room")
        dashboard_url = f"/api/homes/{self.home_id}/dashboard"
        self.assertEqual(self.client.get(dashboard_url).get_json()["alerts"], [])

        reading = self.request_json(
            "POST",
            f"/api/homes/{self.home_id}/demo/readings",
            {"room_id": room["id"], "metric": "CO2", "unit": "ppm", "value": 1800},
        )
        self.assertEqual(reading.status_code, 201, reading.get_json())
        alerts = self.client.get(dashboard_url).get_json()["alerts"]
        self.assertEqual([alert["level"] for alert in alerts], ["high"])

        alert_id = alerts[0]["id"]
        acknowledged = self.request_json(
            "POST", f"/api/alerts/{alert_id}/acknowledge", {}
        )
        self.assertEqual(acknowledged.status_code, 200, acknowledged.get_json())
        updated = self.client.get(dashboard_url).get_json()["alerts"]
        self.assertEqual(updated[0]["status"], "acknowledged")

    def test_dashboard_polling_and_timestamp_wiring_preserve_user_state(self):
        self.assertIn("live-update-scheduler.js", self.template)
        self.assertLess(
            self.template.index("live-update-scheduler.js"),
            self.template.index("js/dashboard.js"),
        )
        self.assertIn('id="liveUpdateTimestamp"', self.template)
        self.assertIn('id="liveUpdateStatus"', self.template)
        self.assertIn("const LIVE_REFRESH_INTERVAL_MS = 20000", self.script)
        self.assertIn("window.createLiveUpdateScheduler({", self.script)
        self.assertIn('document.addEventListener("visibilitychange"', self.script)
        self.assertIn('window.addEventListener("pagehide"', self.script)
        self.assertIn('window.addEventListener("pageshow"', self.script)

        live_refresh = self.script[
            self.script.index("async function fetchLiveDashboard()"):
            self.script.index("async function loadDashboard(", self.script.index("async function fetchLiveDashboard()"))
        ]
        self.assertIn("api(`${homePath}/rooms`)", live_refresh)
        self.assertIn("api(`${homePath}/dashboard`)", live_refresh)
        self.assertIn("renderAlerts();", live_refresh)
        self.assertIn("markDashboardUpdated();", live_refresh)
        self.assertNotIn("api(`${homePath}/thresholds`)", live_refresh)
        self.assertNotIn("api(`${homePath}/members`)", live_refresh)
        self.assertNotIn("go(", live_refresh)
        self.assertIn("renderRooms({ renderThresholdsSection: false });", live_refresh)
        self.assertIn("if (renderThresholdsSection) renderThresholds();", self.script)
        self.assertIn('sensor.state === "fresh"', self.script)
        self.assertIn('sensor.state === "stale"', self.script)
        self.assertIn('status.dataset.state = "error"', self.script)
        self.assertIn("showing last successful data", self.script)
        failure_handler = self.script[
            self.script.index("function markDashboardUpdateFailed()"):
            self.script.index("async function fetchLiveDashboard()")
        ]
        self.assertNotIn("liveUpdateTimestamp", failure_handler)
        self.assertNotIn("lastDashboardUpdate =", failure_handler)
        self.assertIn('focused?.closest("form[data-ack], #room-form")', self.script)
        self.assertIn("#dashboardMetricSelect, #thresholdMetric", self.script)


if __name__ == "__main__":
    unittest.main()
