import re
import tempfile
import unittest
from pathlib import Path

from app.main import create_app


class AirSenseTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        database = Path(self.temp_dir.name) / "airsense.sqlite3"
        self.app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "test-secret-key",
                "DATABASE_URL": f"sqlite:///{database.as_posix()}",
                "AUTO_CREATE_SCHEMA": True,
                "REQUIRE_API_TOKEN": False,
                **getattr(self, "config_overrides", {}),
            }
        )
        self.client = self.app.test_client()
        self.csrf = self.prepare_csrf(self.client)
        response = self.client.post(
            "/api/auth/register",
            json={
                "email": "owner@example.test",
                "display_name": "AirSense Owner",
                "password": "secure-password-123",
            },
            headers={"X-CSRF-Token": self.csrf},
        )
        self.assertEqual(response.status_code, 201, response.get_json())
        self.csrf = self.current_csrf(self.client)
        self.home_id = response.get_json()["home"]["id"]

    def tearDown(self):
        self.app.extensions["airsense_engine"].dispose()
        self.temp_dir.cleanup()

    @staticmethod
    def prepare_csrf(client):
        response = client.get("/register")
        match = re.search(rb'name="csrf_token" value="([^"]+)"', response.data)
        if match:
            return match.group(1).decode()
        return AirSenseTestCase.current_csrf(client)

    @staticmethod
    def current_csrf(client):
        with client.session_transaction() as browser_session:
            return browser_session["csrf_token"]

    def request_json(self, method, path, payload=None, *, client=None, headers=None):
        request_headers = {"X-CSRF-Token": self.csrf}
        request_headers.update(headers or {})
        return (client or self.client).open(
            path,
            method=method,
            json=payload,
            headers=request_headers,
        )

    def create_room(self, name="Living room", ventilation="Window", home_id=None):
        sources = ventilation if isinstance(ventilation, list) else [ventilation]
        response = self.request_json(
            "POST",
            f"/api/homes/{home_id or self.home_id}/rooms",
            {"name": name, "ventilation_sources": sources},
        )
        self.assertEqual(response.status_code, 201, response.get_json())
        return response.get_json()["room"]

    def register_client(self, email, display_name):
        client = self.app.test_client()
        csrf = self.prepare_csrf(client)
        response = client.post(
            "/api/auth/register",
            json={
                "email": email,
                "display_name": display_name,
                "password": "secure-password-123",
            },
            headers={"X-CSRF-Token": csrf},
        )
        self.assertEqual(response.status_code, 201, response.get_json())
        return client, response.get_json(), self.current_csrf(client)
