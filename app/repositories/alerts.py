import math
import re
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.alert import Alert, AlertLevel, AlertStatus
from app.models.home import Home
from app.models.metric import Metric
from app.models.reading import Reading
from app.models.room import Room
from app.models.threshold import ThresholdPolicy
from app.services.alerts.all_clear import (
    InvalidAlertTransition,
    acknowledge_status,
    all_clear_progress,
)
from app.services.alerts.rules import evaluate_reading
from app.services.alerts.wording import build_alert_detail


class AlertNotFound(LookupError):
    pass


class InvalidReading(ValueError):
    pass


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _room_id(home_id: str, room_name: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"airsense:{home_id}:{room_name.casefold()}"))


def _ensure_scope(
    session: Session,
    home_id: str,
    home_name: str,
    room_name: str,
    metric_code: str,
    unit: str,
) -> tuple[Home, Room, Metric]:
    home = session.get(Home, home_id)
    if home is None:
        home = Home(id=home_id, name=home_name)
        session.add(home)
        session.flush()

    room = session.scalar(
        select(Room).where(
            Room.home_id == home_id,
            func.lower(Room.name) == room_name.casefold(),
        )
    )
    if room is None:
        room = Room(id=_room_id(home_id, room_name), home_id=home_id, name=room_name)
        session.add(room)
        session.flush()

    metric = session.get(Metric, metric_code)
    if metric is None:
        metric = Metric(code=metric_code, name=metric_code, unit=unit)
        session.add(metric)
        session.flush()
    elif metric.unit != unit:
        raise InvalidReading(
            f"Metric {metric_code} uses {metric.unit}, not the submitted {unit}."
        )

    return home, room, metric


def _policy(
    session: Session,
    home_id: str,
    room_id: str,
    metric_code: str,
    defaults: dict,
) -> ThresholdPolicy:
    policy = session.scalar(
        select(ThresholdPolicy)
        .where(
            ThresholdPolicy.home_id == home_id,
            ThresholdPolicy.room_id == room_id,
            ThresholdPolicy.metric_code == metric_code,
        )
        .with_for_update()
    )
    if policy is None:
        policy = ThresholdPolicy(
            home_id=home_id,
            room_id=room_id,
            metric_code=metric_code,
            **defaults,
        )
        session.add(policy)
        session.flush()
    return policy


def _level_value(level: str, value: float, rapid_rise: float | None) -> float:
    return rapid_rise or 0.0 if level == AlertLevel.RAPID_RISE.value else value


def _open_alert(
    session: Session,
    home_id: str,
    room: Room,
    metric: Metric,
    policy: ThresholdPolicy,
    level: str,
    value: float,
    rapid_rise: float | None,
    measured_at: datetime,
) -> Alert:
    threshold = {
        AlertLevel.HIGH.value: policy.high_threshold,
        AlertLevel.ELEVATED.value: policy.elevated_threshold,
        AlertLevel.RAPID_RISE.value: policy.rapid_rise_per_minute,
    }[level]
    trigger_value = _level_value(level, value, rapid_rise)
    alert = Alert(
        home_id=home_id,
        room_id=room.id,
        metric_code=metric.code,
        level=level,
        status=AlertStatus.ACTIVE.value,
        trigger_value=trigger_value,
        threshold_value=threshold,
        latest_value=trigger_value,
        threshold_unit=f"{metric.unit}/min" if level == AlertLevel.RAPID_RISE.value else metric.unit,
        clear_duration_seconds=policy.all_clear_duration_seconds,
        created_at=measured_at,
        detail=build_alert_detail(
            level=level,
            metric_name=metric.name,
            value=trigger_value,
            threshold=threshold,
            unit=(
                f"{metric.unit}/min"
                if level == AlertLevel.RAPID_RISE.value
                else metric.unit
            ),
        ),
    )
    session.add(alert)
    session.flush()
    return alert


def process_reading(
    session: Session,
    *,
    home_id: str,
    home_name: str,
    room_name: str,
    metric_code: str,
    unit: str,
    value: float,
    source: str,
    measured_at: datetime,
    defaults: dict,
    max_future_seconds: int = 60,
    sensor_id: str | None = None,
) -> dict:
    if not math.isfinite(value) or value < 0:
        raise InvalidReading("Reading value must be a finite non-negative number.")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", home_id):
        raise InvalidReading("home_id must contain 1 to 64 letters, numbers, underscores, or hyphens.")
    if not room_name.strip() or len(room_name) > 100:
        raise InvalidReading("room must contain 1 to 100 characters.")
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,31}", metric_code):
        raise InvalidReading("metric must be a valid metric code.")
    if not re.fullmatch(r"[A-Za-z0-9/%._-]{1,24}", unit):
        raise InvalidReading("unit must contain 1 to 24 valid characters.")
    if source not in ("dataset", "simulated", "device"):
        raise InvalidReading("source must be dataset, simulated, or device.")
    if not all(
        isinstance(defaults.get(key), (int, float))
        and math.isfinite(float(defaults[key]))
        for key in ("high_threshold", "elevated_threshold", "rapid_rise_per_minute")
    ):
        raise InvalidReading("Alert thresholds must be finite numbers.")
    if (
        defaults["high_threshold"] <= defaults["elevated_threshold"]
        or defaults["high_threshold"] <= 0
        or defaults["elevated_threshold"] < 0
        or defaults["rapid_rise_per_minute"] <= 0
    ):
        raise InvalidReading("Alert thresholds must be valid positive values.")
    if any(
        not isinstance(defaults.get(key), int) or defaults[key] <= 0
        for key in (
            "elevated_duration_seconds",
            "all_clear_duration_seconds",
            "max_reading_gap_seconds",
        )
    ):
        raise InvalidReading("Alert durations must be positive whole seconds.")

    measured_at = _utc(measured_at)
    now = datetime.now(timezone.utc)
    if measured_at > now + timedelta(seconds=max_future_seconds):
        raise InvalidReading("Reading timestamp cannot be in the future.")

    try:
        transaction = session.begin_nested() if session.in_transaction() else session.begin()
        with transaction:
            home, room, metric = _ensure_scope(
                session, home_id, home_name, room_name.strip(), metric_code.upper(), unit
            )
            policy = _policy(
                session, home.id, room.id, metric.code, defaults
            )
            previous = session.scalar(
                select(Reading)
                .where(
                    Reading.home_id == home.id,
                    Reading.room_id == room.id,
                    Reading.metric_code == metric.code,
                )
                .order_by(Reading.measured_at.desc(), Reading.id.desc())
                .limit(1)
            )
            if previous is not None and measured_at <= _utc(previous.measured_at):
                raise InvalidReading("Reading must be newer than the last reading for this room and metric.")

            elapsed = (
                (measured_at - _utc(previous.measured_at)).total_seconds()
                if previous is not None
                else None
            )
            if elapsed is not None and elapsed > policy.max_reading_gap_seconds:
                policy.elevated_since = None

            if value >= policy.elevated_threshold and value < policy.high_threshold:
                if policy.elevated_since is None:
                    policy.elevated_since = measured_at
            else:
                policy.elevated_since = None

            timely_previous = (
                previous is not None
                and elapsed is not None
                and elapsed <= policy.max_reading_gap_seconds
            )
            evaluation = evaluate_reading(
                value,
                previous.value if timely_previous else None,
                elapsed if timely_previous else None,
                policy,
                elevated_sustained=(
                    policy.elevated_since is not None
                    and (measured_at - _utc(policy.elevated_since)).total_seconds()
                    >= policy.elevated_duration_seconds
                ),
            )
            if (
                policy.elevated_since is not None
                and (measured_at - _utc(policy.elevated_since)).total_seconds()
                >= policy.elevated_duration_seconds
                and value < policy.high_threshold
            ):
                evaluation_levels = set(evaluation.triggered_levels)
                evaluation_levels.add(AlertLevel.ELEVATED.value)
            else:
                evaluation_levels = set(evaluation.triggered_levels)

            reading = Reading(
                home_id=home.id,
                room_id=room.id,
                sensor_id=sensor_id,
                metric_code=metric.code,
                value=value,
                source=source,
                measured_at=measured_at,
            )
            session.add(reading)

            open_alerts = list(
                session.scalars(
                    select(Alert)
                    .where(
                        Alert.home_id == home.id,
                        Alert.room_id == room.id,
                        Alert.metric_code == metric.code,
                        Alert.status.in_(
                            (AlertStatus.ACTIVE.value, AlertStatus.ACKNOWLEDGED.value)
                        ),
                    )
                    .with_for_update()
                )
            )
            created = []
            cleared = []
            open_by_level = {alert.level: alert for alert in open_alerts}

            for level in sorted(evaluation_levels):
                alert = open_by_level.get(level)
                if alert is None:
                    alert = _open_alert(
                        session,
                        home.id,
                        room,
                        metric,
                        policy,
                        level,
                        value,
                        evaluation.rapid_rise_per_minute,
                        measured_at,
                    )
                    open_by_level[level] = alert
                    created.append(alert)

            for alert in open_alerts:
                applicable_value = _level_value(
                    alert.level, value, evaluation.rapid_rise_per_minute
                )
                alert.latest_value = applicable_value
                prior_reading_at = _utc(previous.measured_at) if previous else None
                below_since, all_clear = all_clear_progress(
                    value=applicable_value,
                    threshold=alert.threshold_value,
                    below_since=(
                        _utc(alert.below_threshold_since)
                        if alert.below_threshold_since
                        else None
                    ),
                    measured_at=measured_at,
                    previous_reading_at=prior_reading_at,
                    max_reading_gap_seconds=policy.max_reading_gap_seconds,
                    clear_duration_seconds=alert.clear_duration_seconds,
                )
                alert.below_threshold_since = below_since
                if all_clear:
                    alert.status = AlertStatus.ALL_CLEAR.value
                    alert.all_clear_at = measured_at
                    cleared.append(alert)

            session.flush()

        return {
                "reading_id": reading.id,
                "home_id": home.id,
                "room": room.name,
                "metric": metric.code,
                "value": value,
                "unit": metric.unit,
                "source": source,
                "measured_at": measured_at.isoformat().replace("+00:00", "Z"),
                "rapid_rise_per_minute": evaluation.rapid_rise_per_minute,
                "created": [alert.to_dict(room.name, metric.name) for alert in created],
                "cleared": [alert.to_dict(room.name, metric.name) for alert in cleared],
                "alerts": [
                    alert.to_dict(room.name, metric.name)
                    for alert in open_by_level.values()
                ],
        }
    except IntegrityError:
        session.rollback()
        raise


def configure_policy(
    session: Session,
    *,
    home_id: str,
    home_name: str,
    room_name: str,
    metric_code: str,
    unit: str,
    values: dict,
) -> dict:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", home_id):
        raise InvalidReading("home_id must contain 1 to 64 letters, numbers, underscores, or hyphens.")
    if not room_name.strip() or len(room_name) > 100:
        raise InvalidReading("room must contain 1 to 100 characters.")
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,31}", metric_code):
        raise InvalidReading("metric must be a valid metric code.")
    if not re.fullmatch(r"[A-Za-z0-9/%._-]{1,24}", unit):
        raise InvalidReading("unit must contain 1 to 24 valid characters.")
    if not all(
        math.isfinite(value)
        for value in (
            values["high_threshold"],
            values["elevated_threshold"],
            values["rapid_rise_per_minute"],
        )
    ):
        raise InvalidReading("Alert thresholds must be finite numbers.")
    if values["elevated_threshold"] >= values["high_threshold"]:
        raise InvalidReading("The high threshold must be greater than the elevated threshold.")
    if not all(
        isinstance(values[name], int) and not isinstance(values[name], bool) and values[name] > 0
        for name in (
            "elevated_duration_seconds",
            "all_clear_duration_seconds",
            "max_reading_gap_seconds",
        )
    ):
        raise InvalidReading("Alert durations must be positive whole seconds.")
    if values["high_threshold"] <= 0 or values["elevated_threshold"] < 0:
        raise InvalidReading("Thresholds must be non-negative and the high threshold positive.")
    if values["rapid_rise_per_minute"] <= 0:
        raise InvalidReading("rapid_rise_per_minute must be positive.")

    transaction = session.begin_nested() if session.in_transaction() else session.begin()
    with transaction:
        home, room, metric = _ensure_scope(
            session, home_id, home_name, room_name.strip(), metric_code.upper(), unit
        )
        policy = _policy(
            session, home.id, room.id, metric.code, values
        )
        for name, value in values.items():
            setattr(policy, name, value)
        session.flush()
        return {
            "home_id": home.id,
            "room": room.name,
            "metric": metric.code,
            **values,
        }


def list_alerts(session: Session, home_id: str | None = None) -> list[dict]:
    query = (
        select(Alert, Room.name, Metric.name)
        .join(Room, Alert.room_id == Room.id)
        .join(Metric, Alert.metric_code == Metric.code)
        .order_by(Alert.created_at.desc(), Alert.id.desc())
    )
    if home_id:
        query = query.where(Alert.home_id == home_id)
    return [
        alert.to_dict(room_name, metric_name)
        for alert, room_name, metric_name in session.execute(query)
    ]


def list_latest_readings(session: Session, home_id: str) -> list[dict]:
    ranked_readings = (
        select(
            Reading.id.label("reading_id"),
            func.row_number()
            .over(
                partition_by=(Reading.room_id, Reading.metric_code),
                order_by=(Reading.measured_at.desc(), Reading.id.desc()),
            )
            .label("position"),
        )
        .where(Reading.home_id == home_id)
        .subquery()
    )
    rows = session.execute(
        select(
            Reading,
            Room.name,
            Metric.name,
            Metric.unit,
            ranked_readings.c.position,
        )
        .join(ranked_readings, ranked_readings.c.reading_id == Reading.id)
        .join(Room, Reading.room_id == Room.id)
        .join(Metric, Reading.metric_code == Metric.code)
        .where(ranked_readings.c.position <= 2)
        .order_by(Room.name, Reading.metric_code, ranked_readings.c.position)
    )

    latest_by_scope: dict[tuple[str, str], dict] = {}
    for reading, room_name, metric_name, unit, position in rows:
        scope = (room_name, reading.metric_code)
        latest = latest_by_scope.get(scope)
        if position == 1:
            latest = {
                "room": room_name,
                "metric": reading.metric_code,
                "metric_name": metric_name,
                "value": reading.value,
                "unit": unit,
                "source": reading.source,
                "measured_at": _utc(reading.measured_at)
                .isoformat()
                .replace("+00:00", "Z"),
                "previous_value": None,
                "trend": "unavailable",
                "change": None,
            }
            latest_by_scope[scope] = latest
        elif latest is not None:
            latest["previous_value"] = reading.value
            latest["change"] = latest["value"] - reading.value
            latest["trend"] = (
                "rising"
                if latest["value"] > reading.value
                else "falling"
                if latest["value"] < reading.value
                else "steady"
            )

    return list(latest_by_scope.values())


def acknowledge_alert(
    session: Session, alert_id: int, acknowledged_by: str
) -> dict:
    if not acknowledged_by.strip() or len(acknowledged_by.strip()) > 120:
        raise ValueError("acknowledged_by must contain 1 to 120 characters.")

    transaction = session.begin_nested() if session.in_transaction() else session.begin()
    with transaction:
        alert = session.scalar(
            select(Alert).where(Alert.id == alert_id).with_for_update()
        )
        if alert is None:
            raise AlertNotFound(f"Alert {alert_id} was not found.")
        alert.status = acknowledge_status(alert.status)
        if alert.acknowledged_at is None:
            alert.acknowledged_by = acknowledged_by.strip()
            alert.acknowledged_at = datetime.now(timezone.utc)
        room = session.get(Room, alert.room_id)
        metric = session.get(Metric, alert.metric_code)
        session.flush()
        return alert.to_dict(room.name if room else None, metric.name if metric else None)
