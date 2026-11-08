from typing import Any

from flask import Flask, request
from werkzeug.middleware.proxy_fix import ProxyFix
from sqlalchemy import text

from app.config import Config
from app.db import get_session, init_db
from app.routers.alerts import alerts
from app.routers.audit import audit
from app.routers.auth import auth
from app.routers.dashboard import dashboard
from app.routers.demo import demo
from app.routers.history import history
from app.routers.homes import homes
from app.routers.rooms import rooms
from app.routers.sensor_readings import sensor_readings
from app.routers.sensors import sensors
from app.routers.thresholds import thresholds
from app.routers.uploads import uploads
from .error_handlers import register_error_handlers

def create_app(test_config: dict[str, Any] | None = None) -> Flask:
    app = Flask(__name__)
    register_error_handlers(app)
    app.config.from_object(Config)
    if test_config is not None:
        app.config.update(test_config)
    if app.config.get("MAX_LIVE_READING_AGE_SECONDS") is None:
        app.config["MAX_LIVE_READING_AGE_SECONDS"] = 24 * 60 * 60
    if app.config.get("TESTING") and "EMAIL_VERIFICATION_REQUIRED" not in (test_config or {}):
        app.config["EMAIL_VERIFICATION_REQUIRED"] = False
    if app.config["APP_ENV"] == "production":
        if app.config["SECRET_KEY"] == "local-development-key-change-me":
            raise RuntimeError("SECRET_KEY must be configured in production.")
        if not app.config["DEVICE_KEY_PEPPER"]:
            raise RuntimeError("AIRSENSE_DEVICE_KEY_PEPPER must be configured in production.")
        app.config["SESSION_COOKIE_SECURE"] = True
    trusted_proxy_hops = app.config["TRUSTED_PROXY_HOPS"]
    if trusted_proxy_hops < 0:
        raise RuntimeError("TRUSTED_PROXY_HOPS must be zero or greater.")
    if trusted_proxy_hops:
        app.wsgi_app = ProxyFix(
            app.wsgi_app,
            x_for=trusted_proxy_hops,
            x_proto=trusted_proxy_hops,
            x_host=0,
            x_port=0,
            x_prefix=0,
        )
    init_db(app)

    @app.after_request
    def add_security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Permissions-Policy",
            "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
        )
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; "
            "base-uri 'self'; object-src 'none'; frame-ancestors 'none'; "
            "form-action 'self'; img-src 'self' data:; connect-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://unpkg.com; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com",
        )
        if app.config["APP_ENV"] == "production" and request.is_secure:
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains",
            )
        return response

    for blueprint in (
        auth,
        homes,
        rooms,
        sensors,
        sensor_readings,
        thresholds,
        dashboard,
        history,
        audit,
        demo,
        alerts,
        uploads,
    ):
        app.register_blueprint(blueprint)

    @app.get("/api/health")
    def health():
        get_session().execute(text("SELECT 1"))
        return {"status": "ok"}

    @app.get("/")
    def landing():
        from flask import render_template
        return render_template("landing.html")

    return app
