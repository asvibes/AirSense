import re
import unittest
from html import unescape

from helpers import AirSenseTestCase


class LandingAuthTests(AirSenseTestCase):
    def test_root_serves_landing_without_redirecting_unauthenticated_users(self):
        client = self.app.test_client()

        response = client.get("/", follow_redirects=False)

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.headers.get("Location"))
        self.assertIn(
            b'<a class="split-flap-cta" href="/login"', response.data
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

    def test_login_form_preserves_next_and_success_redirects_to_dashboard(self):
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


if __name__ == "__main__":
    unittest.main()
