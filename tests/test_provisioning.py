from helpers import AirSenseTestCase


class ProvisioningTests(AirSenseTestCase):
    def test_provision_key_rotation_and_revocation(self):
        room = self.create_room()
        response = self.request_json(
            "POST",
            f"/api/homes/{self.home_id}/sensors",
            {"name": "Kitchen monitor", "room_id": room["id"]},
        )
        self.assertEqual(response.status_code, 201, response.get_json())
        sensor_id = response.get_json()["sensor"]["id"]
        first_key = response.get_json()["device_key"]

        rotated = self.request_json(
            "POST",
            f"/api/homes/{self.home_id}/sensors/{sensor_id}/rotate-key",
            {},
        )
        self.assertEqual(rotated.status_code, 200, rotated.get_json())
        second_key = rotated.get_json()["device_key"]
        self.assertNotEqual(first_key, second_key)

        revoked = self.request_json(
            "POST",
            f"/api/homes/{self.home_id}/sensors/{sensor_id}/revoke",
            {},
        )
        self.assertEqual(revoked.status_code, 200, revoked.get_json())
        self.assertEqual(revoked.get_json()["sensor"]["status"], "revoked")

        response = self.client.post(
            f"/api/sensors/{sensor_id}/readings",
            json={"room": room["name"], "value": 700},
            headers={"X-Device-Key": second_key},
        )
        self.assertEqual(response.status_code, 401)