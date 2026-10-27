from typing import Any

from flask import Flask
from sqlalchemy import text

from app.config import Config
from app.db import get_session, init_db
from app.routers.alerts import alerts


def create_app(test_config: dict[str, Any] | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)
    if test_config is not None:
        app.config.update(test_config)
    init_db(app)
    app.register_blueprint(alerts)

    @app.get("/api/health")
    def health():
        get_session().execute(text("SELECT 1"))
        return {"status": "ok"}

    return app