from datetime import datetime, timedelta, timezone

from app.db import get_session
from app.models.metric import Metric
from app.models.reading import Reading
from app.models.sensor import Sensor
from helpers import AirSenseTestCase


class HistoryPageTests(AirSenseTestCase):
    def setUp(self):
        super().setUp()
        self.room = self.create_room("Study")
        sensor_response = self.request_json(
            "POST",
            f"/api/homes/{self.home_id}/sensors",
            {"name": "Study monitor", "room_id": self.room["id"]},
        )
        self.assertEqual(sensor_response.status_code, 201, sensor_response.get_json())
        self.sensor_id = sensor_response.get_json()["sensor"]["id"]
        self.measured_at = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(hours=2)
        with self.app.app_context():
            db = get_session()
            db.add_all(
                [
                    Metric(code="PM2.5", name="Fine particulate matter", unit="µg/m³"),
                    Metric(code="VOC", name="Volatile organic compounds", unit="ppb"),
                ]
            )
            db.flush()
            for index, (metric, value) in enumerate(
                (("CO2", 610), ("CO2", 720), ("PM2.5", 8.5), ("VOC", 110))
            ):
                db.add(
                    Reading(
                        home_id=self.home_id,
                        room_id=self.room["id"],
                        sensor_id=self.sensor_id,
                        metric_code=metric,
                        value=value,
                        source="device",
                        measured_at=self.measured_at + timedelta(minutes=index * 5),
                    )
                )
            db.commit()

    def test_history_page_requires_login_and_renders_filters(self):
        response = self.client.get(f"/history?home_id={self.home_id}")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"STORED SENSOR DATA", response.data)
        self.assertIn(b'id="household"', response.data)
        self.assertIn(b'id="sensor"', response.data)
        self.assertIn(b"id=\"export-pdf\"", response.data)
        self.assertIn(b"/static/js/history.js", response.data)

        anonymous = self.app.test_client().get("/history")
        self.assertEqual(anonymous.status_code, 302)
        self.assertIn("/login", anonymous.location)

    def test_insights_pages_render_with_shared_navigation(self):
        analytics = self.client.get(f"/analytics?home_id={self.home_id}")
        self.assertEqual(analytics.status_code, 200)
        self.assertIn(b"Historical trends", analytics.data)
        self.assertIn(b'id="aggregation"', analytics.data)
        self.assertIn(b"Analytics</span>", analytics.data)
        predictions = self.client.get(f"/predictions?home_id={self.home_id}")
        self.assertEqual(predictions.status_code, 200)
        self.assertIn(b"Coming Soon", predictions.data)
        self.assertIn(b"Predictions</span>", predictions.data)
        self.assertEqual(self.app.test_client().get("/predictions").status_code, 302)
        paths = [rule.rule for rule in self.app.url_map.iter_rules()]
        for path in ("/", "/history", "/analytics", "/predictions"):
            self.assertEqual(paths.count(path), 1, f"Expected one route for {path}")
        dashboard = self.client.get(f"/alerts?home_id={self.home_id}&view=sensors")
        self.assertIn(b'"initialView": "sensors"', dashboard.data)

    def test_predictions_api_does_not_create_forecasts_without_saved_model(self):
        from unittest.mock import patch

        with patch("app.routers.history.load_saved_models", return_value=[]):
            listing = self.client.get(f"/api/homes/{self.home_id}/predictions")
            self.assertEqual(listing.status_code, 200)
            self.assertEqual(listing.get_json()["models"], [])
            result = self.client.get(
                f"/api/homes/{self.home_id}/predictions?metric=CO2"
            )
        self.assertEqual(result.status_code, 200)
        self.assertFalse(result.get_json()["available"])
        self.assertEqual(result.get_json()["forecast"], [])
        self.assertIn("No trained", result.get_json()["reason"])
        self.assertTrue(result.get_json()["actual"])
        self.assertTrue(all(item["source"] == "device" for item in result.get_json()["actual"]))

    def test_predictions_api_returns_only_model_estimates_for_validated_series(self):
        from unittest.mock import patch

        model = {
            "home_id": self.home_id,
            "room_id": self.room["id"],
            "sensor_id": self.sensor_id,
            "metric": "CO2",
            "available": True,
            "sample_count": 40,
            "tested_horizon_seconds": 3600,
            "metrics": {
                "trend": {"mae": 2.0, "rmse": 2.5, "r2": 0.9},
                "persistence": {"mae": 8.0, "rmse": 9.0, "r2": 0.1},
            },
            "model": {
                "kind": "linear_time_trend",
                "anchor": self.measured_at.isoformat(),
                "slope_per_second": 0.01,
                "intercept": 600,
                "residual_p90": 3,
            },
        }
        with patch("app.routers.history.load_saved_models", return_value=[model]):
            response = self.client.get(
                f"/api/homes/{self.home_id}/predictions",
                query_string={
                    "room_id": self.room["id"],
                    "sensor_id": self.sensor_id,
                    "metric": "CO2",
                    "horizon_minutes": 1,
                },
            )
        self.assertEqual(response.status_code, 200, response.get_json())
        payload = response.get_json()
        self.assertTrue(payload["available"])
        self.assertEqual(len(payload["forecast"]), 12)
        self.assertTrue(all(item["source"] == "device" for item in payload["actual"]))
        self.assertTrue(all("lower" in item and "upper" in item for item in payload["forecast"]))
        with patch("app.routers.history.load_saved_models", return_value=[model]):
            too_far = self.client.get(
                f"/api/homes/{self.home_id}/predictions",
                query_string={
                    "room_id": self.room["id"],
                    "sensor_id": self.sensor_id,
                    "metric": "CO2",
                    "horizon_minutes": 61,
                },
            )
        self.assertFalse(too_far.get_json()["available"])
        self.assertIn("exceeds", too_far.get_json()["reason"])
        self.assertTrue(too_far.get_json()["actual"])

    def test_household_filter_contains_only_the_signed_in_users_homes(self):
        created = self.request_json(
            "POST", "/api/homes", {"name": "Cabin"}
        )
        self.assertEqual(created.status_code, 201)
        page = self.client.get("/history")
        self.assertIn(b"Cabin", page.data)
        self.assertIn(b"Study monitor", self.client.get(
            f"/api/homes/{self.home_id}/sensors"
        ).data)

    def test_options_and_history_filter_by_sensor_and_multiple_stored_metrics(self):
        options = self.client.get(
            f"/api/homes/{self.home_id}/history/options?sensor_id={self.sensor_id}"
        )
        self.assertEqual(options.status_code, 200)
        self.assertEqual(
            {metric["code"] for metric in options.get_json()["metrics"]},
            {"CO2", "PM2.5", "VOC"},
        )

        start = (self.measured_at - timedelta(minutes=1)).isoformat()
        end = (self.measured_at + timedelta(minutes=20)).isoformat()
        response = self.client.get(
            f"/api/homes/{self.home_id}/history",
            query_string=[
                ("sensor_id", self.sensor_id),
                ("metric", "CO2"),
                ("metric", "PM2.5"),
                ("from", start),
                ("to", end),
            ],
        )
        self.assertEqual(response.status_code, 200, response.get_json())
        readings = response.get_json()["readings"]
        self.assertEqual([reading["metric"] for reading in readings], ["CO2", "CO2", "PM2.5"])
        self.assertTrue(all(reading["sensor_id"] == self.sensor_id for reading in readings))
        self.assertEqual(readings[0]["measured_at"], self.measured_at.isoformat().replace("+00:00", "Z"))

    def test_history_rejects_sensor_from_another_household_or_room(self):
        other_client, other_user, _ = self.register_client(
            "second-owner@example.test", "Second owner"
        )
        other_home = other_user["home"]["id"]
        response = self.client.get(
            f"/api/homes/{self.home_id}/history/options?sensor_id=missing-sensor"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("sensor_id", response.get_json()["error"])
        other_home_response = self.client.get(
            f"/api/homes/{other_home}/history?sensor_id={self.sensor_id}"
        )
        self.assertEqual(other_home_response.status_code, 404)
        self.assertEqual(other_client.get("/history").status_code, 200)

    def test_pdf_export_is_a_multipage_report_of_stored_readings(self):
        start = (self.measured_at - timedelta(minutes=1)).isoformat()
        end = (self.measured_at + timedelta(minutes=20)).isoformat()
        response = self.client.get(
            f"/api/homes/{self.home_id}/history.pdf",
            query_string=[
                ("sensor_id", self.sensor_id),
                ("metric", "CO2"),
                ("metric", "PM2.5"),
                ("from", start),
                ("to", end),
            ],
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "application/pdf")
        self.assertTrue(response.data.startswith(b"%PDF-1.4"))
        self.assertIn(b"/Count 4", response.data)
        self.assertIn(b"610", response.data)
        self.assertIn(b"PM2.5", response.data)
