from flask import Blueprint, jsonify, request

from app.db import get_session
from app.security.sessions import require_home_role, require_user
from app.services.audit import list_events


audit = Blueprint("audit", __name__)


@audit.get("/api/homes/<home_id>/activity")
@require_user()
def get_activity(home_id: str):
    require_home_role(home_id, "owner")
    try:
        limit = int(request.args.get("limit", 100))
    except ValueError:
        return jsonify(error="limit must be a whole number."), 400
    if not 1 <= limit <= 500:
        return jsonify(error="limit must be between 1 and 500."), 400
    return jsonify(events=list_events(get_session(), home_id, limit=limit))