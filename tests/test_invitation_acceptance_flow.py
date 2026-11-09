import hashlib
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

from sqlalchemy import select

from app.db import get_session
from app.models.user import HomeInvitation, HomeMembership, User
from helpers import AirSenseTestCase


class InvitationAcceptanceFlowTests(AirSenseTestCase):
    def create_invitation(self, email):
        response = self.request_json(
            "POST",
            f"/api/homes/{self.home_id}/invitations",
            {"email": email},
        )
        self.assertEqual(response.status_code, 201, response.get_json())
        return response.get_json()["invitation"]

    def login_with_existing_account(self, client, email, *, next_url="/join"):
        page = client.get("/login", query_string={"next": next_url})
        csrf = re.search(rb'name="csrf_token" value="([^"]+)"', page.data).group(1).decode()
        response = client.post(
            "/login",
            query_string={"next": next_url},
            data={
                "csrf_token": csrf,
                "email": email,
                "password": "secure-password-123",
            },
        )
        return response

    def test_join_without_invitation_returns_to_landing_without_login_next(self):
        anonymous = self.app.test_client()

        response = anonymous.get("/join")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/")
        with anonymous.session_transaction() as browser_session:
            self.assertNotIn("pending_invitation_hash", browser_session)

    def test_unauthenticated_invitation_is_carried_to_sign_in_without_raw_token(self):
        invitation = self.create_invitation("recipient@example.test")
        anonymous = self.app.test_client()

        response = anonymous.get(f"/join?token={invitation['token']}")

        self.assertEqual(response.status_code, 302)
        location = response.headers["Location"]
        self.assertEqual(urlparse(location).path, "/login")
        self.assertEqual(parse_qs(urlparse(location).query)["next"], ["/join"])
        self.assertNotIn(invitation["token"], location)
        with anonymous.session_transaction() as browser_session:
            self.assertEqual(
                browser_session["pending_invitation_hash"],
                hashlib.sha256(invitation["token"].encode()).hexdigest(),
            )
            self.assertNotIn(invitation["token"], str(dict(browser_session)))

        rejected = anonymous.post(
            "/api/invitations/accept", json={"token": invitation["token"]}
        )
        self.assertEqual(rejected.status_code, 401)
        with self.app.app_context():
            stored = get_session().get(HomeInvitation, invitation["id"])
            self.assertIsNone(stored.accepted_at)
            self.assertIsNone(
                get_session().get(HomeMembership, (self.home_id, "not-authenticated"))
            )

    def test_successful_login_automatically_accepts_invitation_and_opens_home(self):
        invitation = self.create_invitation("recipient@example.test")
        self.register_client("recipient@example.test", "Invited Recipient")
        anonymous = self.app.test_client()
        handoff = anonymous.get(f"/join?token={invitation['token']}")
        self.assertEqual(handoff.status_code, 302)

        login = self.login_with_existing_account(anonymous, "recipient@example.test")

        self.assertEqual(login.status_code, 302)
        self.assertEqual(urlparse(login.headers["Location"]).path, "/alerts")
        self.assertEqual(
            parse_qs(urlparse(login.headers["Location"]).query).get("home_id"),
            [self.home_id],
        )
        dashboard = anonymous.get(login.headers["Location"])
        self.assertEqual(dashboard.status_code, 200)
        with anonymous.session_transaction() as browser_session:
            self.assertNotIn("pending_invitation_hash", browser_session)
        with self.app.app_context():
            user = get_session().scalar(
                select(User).where(User.email == "recipient@example.test")
            )
            membership = get_session().get(HomeMembership, (self.home_id, user.id))
            stored = get_session().get(HomeInvitation, invitation["id"])
            self.assertEqual(membership.role, "member")
            self.assertIsNotNone(stored.accepted_at)

    def test_wrong_account_login_does_not_accept_invitation_and_allows_switch(self):
        invitation = self.create_invitation("recipient@example.test")
        self.register_client("wrong-account@example.test", "Wrong Account")
        client = self.app.test_client()
        client.get(f"/join?token={invitation['token']}")

        login = self.login_with_existing_account(client, "wrong-account@example.test")

        self.assertEqual(login.status_code, 302)
        self.assertEqual(login.headers["Location"], "/join?error=wrong-account")
        page = client.get(login.headers["Location"])
        self.assertEqual(page.status_code, 200)
        self.assertIn(b"different email address", page.data)
        self.assertIn(b"switch-account-form", page.data)
        with self.app.app_context():
            user = get_session().scalar(
                select(User).where(User.email == "wrong-account@example.test")
            )
            self.assertIsNone(get_session().get(HomeMembership, (self.home_id, user.id)))
            self.assertIsNone(get_session().get(HomeInvitation, invitation["id"]).accepted_at)
        with client.session_transaction() as browser_session:
            self.assertEqual(
                browser_session["pending_invitation_hash"],
                hashlib.sha256(invitation["token"].encode()).hexdigest(),
            )

        csrf = re.search(rb'name="csrf_token" value="([^"]+)"', page.data).group(1).decode()
        signed_out = client.post("/logout", data={"csrf_token": csrf})
        self.assertEqual(signed_out.status_code, 302)
        self.assertEqual(urlparse(signed_out.headers["Location"]).path, "/login")
        self.assertEqual(parse_qs(urlparse(signed_out.headers["Location"]).query)["next"], ["/join"])
        with client.session_transaction() as browser_session:
            self.assertEqual(
                browser_session["pending_invitation_hash"],
                hashlib.sha256(invitation["token"].encode()).hexdigest(),
            )

    def test_expired_invitation_is_rejected_after_sign_in(self):
        invitation = self.create_invitation("recipient@example.test")
        self.register_client("recipient@example.test", "Invited Recipient")
        with self.app.app_context():
            stored = get_session().get(HomeInvitation, invitation["id"])
            stored.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
            get_session().commit()

        client = self.app.test_client()
        client.get(f"/join?token={invitation['token']}")
        login = self.login_with_existing_account(client, "recipient@example.test")

        self.assertEqual(login.status_code, 302)
        self.assertEqual(login.headers["Location"], "/join?error=expired")
        page = client.get(login.headers["Location"])
        self.assertIn(b"This invitation has expired", page.data)
        with self.app.app_context():
            user = get_session().scalar(
                select(User).where(User.email == "recipient@example.test")
            )
            self.assertIsNone(get_session().get(HomeMembership, (self.home_id, user.id)))
            self.assertIsNone(get_session().get(HomeInvitation, invitation["id"]).accepted_at)
        with client.session_transaction() as browser_session:
            self.assertNotIn("pending_invitation_hash", browser_session)

    def test_already_authenticated_recipient_accepts_directly_from_join_link(self):
        invitation = self.create_invitation("recipient@example.test")
        client, account, csrf = self.register_client(
            "recipient@example.test", "Invited Recipient"
        )

        page = client.get(f"/join?token={invitation['token']}")

        self.assertEqual(page.status_code, 200)
        self.assertIn(b"const autoAccept = true", page.data)
        self.assertNotIn(invitation["token"].encode(), page.data)
        accepted = client.post(
            "/api/invitations/accept",
            json={},
            headers={"X-CSRF-Token": csrf},
        )
        self.assertEqual(accepted.status_code, 200, accepted.get_json())
        self.assertEqual(accepted.get_json()["home_id"], self.home_id)
        with self.app.app_context():
            membership = get_session().get(
                HomeMembership, (self.home_id, account["user"]["id"])
            )
            self.assertEqual(membership.role, "member")
            self.assertIsNotNone(get_session().get(HomeInvitation, invitation["id"]).accepted_at)
        repeated = client.post(
            "/api/invitations/accept",
            json={"token": invitation["token"]},
            headers={"X-CSRF-Token": csrf},
        )
        self.assertEqual(repeated.status_code, 404)
