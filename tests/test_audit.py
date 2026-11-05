from datetime import datetime, timedelta, timezone

from app.db import get_session
from app.models.audit import AuditLog
from sqlalchemy import select

from helpers import AirSenseTestCase


class AuditTests(AirSenseTestCase):
    config_overrides = {
        "ALL_CLEAR_DURATION_SECONDS": 60,
        "MAX_READING_GAP_SECONDS": 600,
    }

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

        member_client, member_data, member_csrf = self.register_client(
            "invitee@example.test", "Invited Member"
        )
        accepted = member_client.post(
            "/api/invitations/accept",
            json={"token": invited.get_json()["invitation"]["token"]},
            headers={"X-CSRF-Token": member_csrf},
        )
        self.assertEqual(accepted.status_code, 200, accepted.get_json())
        removed = self.request_json(
            "DELETE",
            f"/api/homes/{self.home_id}/members/{member_data['user']['id']}",
        )
        self.assertEqual(removed.status_code, 200, removed.get_json())

        room = self.create_room("Sensor room")
        provisioned = self.request_json(
            "POST",
            f"/api/homes/{self.home_id}/sensors",
            {"name": "Audit sensor", "room_id": room["id"]},
        )
        self.assertEqual(provisioned.status_code, 201, provisioned.get_json())
        sensor_id = provisioned.get_json()["sensor"]["id"]
        device_key = provisioned.get_json()["device_key"]
        rotated = self.request_json(
            "POST",
            f"/api/homes/{self.home_id}/sensors/{sensor_id}/rotate-key",
            {},
        )
        self.assertEqual(rotated.status_code, 200, rotated.get_json())
        revoked = self.request_json(
            "POST",
            f"/api/homes/{self.home_id}/sensors/{sensor_id}/revoke",
            {},
        )
        self.assertEqual(revoked.status_code, 200, revoked.get_json())

        response = self.client.get(f"/api/homes/{self.home_id}/activity")
        events = response.get_json()["events"]
        event_types = [event["event_type"] for event in events]
        self.assertIn("member.joined", event_types)
        self.assertIn("member.removed", event_types)
        self.assertIn("sensor.provisioned", event_types)
        self.assertIn("sensor.key_rotated", event_types)
        self.assertIn("sensor.revoked", event_types)
        self.assertNotIn(device_key, str(events))
        self.assertNotIn(invited.get_json()["invitation"]["token"], str(events))
        self.assertEqual(
            next(event for event in events if event["event_type"] == "member.joined")[
                "details"
            ],
            {"role": "member"},
        )

    def test_authentication_events_are_audited_without_credentials(self):
        failed = self.request_json(
            "POST",
            "/api/auth/login",
            {"email": "owner@example.test", "password": "wrong-password"},
        )
        self.assertEqual(failed.status_code, 401)
        unknown_account = self.request_json(
            "POST",
            "/api/auth/login",
            {"email": "unknown@example.test", "password": "unknown-password"},
        )
        self.assertEqual(unknown_account.status_code, 401)

        login = self.request_json(
            "POST",
            "/api/auth/login",
            {"email": "owner@example.test", "password": "secure-password-123"},
        )
        self.assertEqual(login.status_code, 200, login.get_json())
        logout = self.request_json(
            "POST",
            "/api/auth/logout",
            {},
            headers={"X-CSRF-Token": self.current_csrf(self.client)},
        )
        self.assertEqual(logout.status_code, 200, logout.get_json())

        with self.app.app_context():
            events = list(
                get_session().scalars(
                    select(AuditLog).where(
                        AuditLog.event_type.in_(
                            (
                                "account.login_failed",
                                "account.login_succeeded",
                                "account.logged_out",
                            )
                        )
                    )
                )
            )
        event_types = [event.event_type for event in events]
        self.assertEqual(event_types.count("account.login_failed"), 1)
        self.assertEqual(event_types.count("account.login_succeeded"), 1)
        self.assertEqual(event_types.count("account.logged_out"), 1)
        failed_event = next(
            event for event in events if event.event_type == "account.login_failed"
        )
        self.assertIsNone(failed_event.actor_user_id)
        self.assertNotIn("wrong-password", str(events))
        self.assertNotIn("unknown@example.test", str(events))
        self.assertNotIn("unknown-password", str(events))
        self.assertNotIn("secure-password-123", str(events))

    def test_alert_lifecycle_events_are_atomic_and_acknowledgement_is_not_duplicated(self):
        clear_room = self.create_room("Clear lifecycle")
        active_room = self.create_room("Acknowledge lifecycle")
        start = datetime.now(timezone.utc) - timedelta(minutes=10)

        def submit(room, value, seconds):
            return self.request_json(
                "POST",
                f"/api/homes/{self.home_id}/demo/readings",
                {
                    "room_id": room["id"],
                    "value": value,
                    "measured_at": (start + timedelta(seconds=seconds)).isoformat(),
                },
            )

        opened_for_clear = submit(clear_room, 1600, 0)
        self.assertEqual(opened_for_clear.status_code, 201, opened_for_clear.get_json())
        self.assertEqual(submit(clear_room, 600, 1).status_code, 201)
        cleared = submit(clear_room, 600, 61)
        self.assertEqual(cleared.status_code, 201, cleared.get_json())
        self.assertEqual(len(cleared.get_json()["cleared"]), 1)

        opened_for_ack = submit(active_room, 1600, 120)
        self.assertEqual(opened_for_ack.status_code, 201, opened_for_ack.get_json())
        alert_id = opened_for_ack.get_json()["created"][0]["id"]
        for _ in range(2):
            acknowledged = self.request_json(
                "POST",
                f"/api/alerts/{alert_id}/acknowledge",
                {},
            )
            self.assertEqual(acknowledged.status_code, 200, acknowledged.get_json())

        events = self.client.get(
            f"/api/homes/{self.home_id}/activity"
        ).get_json()["events"]
        event_types = [event["event_type"] for event in events]
        self.assertEqual(event_types.count("alert.created"), 2)
        self.assertEqual(event_types.count("alert.all_clear"), 1)
        self.assertEqual(event_types.count("alert.acknowledged"), 1)