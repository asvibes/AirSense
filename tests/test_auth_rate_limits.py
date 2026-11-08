from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from sqlalchemy import select

from app.db import get_session
from app.main import create_app
from app.models.user import RateLimitBucket, User
from app.security.rate_limit import allow_persistent
from helpers import AirSenseTestCase


class AuthenticationRateLimitTests(AirSenseTestCase):
    def _login(
        self,
        *,
        email="owner@example.test",
        password="wrong-password",
        ip=None,
        client=None,
        csrf=None,
    ):
        request_client = client or self.client
        request = {
            "json": {"email": email, "password": password},
            "headers": {"X-CSRF-Token": csrf or self.csrf},
        }
        if ip:
            request["environ_base"] = {"REMOTE_ADDR": ip}
        return request_client.post("/api/auth/login", **request)

    def test_failed_login_records_persistent_ip_and_normalized_email_buckets(self):
        response = self._login(email=" OWNER@EXAMPLE.TEST ")

        self.assertEqual(response.status_code, 401)
        with self.app.app_context():
            db = get_session()
            ip_bucket = db.get(RateLimitBucket, "auth:login-failure:ip:127.0.0.1")
            email_bucket = db.get(
                RateLimitBucket, "auth:login-failure:email:owner@example.test"
            )
            self.assertEqual(ip_bucket.count, 1)
            self.assertEqual(email_bucket.count, 1)

    def test_subsequent_failed_login_increments_each_bucket_once(self):
        for expected_count in (1, 2):
            response = self._login(email=" OWNER@EXAMPLE.TEST ")
            self.assertEqual(response.status_code, 401)
            with self.app.app_context():
                db = get_session()
                self.assertEqual(
                    db.get(
                        RateLimitBucket,
                        "auth:login-failure:ip:127.0.0.1",
                    ).count,
                    expected_count,
                )
                self.assertEqual(
                    db.get(
                        RateLimitBucket,
                        "auth:login-failure:email:owner@example.test",
                    ).count,
                    expected_count,
                )

    def test_successful_login_does_not_consume_failed_login_capacity(self):
        response = self._login(password="secure-password-123")

        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            db = get_session()
            self.assertIsNone(
                db.get(RateLimitBucket, "auth:login-failure:ip:127.0.0.1")
            )
            self.assertIsNone(
                db.get(
                    RateLimitBucket,
                    "auth:login-failure:email:owner@example.test",
                )
            )

    def test_valid_password_for_disabled_account_does_not_record_failure(self):
        with self.app.app_context():
            user = get_session().scalar(
                select(User).where(User.email == "owner@example.test")
            )
            user.is_active = False
            get_session().commit()

        response = self._login(password="secure-password-123")

        self.assertEqual(response.status_code, 403)
        with self.app.app_context():
            self.assertIsNone(
                get_session().get(
                    RateLimitBucket, "auth:login-failure:email:owner@example.test"
                )
            )

    def test_valid_password_for_unverified_account_does_not_record_failure(self):
        self.app.config["EMAIL_VERIFICATION_REQUIRED"] = True
        with self.app.app_context():
            user = get_session().scalar(
                select(User).where(User.email == "owner@example.test")
            )
            user.email_verified_at = None
            get_session().commit()

        response = self._login(password="secure-password-123")

        self.assertEqual(response.status_code, 403)
        with self.app.app_context():
            self.assertIsNone(
                get_session().get(
                    RateLimitBucket, "auth:login-failure:email:owner@example.test"
                )
            )

    def test_blocked_login_checks_buckets_before_password_verification(self):
        with self.app.app_context():
            db = get_session()
            for key in (
                "auth:login-failure:ip:127.0.0.1",
                "auth:login-failure:email:owner@example.test",
            ):
                for _ in range(10):
                    allow_persistent(
                        db,
                        key,
                        limit=10,
                        window_seconds=self.app.config["AUTH_RATE_LIMIT_WINDOW_SECONDS"],
                    )

        with patch("app.routers.auth.verify_password") as verify:
            response = self._login(password="secure-password-123")

        self.assertEqual(response.status_code, 429)
        verify.assert_not_called()

    def test_ip_limit_applies_across_email_addresses(self):
        for index in range(10):
            response = self._login(
                email=f"unknown-{index}@example.test",
                ip="198.51.100.10",
            )
            self.assertEqual(response.status_code, 401)

        blocked = self._login(email="another@example.test", ip="198.51.100.10")

        self.assertEqual(blocked.status_code, 429)

    def test_email_limit_applies_across_client_ips(self):
        for index in range(10):
            response = self._login(
                email="owner@example.test",
                ip=f"198.51.100.{index + 10}",
            )
            self.assertEqual(response.status_code, 401)

        blocked = self._login(
            email="OWNER@EXAMPLE.TEST",
            ip="203.0.113.10",
        )

        self.assertEqual(blocked.status_code, 429)

    def test_failed_login_limit_persists_across_application_instances(self):
        for _ in range(10):
            response = self._login(email="persisted@example.test")
            self.assertEqual(response.status_code, 401)

        second_app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "test-secret-key",
                "DATABASE_URL": self.app.config["DATABASE_URL"],
                "AUTO_CREATE_SCHEMA": True,
                "REQUIRE_API_TOKEN": False,
            }
        )
        try:
            second_client = second_app.test_client()
            second_client.get("/login")
            csrf = self.current_csrf(second_client)
            blocked = self._login(
                client=second_client,
                csrf=csrf,
                email="persisted@example.test",
            )
            self.assertEqual(blocked.status_code, 429)
        finally:
            second_app.extensions["airsense_engine"].dispose()

    def test_concurrent_failed_logins_cannot_exceed_failure_limit(self):
        requests = []
        for _ in range(12):
            client = self.app.test_client()
            client.get("/login")
            requests.append((client, self.current_csrf(client)))

        def submit(request):
            client, csrf = request
            return self._login(
                client=client,
                csrf=csrf,
                email="concurrent@example.test",
                ip="198.51.100.20",
            ).status_code

        with ThreadPoolExecutor(max_workers=12) as executor:
            statuses = list(executor.map(submit, requests))

        self.assertTrue(set(statuses) <= {401, 429})
        self.assertLessEqual(statuses.count(401), 10)
        self.assertGreaterEqual(statuses.count(429), 2)
        with self.app.app_context():
            db = get_session()
            ip_bucket = db.get(
                RateLimitBucket, "auth:login-failure:ip:198.51.100.20"
            )
            email_bucket = db.get(
                RateLimitBucket,
                "auth:login-failure:email:concurrent@example.test",
            )
            self.assertEqual(ip_bucket.count, 10)
            self.assertEqual(email_bucket.count, 10)
