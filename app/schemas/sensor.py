from app.services.provisioning import ProvisioningError


def validate_sensor_input(payload: object) -> tuple[str, str, int]:
    if not isinstance(payload, dict):
        raise ProvisioningError("Request body must be a JSON object.")
    name = payload.get("name")
    room_id = payload.get("room_id")
    interval = payload.get("reporting_interval_seconds", 300)
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 120:
        raise ProvisioningError("name must contain 1 to 120 characters.")
    if not isinstance(room_id, str) or not room_id:
        raise ProvisioningError("room_id is required.")
    if isinstance(interval, bool) or not isinstance(interval, int):
        raise ProvisioningError("reporting_interval_seconds must be a whole number.")
    if not 30 <= interval <= 86400:
        raise ProvisioningError("reporting_interval_seconds must be between 30 and 86400.")
    return name.strip(), room_id, interval