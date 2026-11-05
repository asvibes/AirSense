from flask import abort, request


def require_json_object() -> dict:
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        abort(400, description="Request body must be a valid JSON object.")
    return payload
