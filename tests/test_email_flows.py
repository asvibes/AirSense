from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from sqlalchemy import select

from app.db import get_session
from app.models.user import EmailChallenge, HomeInvitation, HomeMembership, RateLimitBucket, User
from app.security.rate_limit import allow_persistent
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
            user = get_session().query(User).filter_by(email="new@example.test").one()
            self.assertTrue(user.is_active)
            self.assertIsNone(user.email_verified_at)
            self.assertEqual(
                get_session().scalar(
                    select(HomeMembership.home_id).where(HomeMembership.user_id == user.id)
                ),
                None,
            )

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

    def test_verification_does_not_reactivate_disabled_account(self):
        self.app.config["EMAIL_VERIFICATION_REQUIRED"] = True
        with patch("app.routers.auth.send_otp_email") as send:
            response = self.client.post(
                "/api/auth/register",
                json={
                    "email": "disabled@example.test",
                    "display_name": "Disabled User",
                    "password": "secure-password-123",
                },
                headers={"X-CSRF-Token": self.csrf},
            )
        self.assertEqual(response.status_code, 202)
        with self.app.app_context():
            db = get_session()
            user = db.scalar(select(User).where(User.email == "disabled@example.test"))
            user.is_active = False
            db.commit()
        verification = self.client.post(
            "/api/auth/verify-email",
            json={"email": "disabled@example.test", "otp": send.call_args.kwargs["otp"]},
            headers={"X-CSRF-Token": self.csrf},
        )
        self.assertEqual(verification.status_code, 400)
        with self.app.app_context():
            user = get_session().scalar(select(User).where(User.email == "disabled@example.test"))
            self.assertFalse(user.is_active)
            self.assertIsNone(user.email_verified_at)

    def test_otp_failures_persist_and_lock_the_challenge(self):
        self.app.config["EMAIL_VERIFICATION_REQUIRED"] = True
        with patch("app.routers.auth.send_otp_email") as send:
            response = self.client.post(
                "/api/auth/register",
                json={
                    "email": "locked@example.test",
                    "display_name": "Locked User",
                    "password": "secure-password-123",
                },
                headers={"X-CSRF-Token": self.csrf},
            )
        self.assertEqual(response.status_code, 202)
        otp = send.call_args.kwargs["otp"]
        for _ in range(5):
            failed = self.client.post(
                "/api/auth/verify-email",
                json={"email": "locked@example.test", "otp": "000000"},
                headers={"X-CSRF-Token": self.csrf},
            )
            self.assertEqual(failed.status_code, 400)
        with self.app.app_context():
            challenge = get_session().query(EmailChallenge).filter_by(
                email="locked@example.test"
            ).one()
            self.assertEqual(challenge.attempts, 5)
        locked = self.client.post(
            "/api/auth/verify-email",
            json={"email": "locked@example.test", "otp": otp},
            headers={"X-CSRF-Token": self.csrf},
        )
        self.assertEqual(locked.status_code, 400)

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

    def test_password_reset_token_is_expiring_single_use_and_invalidates_sessions(self):
        with patch("app.routers.auth.send_otp_email") as send:
            response = self.client.post(
                "/api/auth/forgot-password",
                json={"email": "owner@example.test"},
                headers={"X-CSRF-Token": self.csrf},
            )
        self.assertEqual(response.status_code, 200)
        verified = self.client.post(
            "/api/auth/verify-reset",
            json={"email": "owner@example.test", "otp": send.call_args.kwargs["otp"]},
            headers={"X-CSRF-Token": self.csrf},
        )
        self.assertEqual(verified.status_code, 200)
        reset_token = verified.get_json()["reset_token"]
        with self.app.app_context():
            challenge = get_session().query(EmailChallenge).filter_by(
                reset_token_hash=challenge_hash(reset_token, self.app)
            ).one()
            self.assertIsNotNone(challenge.reset_token_expires_at)
            self.assertIsNone(challenge.reset_token_used_at)
        reset = self.client.post(
            "/api/auth/reset-password",
            json={"reset_token": reset_token, "password": "new-secure-password-123"},
            headers={"X-CSRF-Token": self.csrf},
        )
        self.assertEqual(reset.status_code, 200, reset.get_json())
        reused = self.client.post(
            "/api/auth/reset-password",
            json={"reset_token": reset_token, "password": "another-password-123"},
            headers={"X-CSRF-Token": self.csrf},
        )
        self.assertEqual(reused.status_code, 400)
        with self.app.app_context():
            from sqlalchemy.orm import Session

            with Session(self.app.extensions["airsense_engine"]) as fresh_session:
                challenge = fresh_session.query(EmailChallenge).filter_by(
                    reset_token_hash=challenge_hash(reset_token, self.app)
                ).one()
                self.assertIsNotNone(challenge.reset_token_used_at)
        self.assertEqual(self.client.get("/api/me").status_code, 401)

    def test_reset_token_reuse_is_rejected_from_a_fresh_client(self):
        with patch("app.routers.auth.send_otp_email") as send:
            self.client.post(
                "/api/auth/forgot-password",
                json={"email": "owner@example.test"},
                headers={"X-CSRF-Token": self.csrf},
            )
        verified = self.client.post(
            "/api/auth/verify-reset",
            json={"email": "owner@example.test", "otp": send.call_args.kwargs["otp"]},
            headers={"X-CSRF-Token": self.csrf},
        )
        reset_token = verified.get_json()["reset_token"]
        with self.app.app_context():
            challenge = get_session().query(EmailChallenge).filter_by(
                reset_token_hash=challenge_hash(reset_token, self.app)
            ).one()
            self.assertIsNotNone(challenge.reset_token_expires_at)
        first = self.client.post(
            "/api/auth/reset-password",
            json={"reset_token": reset_token, "password": "new-secure-password-123"},
            headers={"X-CSRF-Token": self.csrf},
        )
        self.assertEqual(first.status_code, 200, first.get_json())
        fresh_client = self.app.test_client()
        csrf = self.prepare_csrf(fresh_client)
        second = fresh_client.post(
            "/api/auth/reset-password",
            json={"reset_token": reset_token, "password": "another-password-123"},
            headers={"X-CSRF-Token": csrf},
        )
        self.assertEqual(second.status_code, 400)

    def test_persistent_rate_limit_enforces_boundary_and_expiry(self):
        with self.app.app_context():
            db = get_session()
            key = "test:rate-limit"
            self.assertTrue(allow_persistent(db, key, limit=2, window_seconds=60))
            self.assertTrue(allow_persistent(db, key, limit=2, window_seconds=60))
            self.assertFalse(allow_persistent(db, key, limit=2, window_seconds=60))
            bucket = db.get(RateLimitBucket, key)
            bucket.window_started_at = datetime.now(timezone.utc) - timedelta(seconds=61)
            db.commit()
            self.assertTrue(allow_persistent(db, key, limit=2, window_seconds=60))

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


def challenge_hash(token, app):
    import hashlib

    return hashlib.sha256(
        f"{app.config['SECRET_KEY']}:reset:{token}".encode()
    ).hexdigest()
