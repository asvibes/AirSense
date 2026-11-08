from datetime import datetime, timezone
from time import perf_counter

from sqlalchemy import insert
from sqlalchemy.orm import Session

from app.models.home import Home
from app.models.metric import Metric
from app.models.reading import Reading
from app.models.room import Room
from app.repositories.alerts import prepare_replay_scope, process_reading
from app.services.audit import record_event
from app.services.ingestion.validate import validate_reading
from app.timestamps import normalize_utc


def ingest_reading(
    session: Session,
    *,
    home_id: str,
    home_name: str,
    payload: object,
    source: str,
    defaults: dict,
    max_future_seconds: int,
    actor_user_id: str | None,
    sensor_id: str | None = None,
    max_age_seconds: int | None = None,
    commit: bool = True,
    phase_timings: dict[str, float] | None = None,
    scope_cache: dict[str, tuple[Home, Room, Metric]] | None = None,
    manage_transaction: bool = True,
    defer_flush: bool = False,
    record_audit: bool = True,
) -> dict:
    received_at = datetime.now(timezone.utc)
    reading = validate_reading(payload)
    if max_age_seconds is not None:
        age_seconds = (
            datetime.now(timezone.utc) - reading["measured_at"]
        ).total_seconds()
        if age_seconds > max_age_seconds:
            raise ValueError("Reading timestamp is too old for live ingestion.")
    insertion_started = perf_counter()
    result = process_reading(
        session,
        home_id=home_id,
        home_name=home_name,
        room_name=reading["room"],
        metric_code=reading["metric"],
        metric_name=reading["metric_name"],
        unit=reading["unit"],
        value=reading["value"],
        source=source,
        measured_at=reading["measured_at"],
        received_at=received_at,
        defaults=defaults,
        max_future_seconds=max_future_seconds,
        sensor_id=sensor_id,
        actor_user_id=actor_user_id,
        phase_timings=phase_timings,
        scope_cache=scope_cache,
        manage_transaction=manage_transaction,
        defer_flush=defer_flush,
    )
    if phase_timings is not None:
        phase_timings["reading_insertion_ms"] = phase_timings.get(
            "reading_insertion_ms", 0.0
        ) + (perf_counter() - insertion_started) * 1000
    if sensor_id:
        from app.models.sensor import Sensor

        sensor = session.get(Sensor, sensor_id)
        if sensor:
            sensor.last_seen_at = datetime.now(timezone.utc)
    if record_audit:
        audit_started = perf_counter()
        record_event(
            session,
            home_id=home_id,
            actor_user_id=actor_user_id,
            event_type="reading.ingested",
            entity_type="reading",
            entity_id=str(result["reading_id"]),
            details={"source": source, "metric": reading["metric"]},
        )
        if phase_timings is not None:
            phase_timings["audit_insertion_ms"] = phase_timings.get(
                "audit_insertion_ms", 0.0
            ) + (perf_counter() - audit_started) * 1000
    if commit:
        session.commit()
    return result


def ingest_dataset_batch(
    session: Session,
    *,
    home_id: str,
    payloads: list[dict],
    actor_user_id: str | None,
    max_future_seconds: int,
    defaults: dict,
    room_id: str | None = None,
) -> list[dict]:
    """Validate and persist replay readings with one scope prefetch and flush.

    Scope lookups are performed once for the batch. Each reading still passes
    through the existing validation and dataset ingestion path; reading and
    audit writes remain within the caller's transaction/savepoint.
    """
    if not payloads:
        return []

    normalized = [validate_reading(payload) for payload in payloads]
    room_names = {item["room"].casefold() for item in normalized}
    if len(room_names) != 1:
        raise ValueError("A replay batch must target one room.")
    room_name = normalized[0]["room"]

    metric_specs: dict[str, tuple[str, str | None]] = {}
    for item in normalized:
        code = item["metric"].upper()
        spec = (item["unit"], item["metric_name"])
        prior = metric_specs.get(code)
        if prior is not None and prior[0] != spec[0]:
            raise ValueError(
                f"Metric {code} uses inconsistent units in this replay batch."
            )
        metric_specs.setdefault(code, spec)

    scope_cache = prepare_replay_scope(
        session,
        home_id=home_id,
        home_name="",
        room_name=room_name,
        metric_specs=metric_specs,
    )
    if room_id is not None and any(
        scope[1].id != room_id for scope in scope_cache.values()
    ):
        raise ValueError("Replay room does not match the selected room.")

    results = []
    for payload in payloads:
        result = ingest_reading(
            session,
            home_id=home_id,
            home_name="",
            payload=payload,
            source="dataset",
            defaults=defaults,
            max_future_seconds=max_future_seconds,
            actor_user_id=actor_user_id,
            commit=False,
            scope_cache=scope_cache,
            manage_transaction=False,
            defer_flush=True,
            record_audit=False,
        )
        results.append(result)

    staged_readings = [result.pop("_reading") for result in results]
    mappings = [
        {
            "home_id": reading.home_id,
            "room_id": reading.room_id,
            "sensor_id": reading.sensor_id,
            "metric_code": reading.metric_code,
            "value": reading.value,
            "source": reading.source,
            "measured_at": reading.measured_at,
            "received_at": reading.received_at,
        }
        for reading in staged_readings
    ]
    for reading in staged_readings:
        session.expunge(reading)

    inserted = session.execute(
        insert(Reading).returning(
            Reading.id, Reading.metric_code, Reading.measured_at
        ),
        mappings,
    ).all()
    reading_ids = {
        (code, normalize_utc(measured_at)): reading_id
        for reading_id, code, measured_at in inserted
    }
    if len(reading_ids) != len(results):
        raise RuntimeError("Not all replay readings were inserted.")

    for result in results:
        measured_at = datetime.fromisoformat(
            result["measured_at"].replace("Z", "+00:00")
        )
        reading_id = reading_ids[
            (result["metric"], normalize_utc(measured_at))
        ]
        result["reading_id"] = reading_id
        record_event(
            session,
            home_id=home_id,
            actor_user_id=actor_user_id,
            event_type="reading.ingested",
            entity_type="reading",
            entity_id=str(reading_id),
            details={"source": "dataset", "metric": result["metric"]},
        )
    return results
