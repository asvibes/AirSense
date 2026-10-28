from helpers import AirSenseTestCase


class AuditTests(AirSenseTestCase):
    def test_owner_can_view_persisted_room_and_invitation_events(self):
        self.create_room("Study", "Window")
        invited = self.request_json(
            "POST",
            f"/api/homes/{self.home_id}/invitations",
            {"email": "invitee@example.test"},
        )
        self.assertEqual(invited.status_code, 201, invited.get_json())

        response = self.client.get(f"/api/homes/{self.home_id}/activity")
        self.assertEqual(response.status_code, 200, response.get_json())
        event_types = [event["event_type"] for event in response.get_json()["events"]]
        self.assertIn("room.created", event_types)
        self.assertIn("member.invited", event_types)