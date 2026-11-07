from helpers import AirSenseTestCase


class AccessControlTests(AirSenseTestCase):
    def test_api_requires_authentication_and_isolates_homes(self):
        anonymous = self.app.test_client()
        response = anonymous.get(f"/api/homes/{self.home_id}/rooms")
        self.assertEqual(response.status_code, 401)

        other_client, _, _ = self.register_client("other@example.test", "Other User")
        response = other_client.get(f"/api/homes/{self.home_id}/rooms")
        self.assertEqual(response.status_code, 404)

        response = self.client.get(f"/api/homes/{self.home_id}/rooms")
        self.assertEqual(response.status_code, 200)

    def test_member_cannot_mutate_owner_only_resources(self):
        invitation = self.request_json(
            "POST",
            f"/api/homes/{self.home_id}/invitations",
            {"email": "member@example.test"},
        )
        self.assertEqual(invitation.status_code, 201, invitation.get_json())
        member_client, _, member_csrf = self.register_client(
            "member@example.test", "Home Member"
        )
        response = member_client.post(
            "/api/invitations/accept",
            json={"token": invitation.get_json()["invitation"]["token"]},
            headers={"X-CSRF-Token": member_csrf},
        )
        self.assertEqual(response.status_code, 200, response.get_json())

        members = member_client.get(f"/api/homes/{self.home_id}/members")
        self.assertEqual(members.status_code, 200, members.get_json())
        self.assertEqual(len(members.get_json()["members"]), 2)

        response = member_client.get(f"/api/homes/{self.home_id}/activity")
        self.assertEqual(response.status_code, 403)
        response = member_client.post(
            f"/api/homes/{self.home_id}/rooms",
            json={"name": "Unauthorized room"},
            headers={"X-CSRF-Token": member_csrf},
        )
        self.assertEqual(response.status_code, 403)