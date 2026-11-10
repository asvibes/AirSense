from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.db import get_session
from app.models.audit import AuditLog
from app.models.reading import Reading
from app.sources.airgradient import (
    AirGradientPayloadError,
    normalize_airgradient_payload,
)


def test_normalize_airgradient_payload(room):
    measured_at = datetime.now(timezone.utc).isoformat()
    reading = normalize_airgradient_payload(
        {"rco2": 612, "timestamp": measured_at, "wifi": 70},
        room_name=room["name"],
    )
    assert reading == {
        "room": room["name"],
        "metric": "CO2",
        "unit": "ppm",
        "value": 612,
        "measured_at": measured_at,
    }


def test_normalize_airgradient_epoch_milliseconds(room):
    reading = normalize_airgradient_payload(
        {"rco2": 600, "ts": 1_798_742_400_000},
        room_name=room["name"],
    )
    assert reading["measured_at"].endswith("+00:00")


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {"rco2": 600, "room": "Another room"},
        {"rco2": 600, "timestamp": True},
    ],
)
def test_normalize_airgradient_rejects_invalid_payloads(room, payload):
    with pytest.raises(AirGradientPayloadError):
        normalize_airgradient_payload(payload, room_name=room["name"])


def test_airgradient_push_reuses_device_auth_and_ingestion(owner, room, app):
    provisioned = owner.client.post(
        f"/api/homes/{owner.home_id}/sensors",
        json={"name": "AirGradient ONE", "room_id": room["id"]},
        headers={"X-CSRF-Token": owner.csrf_token},
    )
    assert provisioned.status_code == 201, provisioned.get_json()
    sensor_id = provisioned.get_json()["sensor"]["id"]
    device_key = provisioned.get_json()["device_key"]
    measured_at = datetime.now(timezone.utc).isoformat()

    response = owner.client.post(
        f"/api/sensors/{sensor_id}/readings",
        json={"rco2": 640, "timestamp": measured_at, "wifi": 70},
        headers={"X-Device-Key": device_key},
    )
    assert response.status_code == 201, response.get_json()
    with app.app_context():
        reading = get_session().scalar(
            select(Reading).where(Reading.sensor_id == sensor_id)
        )
        assert reading is not None
        assert reading.metric_code == "CO2"
        assert reading.value == 640
        assert reading.source == "device"

    rejected = owner.client.post(
        f"/api/sensors/{sensor_id}/readings",
        json={"rco2": "not-a-number"},
        headers={"X-Device-Key": device_key},
    )
    assert rejected.status_code == 400
    with app.app_context():
        event = get_session().scalar(
            select(AuditLog).where(AuditLog.event_type == "reading.rejected")
        )
        assert event is not None


def test_airgradient_push_still_requires_device_key(owner, room):
    provisioned = owner.client.post(
        f"/api/homes/{owner.home_id}/sensors",
        json={"name": "AirGradient ONE", "room_id": room["id"]},
        headers={"X-CSRF-Token": owner.csrf_token},
    )
    sensor_id = provisioned.get_json()["sensor"]["id"]
    response = owner.client.post(
        f"/api/sensors/{sensor_id}/readings",
        json={"rco2": 500},
    )
    assert response.status_code == 401
