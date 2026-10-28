from typing import Any

from flask import Flask
from flask import jsonify, request
from werkzeug.exceptions import HTTPException
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
from app.security.rate_limit import InMemoryRateLimiter


def create_app(test_config: dict[str, Any] | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)
    if test_config is not None:
        app.config.update(test_config)
    if app.config["APP_ENV"] == "production":
        if app.config["SECRET_KEY"] == "local-development-key-change-me":
            raise RuntimeError("SECRET_KEY must be configured in production.")
        if not app.config["DEVICE_KEY_PEPPER"]:
            raise RuntimeError("AIRSENSE_DEVICE_KEY_PEPPER must be configured in production.")
        app.config["SESSION_COOKIE_SECURE"] = True
    init_db(app)
    app.extensions["airsense_rate_limiter"] = InMemoryRateLimiter()
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
    ):
        app.register_blueprint(blueprint)

    @app.errorhandler(HTTPException)
    def handle_http_error(error: HTTPException):
        if request.path.startswith("/api/"):
            return jsonify(error=error.description), error.code
        return error

    @app.get("/api/health")
    def health():
        get_session().execute(text("SELECT 1"))
        return {"status": "ok"}

    return app