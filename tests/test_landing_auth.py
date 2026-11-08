import json
import re
import unittest
from html import unescape
from urllib.parse import urlparse

from flask import request
from sqlalchemy import select

from app.db import get_session
from app.main import create_app
from app.models.user import User
from helpers import AirSenseTestCase


class LandingAuthTests(AirSenseTestCase):
    def test_registration_signs_in_without_email_verification(self):
        client = self.app.test_client()
        csrf = self.prepare_csrf(client)
        response = client.post(
            "/api/auth/register",
            json={
                "email": "direct-registration@example.test",
                "display_name": "Direct Registration",
                "password": "secure-password-123",
            },
            headers={"X-CSRF-Token": csrf},
        )

        self.assertEqual(response.status_code, 201, response.get_json())
        self.assertEqual(client.get("/alerts").status_code, 200)
        with self.app.app_context():
            user = get_session().scalar(
                select(User).where(
                    User.email == "direct-registration@example.test"
                )
            )
            self.assertIsNotNone(user.email_verified_at)

    def test_forwarded_headers_are_ignored_without_explicit_trust(self):
        proxy_app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "proxy-test-secret",
                "DATABASE_URL": f"sqlite:///{self.temp_dir.name}\\no-proxy.sqlite3",
                "AUTO_CREATE_SCHEMA": True,
                "TRUSTED_PROXY_HOPS": 0,
            }
        )
        proxy_app.add_url_rule(
            "/_test-client-ip",
            endpoint="_test_client_ip",
            view_func=lambda: {"ip": request.remote_addr},
        )
        try:
            response = proxy_app.test_client().get(
                "/_test-client-ip",
                environ_base={"REMOTE_ADDR": "198.51.100.10"},
                headers={"X-Forwarded-For": "203.0.113.10"},
            )
            self.assertEqual(response.json["ip"], "198.51.100.10")
        finally:
            proxy_app.extensions["airsense_engine"].dispose()

    def test_configured_proxy_hop_is_applied(self):
        database = self.temp_dir.name + "\\proxy.sqlite3"
        proxy_app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "proxy-test-secret",
                "DATABASE_URL": f"sqlite:///{database}",
                "AUTO_CREATE_SCHEMA": True,
                "TRUSTED_PROXY_HOPS": 1,
            }
        )
        try:
            proxy_app.add_url_rule(
                "/_test-client-ip",
                endpoint="_test_client_ip",
                view_func=lambda: {"ip": request.remote_addr},
            )
            response = proxy_app.test_client().get(
                "/_test-client-ip",
                environ_base={"REMOTE_ADDR": "198.51.100.10"},
                headers={"X-Forwarded-For": "203.0.113.10"},
            )
            self.assertEqual(response.json["ip"], "203.0.113.10")
        finally:
            proxy_app.extensions["airsense_engine"].dispose()
    def test_root_serves_landing_without_redirecting_unauthenticated_users(self):
        client = self.app.test_client()

        response = client.get("/", follow_redirects=False)

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.headers.get("Location"))
        self.assertIn(
            b'<a class="split-flap-cta" href="/login"', response.data
        )
        self.assertIn(
            b'<a class="landing-brand" href="/" '
            b'aria-label="AirSense landing page">AirSense</a>',
            response.data,
        )
        self.assertIn(b"Get Started", response.data)
        self.assertIn(
            b"window.addEventListener('pageshow',onPageShow)", response.data
        )
        self.assertIn(b"trigger.refresh(true)", response.data)

        root_rules = [
            rule for rule in self.app.url_map.iter_rules() if rule.rule == "/"
        ]
        self.assertEqual(len(root_rules), 1)
        self.assertEqual(root_rules[0].endpoint, "landing")

    def test_login_form_preserves_internal_next_and_success_redirects_to_dashboard(self):
        client = self.app.test_client()
        response = client.get("/login?next=/alerts")
        form_action = re.search(
            rb'<form method="post" action="([^"]+)"', response.data
        )
        csrf_token = re.search(
            rb'name="csrf_token" value="([^"]+)"', response.data
        )

        self.assertIsNotNone(form_action)
        self.assertIsNotNone(csrf_token)
        action = unescape(form_action.group(1).decode())
        self.assertIn("next=", action)

        login = client.post(
            action,
            data={
                "csrf_token": csrf_token.group(1).decode(),
                "email": "owner@example.test",
                "password": "secure-password-123",
            },
        )

        self.assertEqual(login.status_code, 302)
        self.assertEqual(login.headers["Location"], "/alerts")
        self.assertEqual(client.get("/alerts").status_code, 200)
        landing = client.get("/", follow_redirects=False)
        self.assertEqual(landing.status_code, 200)
        self.assertIsNone(landing.headers.get("Location"))

    def test_login_does_not_redirect_to_landing_when_next_is_root(self):
        client = self.app.test_client()
        next_url = "/?source=login"
        login_page = client.get("/login", query_string={"next": next_url})
        csrf = re.search(
            rb'name="csrf_token" value="([^"]+)"', login_page.data
        ).group(1).decode()

        signed_in = client.post(
            "/login",
            query_string={"next": next_url},
            data={
                "csrf_token": csrf,
                "email": "owner@example.test",
                "password": "secure-password-123",
            },
        )

        self.assertEqual(signed_in.status_code, 302)
        self.assertEqual(signed_in.headers["Location"], "/alerts")

    def test_landing_sign_in_dashboard_and_sign_out_are_connected(self):
        client = self.app.test_client()

        landing = client.get("/")
        self.assertEqual(landing.status_code, 200)
        self.assertIn(b'href="/login"', landing.data)

        login_page = client.get("/login")
        self.assertEqual(login_page.status_code, 200)
        self.assertIn(b'href="/"', login_page.data)
        csrf = re.search(
            rb'name="csrf_token" value="([^"]+)"', login_page.data
        ).group(1).decode()
        signed_in = client.post(
            "/login",
            data={
                "csrf_token": csrf,
                "email": "owner@example.test",
                "password": "secure-password-123",
            },
        )
        self.assertEqual(signed_in.status_code, 302)
        self.assertEqual(signed_in.headers["Location"], "/alerts")

        dashboard = client.get("/alerts")
        self.assertEqual(dashboard.status_code, 200)
        self.assertIn(b'AirSense <span>Home</span></a>', dashboard.data)
        self.assertIn(
            b'href="/alerts?home_id=', dashboard.data
        )
        self.assertNotIn(
            b'<a class="dashboard-home-link" href="/">', dashboard.data
        )
        self.assertIn(b"AirSense Owner", dashboard.data)
        self.assertIn(b"owner@example.test", dashboard.data)
        for path in ("/analytics", "/history", "/predictions"):
            page = client.get(path)
            self.assertEqual(page.status_code, 200, path)
            self.assertIn(
                f'href="/alerts?home_id={self.home_id}"'.encode(),
                page.data,
                path,
            )
        sign_out_form = re.search(
            rb'<form class="sign-out-form" method="post" action="([^"]+)">'
            rb'<input type="hidden" name="csrf_token" value="([^"]+)">',
            dashboard.data,
        )
        self.assertIsNotNone(sign_out_form)
        signed_out = client.post(
            unescape(sign_out_form.group(1).decode()),
            data={"csrf_token": sign_out_form.group(2).decode()},
        )
        self.assertEqual(signed_out.status_code, 302)
        self.assertEqual(signed_out.headers["Location"], "/")

        landing_after_sign_out = client.get("/")
        self.assertEqual(landing_after_sign_out.status_code, 200)
        protected_dashboard = client.get("/alerts")
        self.assertEqual(protected_dashboard.status_code, 302)
        self.assertEqual(urlparse(protected_dashboard.headers["Location"]).path, "/login")
        dashboard_script = self.client.get("/static/js/dashboard.js")
        self.assertIn(b'window.location.assign("/")', dashboard_script.data)

    def test_dashboard_sidebar_account_and_banner_content(self):
        response = self.client.get("/alerts")

        self.assertEqual(response.status_code, 200)
        dashboard = unescape(response.get_data(as_text=True))
        self.assertIn('id="sidebarToggle"', dashboard)
        self.assertIn('id="homeAccountToggle"', dashboard)
        self.assertIn("YOUR HOME", dashboard)
        self.assertIn("AirSense Owner's home", dashboard)
        self.assertIn('id="accountDetails" hidden', dashboard)
        self.assertIn("AirSense Owner", dashboard)
        self.assertIn("owner@example.test", dashboard)
        self.assertIn("Owner · Signed in", dashboard)
        self.assertIn("Sign out", dashboard)
        self.assertNotIn("Ventilation support, at a glance.", dashboard)
        self.assertIn(
            ".sidebar:not(.expanded) .nav-text{position:absolute", dashboard
        )
        self.assertIn(
            ".account-page-card{width:100%;min-width:0}", dashboard
        )
        config_json = re.search(
            r'<script id="airsense-config" type="application/json">(.*?)</script>',
            dashboard,
        )
        self.assertIsNotNone(config_json)
        config = json.loads(config_json.group(1))
        self.assertEqual(config["thresholdDefaults"]["elevated_threshold"], 1000)
        self.assertEqual(config["thresholdDefaults"]["high_threshold"], 1500)
        self.assertEqual(config["thresholdDefaults"]["max_reading_gap_seconds"], 120)
        self.assertIn('id="saveThresholds"', dashboard)
        self.assertIn('id="thresholdRows"', dashboard)
        self.assertIn("threshold-table-wrap", dashboard)
        self.assertIn(
            '#room-form .ventilation-options>label input[type="checkbox"]'
            '{width:16px;height:16px;flex:0 0 16px;margin:0}',
            dashboard,
        )
        script = self.client.get("/static/js/dashboard.js")
        self.assertEqual(script.status_code, 200)
        self.assertIn(b"async function saveThresholds()", script.data)
        self.assertIn(b'method: "PUT"', script.data)


if __name__ == "__main__":
    unittest.main()
