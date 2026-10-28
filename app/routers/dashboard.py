from flask import Blueprint, jsonify

from app.db import get_session
from app.repositories.alerts import list_alerts, list_latest_readings
from app.security.sessions import require_home_role, require_user


dashboard = Blueprint("dashboard", __name__)


@dashboard.get("/api/homes/<home_id>/dashboard")
@require_user()
def home_dashboard(home_id: str):
    require_home_role(home_id, "owner", "member")
    return jsonify(
        home_id=home_id,
        readings=list_latest_readings(get_session(), home_id),
        alerts=list_alerts(get_session(), home_id),
    )