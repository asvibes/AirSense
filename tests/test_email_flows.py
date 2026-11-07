from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.db import get_session
from app.models.user import EmailChallenge, HomeInvitation, User
from app.services.email import send_invitation_email, send_otp_email
from helpers import AirSenseTestCase


class EmailFlowTests(AirSenseTestCase):
    def test_email_copy_uses_encoded_signoff_and_dynamic_names(self):
        with patch("app.services.email.send_transactional_email") as send:
            send_otp_email(
                recipient="user@example.test",
                otp="123456",
                purpose="email_verification",
                user_name="New User",
            )
            verification_html = send.call_args.kwargs["html_content"]
            self.assertIn("Hi New User,", verification_html)
            self.assertIn("&#8212; Team AirSense", verification_html)
            self.assertNotIn("â€”", verification_html)

            send_invitation_email(
                recipient="member@example.test",
                invitation_url="https://example.test/join?token=test",
                expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
                owner_name="AirSense Owner",
            )
            invitation_html = send.call_args.kwargs["html_content"]
            self.assertIn("AirSense Owner has invited you", invitation_html)
            self.assertIn("&#8212; Team AirSense", invitation_html)

    def test_registration_creates_hashed_otp_and_requires_verification(self):
        self.app.config["EMAIL_VERIFICATION_REQUIRED"] = True
        csrf = self.current_csrf(self.client)
        with patch("app.routers.auth.send_otp_email") as send:
            response = self.client.post(
                "/api/auth/register",
                json={
                    "email": "new@example.test",
                    "display_name": "New User",
                    "password": "secure-password-123",
                },
                headers={"X-CSRF-Token": csrf},
            )
        self.assertEqual(response.status_code, 202)
        send.assert_called_once()
        self.assertEqual(send.call_args.kwargs["user_name"], "New User")
        with self.app.app_context():
            challenge = get_session().query(EmailChallenge).filter_by(
                email="new@example.test", purpose="email_verification"
            ).one()
            self.assertNotEqual(challenge.otp_hash, send.call_args.kwargs["otp"])

    def test_email_verification_is_single_use_and_attempt_limited(self):
        self.app.config["EMAIL_VERIFICATION_REQUIRED"] = True
        with patch("app.routers.auth.send_otp_email"):
            response = self.client.post(
                "/api/auth/register",
                json={
                    "email": "verify@example.test",
                    "display_name": "Verify User",
                    "password": "secure-password-123",
                },
                headers={"X-CSRF-Token": self.csrf},
            )
        self.assertEqual(response.status_code, 202)
        with self.app.app_context():
            challenge = get_session().query(EmailChallenge).filter_by(
                email="verify@example.test"
            ).one()
            user = get_session().query(User).filter_by(email="verify@example.test").one()
            challenge.expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
            get_session().commit()
        with patch("app.routers.auth._challenge_hash", return_value=challenge.otp_hash):
            verified = self.client.post(
                "/api/auth/verify-email",
                json={"email": user.email, "otp": "123456"},
                headers={"X-CSRF-Token": self.csrf},
            )
        self.assertEqual(verified.status_code, 200, verified.get_json())
        reused = self.client.post(
            "/api/auth/verify-email",
            json={"email": user.email, "otp": "123456"},
            headers={"X-CSRF-Token": self.csrf},
        )
        self.assertEqual(reused.status_code, 400)

    def test_password_reset_preserves_membership_and_hides_unknown_email(self):
        self.app.config["EMAIL_VERIFICATION_REQUIRED"] = True
        with patch("app.routers.auth.send_otp_email") as send:
            response = self.client.post(
                "/api/auth/forgot-password",
                json={"email": "owner@example.test"},
                headers={"X-CSRF-Token": self.csrf},
            )
        self.assertEqual(response.status_code, 200)
        self.assertIn("sent", response.get_json()["message"])
        send.assert_called_once()
        unknown = self.client.post(
            "/api/auth/forgot-password",
            json={"email": "unknown@example.test"},
            headers={"X-CSRF-Token": self.csrf},
        )
        self.assertEqual(unknown.status_code, 200)
        self.assertEqual(unknown.get_json()["message"], response.get_json()["message"])

    def test_invitation_sends_email_and_expires_in_24_hours(self):
        with patch("app.routers.homes.send_invitation_email") as send:
            response = self.request_json(
                "POST",
                f"/api/homes/{self.home_id}/invitations",
                {"email": "member@example.test"},
            )
        self.assertEqual(response.status_code, 201, response.get_json())
        send.assert_called_once()
        self.assertEqual(send.call_args.kwargs["owner_name"], "AirSense Owner")
        with self.app.app_context():
            invitation = get_session().query(HomeInvitation).filter_by(
                email="member@example.test"
            ).one()
            lifetime = invitation.expires_at - invitation.created_at
            self.assertEqual(lifetime.total_seconds(), 24 * 60 * 60)
