import logging


def test_invitation_email_is_logged_only_in_development(owner, app, caplog):
    caplog.set_level(logging.INFO, logger="app.services.email")
    with app.app_context():
        app.config["APP_ENV"] = "development"
    response = owner.client.post(
        f"/api/homes/{owner.home_id}/invitations",
        json={"email": "member@example.test"},
        headers={"X-CSRF-Token": owner.csrf_token},
    )
    assert response.status_code == 201
    token = response.get_json()["invitation"]["token"]
    assert token in caplog.text

    caplog.clear()
    with app.app_context():
        app.config["APP_ENV"] = "production"
    response = owner.client.post(
        f"/api/homes/{owner.home_id}/invitations",
        json={"email": "production-member@example.test"},
        headers={"X-CSRF-Token": owner.csrf_token},
    )
    assert response.status_code == 201
    production_token = response.get_json()["invitation"]["token"]
    assert production_token not in caplog.text
    assert "production-member@example.test" not in caplog.text
