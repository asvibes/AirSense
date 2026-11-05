import json

from helpers import AirSenseTestCase


class JsonObjectRequestValidationTests(AirSenseTestCase):
    def setUp(self):
        super().setUp()
        room = self.create_room("Threshold room")
        self.routes = {
            "create_home": ("/api/homes", "POST"),
            "choose_home": ("/api/active-home", "POST"),
            "invite_member": (
                f"/api/homes/{self.home_id}/invitations",
                "POST",
            ),
            "accept_invitation": ("/api/invitations/accept", "POST"),
            "update_threshold": (
                f"/api/homes/{self.home_id}/thresholds/{room['id']}/CO2",
                "PUT",
            ),
        }

    def _send_raw_json(self, path, method, body, *, client=None, headers=None):
        request_headers = {
            "Content-Type": "application/json",
            "X-CSRF-Token": self.csrf,
        }
        request_headers.update(headers or {})
        return (client or self.client).open(
            path,
            method=method,
            data=body,
            headers=request_headers,
        )

    def test_non_object_and_malformed_json_return_consistent_400(self):
        invalid_json = ("[]", '"text"', "42", "true", "{")
        for route_name, (path, method) in self.routes.items():
            for body in invalid_json:
                with self.subTest(route=route_name, body=body):
                    response = self._send_raw_json(path, method, body)
                    self.assertEqual(response.status_code, 400, response.get_json())
                    self.assertEqual(
                        response.get_json(),
                        {"error": "Request body must be a valid JSON object."},
                    )

    def test_valid_json_objects_continue_to_work_on_all_targeted_routes(self):
        created_home = self.request_json(
            "POST", "/api/homes", {"name": "Second home"}
        )
        self.assertEqual(created_home.status_code, 201, created_home.get_json())

        chosen = self.request_json(
            "POST",
            "/api/active-home",
            {"home_id": self.home_id},
        )
        self.assertEqual(chosen.status_code, 200, chosen.get_json())

        invited = self.request_json(
            "POST",
            f"/api/homes/{self.home_id}/invitations",
            {"email": "valid-payload@example.test"},
        )
        self.assertEqual(invited.status_code, 201, invited.get_json())

        invitee, _, invitee_csrf = self.register_client(
            "valid-payload@example.test", "Valid Payload Invitee"
        )
        accepted = invitee.post(
            "/api/invitations/accept",
            json={"token": invited.get_json()["invitation"]["token"]},
            headers={"X-CSRF-Token": invitee_csrf},
        )
        self.assertEqual(accepted.status_code, 200, accepted.get_json())

        room_id = self.routes["update_threshold"][0].split("/")[-2]
        updated = self.request_json(
            "PUT",
            f"/api/homes/{self.home_id}/thresholds/{room_id}/CO2",
            {
                "high_threshold": 1600,
                "elevated_threshold": 1000,
                "elevated_duration_seconds": 300,
                "rapid_rise_per_minute": 200,
                "all_clear_duration_seconds": 300,
                "max_reading_gap_seconds": 120,
            },
        )
        self.assertEqual(updated.status_code, 200, updated.get_json())

    def test_unauthenticated_requests_still_fail_before_payload_validation(self):
        anonymous = self.app.test_client()
        for route_name, (path, method) in self.routes.items():
            with self.subTest(route=route_name):
                response = self._send_raw_json(
                    path, method, json.dumps(["not", "an", "object"]), client=anonymous
                )
                self.assertEqual(response.status_code, 401, response.get_json())
                self.assertEqual(
                    response.get_json(), {"error": "Authentication is required."}
                )
