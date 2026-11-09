from helpers import AirSenseTestCase
from io import BytesIO
from pathlib import Path
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.db import get_session
from app.models.user import HomeInvitation
from app.models.user import User
from app.models.alert import Alert
from app.models.reading import Reading


class AccessControlTests(AirSenseTestCase):
    def test_owner_invitation_request_uses_rendered_home_and_csrf_session(self):
        page = self.client.get(f"/alerts?home_id={self.home_id}")
        self.assertEqual(page.status_code, 200)
        self.assertIn(b'"homeId": "' + self.home_id.encode() + b'"', page.data)
        self.assertIn(b'"role": "owner"', page.data)
        self.assertIn(b'id="inviteBtn" type="button"', page.data)
        self.assertNotIn(b'id="inviteBtn" type="button" hidden', page.data)

        response = self.client.post(
            f"/api/homes/{self.home_id}/invitations",
            json={"email": "authorized-invite@example.test"},
            headers={"X-CSRF-Token": self.csrf},
        )
        self.assertEqual(response.status_code, 201, response.get_data(as_text=True))
        self.assertEqual(
            response.get_json()["invitation"]["email"],
            "authorized-invite@example.test",
        )

    def test_non_owner_invite_control_is_hidden_and_invitation_is_forbidden(self):
        invitation = self.request_json(
            "POST",
            f"/api/homes/{self.home_id}/invitations",
            {"email": "member-invite-test@example.test"},
        ).get_json()["invitation"]
        member_client, _, member_csrf = self.register_client(
            "member-invite-test@example.test", "Invitation Test Member"
        )
        accepted = member_client.post(
            "/api/invitations/accept",
            json={"token": invitation["token"]},
            headers={"X-CSRF-Token": member_csrf},
        )
        self.assertEqual(accepted.status_code, 200, accepted.get_json())

        page = member_client.get(f"/alerts?home_id={self.home_id}")
        self.assertEqual(page.status_code, 200)
        self.assertIn(b'id="inviteBtn" type="button" hidden', page.data)
        denied = member_client.post(
            f"/api/homes/{self.home_id}/invitations",
            json={"email": "unauthorized-invite@example.test"},
            headers={"X-CSRF-Token": member_csrf},
        )
        self.assertEqual(denied.status_code, 403, denied.get_data(as_text=True))
        self.assertEqual(
            denied.get_json(),
            {
                "error": (
                    "You don't have the permission to access the requested resource. "
                    "It is either read-protected or not readable by the server."
                )
            },
        )

    def test_invitation_rejects_wrong_household_stale_session_and_bad_csrf(self):
        other_client, _, other_csrf = self.register_client(
            "another-owner@example.test", "Another Owner"
        )
        wrong_home = other_client.post(
            f"/api/homes/{self.home_id}/invitations",
            json={"email": "wrong-home@example.test"},
            headers={"X-CSRF-Token": other_csrf},
        )
        self.assertEqual(wrong_home.status_code, 404, wrong_home.get_data(as_text=True))

        bad_csrf = self.client.post(
            f"/api/homes/{self.home_id}/invitations",
            json={"email": "bad-csrf@example.test"},
            headers={"X-CSRF-Token": "invalid-token"},
        )
        self.assertEqual(bad_csrf.status_code, 400, bad_csrf.get_data(as_text=True))

        with self.client.session_transaction() as browser_session:
            owner_id = browser_session["user_id"]
        with self.app.app_context():
            user = get_session().get(User, owner_id)
            user.session_version += 1
            get_session().commit()
        expired = self.client.post(
            f"/api/homes/{self.home_id}/invitations",
            json={"email": "stale-session@example.test"},
            headers={"X-CSRF-Token": self.csrf},
        )
        self.assertEqual(expired.status_code, 401, expired.get_data(as_text=True))

    def test_owner_can_use_both_legacy_reading_routes(self):
        self.create_room("Bedroom")
        payload = {
            "home_id": self.home_id,
            "room": "Bedroom",
            "metric": "CO2",
            "unit": "ppm",
            "value": 700,
        }
        api_response = self.client.post(
            "/api/readings",
            json=payload,
            headers={"X-CSRF-Token": self.csrf},
        )
        self.assertEqual(api_response.status_code, 201, api_response.get_json())

        html_response = self.client.post(
            "/readings",
            data={**payload, "csrf_token": self.csrf},
        )
        self.assertEqual(html_response.status_code, 302)

    def test_unauthenticated_legacy_reading_routes_are_rejected(self):
        anonymous = self.app.test_client()
        for endpoint in ("/api/readings", "/readings"):
            response = anonymous.post(
                endpoint,
                json={
                    "home_id": self.home_id,
                    "room": "Bedroom",
                    "value": 700,
                },
            )
            self.assertEqual(response.status_code, 401)

    def test_room_photo_requires_membership_and_supports_authorized_upload(self):
        self.app.config["PRIVATE_UPLOAD_FOLDER"] = str(
            Path(self.temp_dir.name) / "private_uploads"
        )
        room = self.create_room("Photo room")
        image = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
        response = self.client.post(
            f"/api/homes/{self.home_id}/rooms/{room['id']}/photos",
            data={"photo": (BytesIO(image), "room.png")},
            headers={"X-CSRF-Token": self.csrf},
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 201, response.get_json())
        filename = response.get_json()["photo"]["filename"]
        fetched = self.client.get(
            f"/api/homes/{self.home_id}/rooms/{room['id']}/photos/{filename}"
        )
        self.assertEqual(fetched.status_code, 200)
        self.assertEqual(fetched.mimetype, "image/png")

        other_client, _, _ = self.register_client("photo-other@example.test", "Other")
        denied = other_client.get(
            f"/api/homes/{self.home_id}/rooms/{room['id']}/photos/{filename}"
        )
        self.assertEqual(denied.status_code, 404)
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
            f"/api/homes/{self.home_id}/demo/readings",
            json={"room_id": self.create_room("Owner-only room")["id"], "value": 500},
            headers={"X-CSRF-Token": member_csrf},
        )
        self.assertEqual(response.status_code, 403)
        for endpoint in ("/api/readings", "/readings"):
            response = member_client.post(
                endpoint,
                json={
                    "home_id": self.home_id,
                    "room": "Bedroom",
                    "metric": "CO2",
                    "unit": "ppm",
                    "value": 1800,
                },
                headers={"X-CSRF-Token": member_csrf},
            )
            self.assertEqual(response.status_code, 403)

        with self.app.app_context():
            db = get_session()
            self.assertEqual(
                db.scalar(
                    select(Reading.id).where(
                        Reading.home_id == self.home_id,
                        Reading.value == 1800,
                    )
                ),
                None,
            )
            self.assertEqual(
                db.scalar(
                    select(Alert.id).where(
                        Alert.home_id == self.home_id,
                        Alert.level == "high",
                    )
                ),
                None,
            )
        response = member_client.post(
            f"/api/homes/{self.home_id}/rooms",
            json={"name": "Unauthorized room"},
            headers={"X-CSRF-Token": member_csrf},
        )
        self.assertEqual(response.status_code, 403)

    def test_invitation_expiry_and_single_use_are_enforced(self):
        invitation = self.request_json(
            "POST",
            f"/api/homes/{self.home_id}/invitations",
            {"email": "expiry-member@example.test"},
        ).get_json()["invitation"]
        member_client, _, member_csrf = self.register_client(
            "expiry-member@example.test", "Expiry Member"
        )
        with self.app.app_context():
            row = get_session().get(HomeInvitation, invitation["id"])
            row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
            get_session().commit()
        expired = member_client.post(
            "/api/invitations/accept",
            json={"token": invitation["token"]},
            headers={"X-CSRF-Token": member_csrf},
        )
        self.assertEqual(expired.status_code, 410)

        with self.app.app_context():
            row = get_session().get(HomeInvitation, invitation["id"])
            row.expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
            get_session().commit()
        accepted = member_client.post(
            "/api/invitations/accept",
            json={"token": invitation["token"]},
            headers={"X-CSRF-Token": member_csrf},
        )
        self.assertEqual(accepted.status_code, 200)
        reused = member_client.post(
            "/api/invitations/accept",
            json={"token": invitation["token"]},
            headers={"X-CSRF-Token": member_csrf},
        )
        self.assertEqual(reused.status_code, 404)
