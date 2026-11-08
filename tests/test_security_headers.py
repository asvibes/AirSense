from flask import request

from app.main import create_app
from helpers import AirSenseTestCase


class SecurityHeaderAndProxyTests(AirSenseTestCase):
    def create_security_app(self, *, app_env, trusted_proxy_hops, name):
        app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "security-header-test-secret",
                "DEVICE_KEY_PEPPER": "security-header-test-pepper",
                "APP_ENV": app_env,
                "DATABASE_URL": f"sqlite:///{self.temp_dir.name}/{name}.sqlite3",
                "AUTO_CREATE_SCHEMA": True,
                "TRUSTED_PROXY_HOPS": trusted_proxy_hops,
            }
        )
        app.add_url_rule(
            "/_test-proxy",
            endpoint="_test_proxy",
            view_func=lambda: {
                "scheme": request.scheme,
                "remote_addr": request.remote_addr,
                "host": request.host,
                "script_root": request.script_root,
            },
        )
        return app

    def test_render_https_forwarded_proto_emits_hsts_and_preserves_other_headers(self):
        proxy_app = self.create_security_app(
            app_env="production", trusted_proxy_hops=1, name="render-proxy"
        )
        try:
            response = proxy_app.test_client().get(
                "/_test-proxy",
                environ_base={"REMOTE_ADDR": "10.0.0.8"},
                headers={
                    "X-Forwarded-For": "198.51.100.77, 203.0.113.24",
                    "X-Forwarded-Proto": "https",
                    "X-Forwarded-Host": "attacker.example",
                    "X-Forwarded-Port": "8443",
                    "X-Forwarded-Prefix": "/untrusted-prefix",
                },
            )

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.get_json()["scheme"], "https")
            self.assertEqual(response.get_json()["remote_addr"], "203.0.113.24")
            self.assertEqual(response.get_json()["host"], "localhost")
            self.assertEqual(response.get_json()["script_root"], "")
            self.assertEqual(
                response.headers["Strict-Transport-Security"],
                "max-age=31536000; includeSubDomains",
            )
            self.assertEqual(
                response.headers["Content-Security-Policy"],
                "default-src 'self'; base-uri 'self'; object-src 'none'; "
                "frame-ancestors 'none'; form-action 'self'; img-src 'self' data:; "
                "connect-src 'self'; script-src 'self' 'unsafe-inline' https://unpkg.com; "
                "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                "font-src 'self' https://fonts.gstatic.com",
            )
            self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
            self.assertEqual(response.headers["X-Frame-Options"], "DENY")
            self.assertEqual(
                response.headers["Referrer-Policy"], "strict-origin-when-cross-origin"
            )
            self.assertEqual(
                response.headers["Permissions-Policy"],
                "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
            )
        finally:
            proxy_app.extensions["airsense_engine"].dispose()

    def test_production_http_response_does_not_emit_hsts(self):
        proxy_app = self.create_security_app(
            app_env="production", trusted_proxy_hops=1, name="production-http"
        )
        try:
            response = proxy_app.test_client().get("/_test-proxy")

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.get_json()["scheme"], "http")
            self.assertNotIn("Strict-Transport-Security", response.headers)
        finally:
            proxy_app.extensions["airsense_engine"].dispose()

    def test_development_ignores_spoofed_https_header_without_forcing_https(self):
        dev_app = self.create_security_app(
            app_env="development", trusted_proxy_hops=0, name="development-http"
        )
        try:
            response = dev_app.test_client().get(
                "/_test-proxy",
                headers={"X-Forwarded-Proto": "https"},
            )

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.get_json()["scheme"], "http")
            self.assertNotIn("Strict-Transport-Security", response.headers)
        finally:
            dev_app.extensions["airsense_engine"].dispose()
