from helpers import AirSenseTestCase


class ThresholdTests(AirSenseTestCase):
    def test_batch_threshold_update_persists_all_room_settings(self):
        first = self.create_room("Living")
        second = self.create_room("Bedroom")
        settings = [
            {
                "room_id": room["id"],
                "elevated_threshold": elevated,
                "high_threshold": elevated + 500,
                "elevated_duration_seconds": 300,
                "rapid_rise_per_minute": 200,
                "all_clear_duration_seconds": 300,
                "max_reading_gap_seconds": 120,
            }
            for room, elevated in [(first, 900), (second, 1100)]
        ]
        response = self.request_json(
            "PUT",
            f"/api/homes/{self.home_id}/thresholds",
            {"thresholds": settings},
        )
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(len(response.get_json()["thresholds"]), 2)

        response = self.client.get(f"/api/homes/{self.home_id}/thresholds")
        self.assertEqual(response.status_code, 200, response.get_json())
        policies = response.get_json()["thresholds"]
        self.assertEqual(len(policies), 2)
        self.assertEqual(
            {policy["elevated_threshold"] for policy in policies}, {900, 1100}
        )

    def test_invalid_batch_does_not_save_partial_policy(self):
        room = self.create_room("Dining")
        settings = {
            "elevated_threshold": 900,
            "high_threshold": 1500,
            "elevated_duration_seconds": 300,
            "rapid_rise_per_minute": 200,
            "all_clear_duration_seconds": 300,
            "max_reading_gap_seconds": 120,
        }
        response = self.request_json(
            "PUT",
            f"/api/homes/{self.home_id}/thresholds",
            {
                "thresholds": [
                    {"room_id": room["id"], **settings},
                    {"room_id": "not-in-home", **settings},
                ]
            },
        )
        self.assertEqual(response.status_code, 400)
        saved = self.client.get(f"/api/homes/{self.home_id}/thresholds")
        self.assertEqual(saved.get_json()["thresholds"], [])
