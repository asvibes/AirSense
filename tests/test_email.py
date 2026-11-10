import logging


def test_invitation_email_is_not_logged(owner, app, caplog, monkeypatch):
    sent_emails = []
    monkeypatch.setattr(
        "app.services.email.send_transactional_email",
        lambda **message: sent_emails.append(message),
    )
    caplog.set_level(logging.INFO, logger="app.services.email")
    for environment, recipient in (
        ("development", "member@example.test"),
        ("production", "production-member@example.test"),
    ):
        with app.app_context():
            app.config["APP_ENV"] = environment
            app.config["PUBLIC_BASE_URL"] = "https://airsense.example.test"
        response = owner.client.post(
            f"/api/homes/{owner.home_id}/invitations",
            json={"email": recipient},
            headers={"X-CSRF-Token": owner.csrf_token},
        )
        assert response.status_code == 201, response.get_json()
        token = response.get_json()["invitation"]["token"]
        assert token not in caplog.text
        assert recipient not in caplog.text
        caplog.clear()

    assert len(sent_emails) == 2
