import unittest

from werkzeug.exceptions import HTTPException

from helpers import AirSenseTestCase


class ErrorHandlerTests(AirSenseTestCase):
    def test_http_errors_render_error_template_and_home_links_use_landing_route(self):
        client = self.app.test_client()

        for response, code, title in (
            (client.get("/missing-page"), 404, b"Not found"),
            (client.post("/"), 405, b"Method not allowed"),
            (client.post("/login"), 400, b"Bad request"),
        ):
            with self.subTest(status=code):
                self.assertEqual(response.status_code, code)
                self.assertIn(b"error-shell", response.data)
                self.assertIn(title, response.data)
                self.assertIn(
                    b'<a class="home-link" href="/">Return home',
                    response.data,
                )
                self.assertIn(
                    b'<a class="brand" href="/" aria-label="AirSense home">',
                    response.data,
                )

    def test_unexpected_error_renders_500_template(self):
        self.app.config["PROPAGATE_EXCEPTIONS"] = False

        def raise_server_error():
            raise RuntimeError("test-only server error")

        self.app.view_functions["health"] = raise_server_error
        response = self.app.test_client().get("/api/health")

        self.assertEqual(response.status_code, 500)
        self.assertIn(b"error-shell", response.data)
        self.assertIn(b"HTTP 500", response.data)
        self.assertIn(b"Server error", response.data)

    def test_api_http_errors_remain_json(self):
        response = self.app.test_client().get("/api/missing-endpoint")

        self.assertEqual(response.status_code, 404)
        self.assertIn("error", response.get_json())

    def test_landing_login_dashboard_and_error_routes_work_together(self):
        client = self.app.test_client()

        landing = client.get("/")
        login = client.get("/login")
        dashboard = self.client.get("/alerts")
        missing = client.get("/missing-page")

        self.assertEqual(landing.status_code, 200)
        self.assertIn(b"split-flap-cta", landing.data)
        self.assertEqual(login.status_code, 200)
        self.assertIn(b"Sign in", login.data)
        self.assertEqual(dashboard.status_code, 200)
        self.assertIn(b"Recent alerts", dashboard.data)
        self.assertEqual(missing.status_code, 404)
        self.assertIn(b"error-shell", missing.data)


if __name__ == "__main__":
    unittest.main()
