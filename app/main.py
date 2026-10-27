import math
from typing import Any

from flask import Flask, jsonify, redirect, render_template, request, url_for
from werkzeug.exceptions import BadRequest

from app.config import Config
from app.db import get_db, init_db
from app.services.alerts.all_clear import InvalidAlertTransition
from app.repositories.alerts import (
    AlertNotFound,
    acknowledge_alert,
    list_alerts,
    process_reading,
)


def create_app(test_config: dict[str, Any] | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)
    if test_config is not None:
        app.config.update(test_config)
    init_db(app)

    @app.get("/")
    def index():
        return redirect(url_for("alerts_page"))

    @app.get("/alerts")
    def alerts_page():
        return render_template(
            "alerts.html",
            alerts=list_alerts(get_db()),
            error=request.args.get("error"),
            notice=request.args.get("notice"),
        )

    @app.get("/api/alerts")
    def api_alerts():
        return jsonify(alerts=list_alerts(get_db()))

    @app.post("/api/readings")
    @app.post("/readings")
    def submit_reading():
        try:
            payload = _request_payload()
            room_name = _required_text(payload, "room", 100)
            co2_ppm = _number(payload, "co2_ppm", minimum=0)
            threshold_ppm = _number(payload, "threshold_ppm", minimum=0, exclusive=True)
        except ValueError as error:
            return _request_error(str(error), 400)

        alert, action = process_reading(
            get_db(),
            room_name=room_name,
            co2_ppm=co2_ppm,
            threshold_ppm=threshold_ppm,
        )
        if _wants_json():
            return jsonify(action=action, alert=alert), 201 if action == "open" else 200

        notice = {
            "open": "A new alert was created.",
            "update": "The reading was added to the open alert.",
            "clear": "The alert is now all clear.",
            "none": "Reading recorded; no alert is active.",
        }[action]
        return redirect(url_for("alerts_page", notice=notice))

    @app.post("/api/alerts/<int:alert_id>/acknowledge")
    @app.post("/alerts/<int:alert_id>/acknowledge")
    def acknowledge(alert_id: int):
        try:
            payload = _request_payload()
            acknowledged_by = _required_text(payload, "acknowledged_by", 120)
            alert = acknowledge_alert(get_db(), alert_id, acknowledged_by)
        except InvalidAlertTransition as error:
            return _request_error(str(error), 409)
        except ValueError as error:
            return _request_error(str(error), 400)
        except AlertNotFound as error:
            return _request_error(str(error), 404)

        if _wants_json():
            return jsonify(alert=alert)
        return redirect(url_for("alerts_page", notice="Alert acknowledged."))

    return app


def _request_payload():
    if request.is_json:
        try:
            payload = request.get_json()
        except BadRequest as error:
            raise ValueError("Request body must contain valid JSON.") from error
        if not isinstance(payload, dict):
            raise ValueError("JSON request body must be an object.")
        return payload
    return request.form


def _required_text(payload, field: str, maximum_length: int) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} is required.")
    value = value.strip()
    if len(value) > maximum_length:
        raise ValueError(f"{field} must be {maximum_length} characters or fewer.")
    return value


def _number(payload, field: str, minimum: float, exclusive: bool = False) -> float:
    value = payload.get(field)
    if isinstance(value, bool):
        raise ValueError(f"{field} must be a number.")
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{field} must be a number.") from error

    if not math.isfinite(number):
        raise ValueError(f"{field} must be finite.")
    if number < minimum or (exclusive and number == minimum):
        operator = "greater than" if exclusive else "at least"
        raise ValueError(f"{field} must be {operator} {minimum:g}.")
    return number


def _wants_json() -> bool:
    return request.path.startswith("/api/") or request.is_json


def _request_error(message: str, status: int):
    if _wants_json():
        return jsonify(error=message), status
    return (
        render_template("alerts.html", alerts=list_alerts(get_db()), error=message),
        status,
    )