from helpers import AirSenseTestCase
from io import BytesIO
from pathlib import Path
from datetime import datetime, timedelta, timezone

from app.db import get_session
from app.models.user import HomeInvitation


class AccessControlTests(AirSenseTestCase):
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