import re
from dataclasses import dataclass

import pytest

from app.main import create_app


@dataclass
class AuthenticatedUser:
    client: object
    csrf_token: str
    user_id: str
    home_id: str


@pytest.fixture
def app(tmp_path, tmp_path_factory):
    database = tmp_path / "airsense-test.sqlite3"
    application = create_app(
        {
            "TESTING": True,
            "APP_ENV": "development",
            "SECRET_KEY": "pytest-secret",
            "DATABASE_URL": f"sqlite:///{database.as_posix()}",
            "AUTO_CREATE_SCHEMA": True,
            "PRIVATE_UPLOAD_FOLDER": str(tmp_path_factory.mktemp("u")),
            "MAX_CONTENT_LENGTH": 17 * 1024 * 1024,
        }
    )
    yield application
    application.extensions["airsense_engine"].dispose()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def owner(client):
    response = client.get("/register")
    match = re.search(rb'name="csrf_token" value="([^"]+)"', response.data)
    assert match, "registration page must provide a CSRF token"
    csrf_token = match.group(1).decode()
    response = client.post(
        "/api/auth/register",
        json={
            "email": "pytest-owner@example.test",
            "display_name": "Pytest Owner",
            "password": "secure-password-123",
        },
        headers={"X-CSRF-Token": csrf_token},
    )
    assert response.status_code == 201, response.get_json()
    with client.session_transaction() as browser_session:
        csrf_token = browser_session["csrf_token"]
    body = response.get_json()
    return AuthenticatedUser(
        client=client,
        csrf_token=csrf_token,
        user_id=body["user"]["id"],
        home_id=body["home"]["id"],
    )


@pytest.fixture
def room(owner):
    response = owner.client.post(
        f"/api/homes/{owner.home_id}/rooms",
        json={"name": "Pytest room", "ventilation_sources": ["Window"]},
        headers={"X-CSRF-Token": owner.csrf_token},
    )
    assert response.status_code == 201, response.get_json()
    return response.get_json()["room"]