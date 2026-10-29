from datetime import datetime, timezone

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
            },
            headers={"X-Device-Key": key},
        )
        self.assertEqual(reading.status_code, 201, reading.get_json())

        history = self.client.get(
            f"/api/homes/{self.home_id}/history?room_id={room['id']}&metric=CO2"
        )
        self.assertEqual(history.status_code, 200, history.get_json())
        self.assertEqual(len(history.get_json()["readings"]), 1)
        self.assertEqual(history.get_json()["readings"][0]["value"], 720)

        invalid_key = self.client.post(
            f"/api/sensors/{sensor_id}/readings",
            json={"room": room["name"], "value": 700},
            headers={"X-Device-Key": "not-the-device-key"},
        )
        self.assertEqual(invalid_key.status_code, 401)
