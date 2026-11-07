import csv
import io
from datetime import datetime, timedelta, timezone
from pathlib import Path

from flask import (
    Blueprint,
    current_app,
    Response,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from sqlalchemy import select

from app.csv_safety import safe_csv_cell
from app.db import get_session
from app.models.home import Home
from app.models.metric import Metric
from app.models.reading import Reading
from app.models.room import Room
from app.models.sensor import Sensor
from app.ml.forecasting import MAX_FORECAST_SECONDS, load_saved_models, predict
from app.security.sessions import (
    current_user,
    list_user_homes,
    require_home_role,
    require_user,
)
from app.timestamps import format_utc, normalize_utc
from app.services.history_report import build_history_pdf


history = Blueprint("history", __name__)


@history.get("/history")
@require_user(api=False)
def history_page():
    return _history_page("history", "history")


@history.get("/analytics")
@require_user(api=False)
def analytics_page():
    return _history_page("analytics", "analytics")


def _history_page(page_mode: str, active_nav: str):
    homes = list_user_homes(current_user().id)
    if not homes:
        return redirect(url_for("auth.login_page"))
    requested_home = request.args.get("home_id") or session.get("home_id")
    selected_home = next(
        (home for home in homes if home["id"] == requested_home), homes[0]
    )
    return render_template(
        "history.html",
        homes=homes,
        active_home=selected_home,
        current_user=current_user(),
        csrf_token=_csrf_token(),
        page_mode=page_mode,
        active_nav=active_nav,
    )


@history.get("/predictions")
@require_user(api=False)
def predictions_page():
    homes = list_user_homes(current_user().id)
    if not homes:
        return redirect(url_for("auth.login_page"))
    requested_home = request.args.get("home_id") or session.get("home_id")
    selected_home = next(
        (home for home in homes if home["id"] == requested_home), homes[0]
    )
    return render_template(
        "predictions.html",
        homes=homes,
        active_home=selected_home,
        current_user=current_user(),
        csrf_token=_csrf_token(),
        active_nav="predictions",
    )


@history.get("/api/homes/<home_id>/history")
@require_user()
def readings_history(home_id: str):
    require_home_role(home_id, "owner", "member")
    try:
        room_id, sensor_id, metric_codes, start, end, limit = _filters(home_id)
    except ValueError as error:
        return jsonify(error=str(error)), 400
    rows = _query(home_id, room_id, sensor_id, metric_codes, start, end, limit)
    return jsonify(
        readings=[
            {
                "id": reading.id,
                "room_id": reading.room_id,
                "sensor_id": reading.sensor_id,
                "room": room_name,
                "metric": reading.metric_code,
                "metric_name": metric_name,
                "value": reading.value,
                "unit": unit,
                "source": reading.source,
                "measured_at": format_utc(reading.measured_at),
                "received_at": format_utc(reading.received_at),
            }
            for reading, room_name, metric_name, unit in rows
        ],
        range={"from": format_utc(start), "to": format_utc(end)},
    )


@history.get("/api/homes/<home_id>/history/options")
@require_user()
def history_options(home_id: str):
    require_home_role(home_id, "owner", "member")
    try:
        room_id = _validated_room(home_id, request.args.get("room_id"))
        sensor_id = _validated_sensor(home_id, room_id, request.args.get("sensor_id"))
    except ValueError as error:
        return jsonify(error=str(error)), 400

    query = (
        select(Metric.code, Metric.name, Metric.unit)
        .join(Reading, Reading.metric_code == Metric.code)
        .where(Reading.home_id == home_id)
        .distinct()
        .order_by(Metric.name, Metric.code)
    )
    if room_id:
        query = query.where(Reading.room_id == room_id)
    if sensor_id:
        query = query.where(Reading.sensor_id == sensor_id)
    metrics = get_session().execute(query).all()
    return jsonify(
        metrics=[
            {"code": code, "name": name, "unit": unit}
            for code, name, unit in metrics
        ]
    )


@history.get("/api/homes/<home_id>/predictions")
@require_user()
def prediction_data(home_id: str):
    require_home_role(home_id, "owner", "member")
    try:
        room_id = _validated_room(home_id, request.args.get("room_id"))
        sensor_id = _validated_sensor(home_id, room_id, request.args.get("sensor_id"))
    except ValueError as error:
        return jsonify(error=str(error)), 400

    model_path = Path(current_app.instance_path) / "forecast_models.json"
    saved_models = load_saved_models(model_path)
    candidates = [
        item
        for item in saved_models
        if item.get("home_id") == home_id
        and (room_id is None or item.get("room_id") == room_id)
        and (sensor_id is None or item.get("sensor_id") == sensor_id)
    ]
    metric_code = request.args.get("metric")
    if not metric_code:
        return jsonify(
            models=[
                {
                    "room_id": item.get("room_id"),
                    "sensor_id": item.get("sensor_id"),
                    "metric": item.get("metric"),
                    "available": item.get("available", False),
                    "reason": item.get("reason"),
                    "sample_count": item.get("sample_count", 0),
                    "tested_horizon_seconds": item.get("tested_horizon_seconds", 0),
                    "metrics": item.get("metrics"),
                }
                for item in candidates
            ]
        )

    now = datetime.now(timezone.utc)
    actual = _recent_real_readings(home_id, room_id, sensor_id, metric_code, now)
    metric_candidates = [
        item for item in candidates if item.get("metric") == metric_code
    ]
    if len(metric_candidates) > 1 and (room_id is None or sensor_id is None):
        return jsonify(
            available=False,
            reason="More than one trained series matches. Select a room and sensor to identify the exact stored series.",
            matches=[
                {"room_id": item.get("room_id"), "sensor_id": item.get("sensor_id")}
                for item in metric_candidates
            ],
            actual=actual,
            forecast=[],
        )
    candidate = metric_candidates[0] if metric_candidates else None
    if not candidate:
        return jsonify(
            available=False,
            reason="No trained forecasting result exists for this household, room, sensor, and parameter.",
            actual=actual,
            forecast=[],
        )
    if not candidate.get("available") or not candidate.get("model"):
        return jsonify(
            available=False,
            reason=candidate.get("reason", "This series does not have a validated forecasting model."),
            sample_count=candidate.get("sample_count", 0),
            metrics=candidate.get("metrics"),
            actual=actual,
            forecast=[],
        )

    try:
        horizon_minutes = int(request.args.get("horizon_minutes", "60"))
    except ValueError:
        return jsonify(error="horizon_minutes must be an integer."), 400
    if horizon_minutes < 1 or horizon_minutes > MAX_FORECAST_SECONDS // 60:
        return jsonify(error="horizon_minutes must be between 1 and 1440."), 400
    horizon_seconds = horizon_minutes * 60
    tested_horizon = float(candidate["tested_horizon_seconds"])
    if horizon_seconds > tested_horizon:
        return jsonify(
            available=False,
            reason=(
                f"The selected {horizon_minutes}-minute horizon exceeds the "
                f"{int(tested_horizon)}-second forward test interval."
            ),
            tested_horizon_seconds=tested_horizon,
            metrics=candidate.get("metrics"),
            actual=actual,
            forecast=[],
        )

    if not actual:
        return jsonify(
            available=False,
            reason="No recent real sensor readings are available for this trained series.",
            sample_count=candidate.get("sample_count", 0),
            metrics=candidate.get("metrics"),
            actual=[],
            forecast=[],
        )
    return jsonify(
        available=True,
        metric=metric_code,
        room_id=candidate.get("room_id"),
        sensor_id=candidate.get("sensor_id"),
        sample_count=candidate.get("sample_count"),
        tested_horizon_seconds=tested_horizon,
        horizon_seconds=horizon_seconds,
        metrics=candidate.get("metrics"),
        actual=actual,
        forecast=predict(candidate["model"], now, horizon_seconds),
    )


def _recent_real_readings(
    home_id: str,
    room_id: str | None,
    sensor_id: str | None,
    metric_code: str,
    now: datetime,
) -> list[dict]:
    rows = _query(
        home_id,
        room_id,
        sensor_id,
        [metric_code],
        now - timedelta(days=7),
        now,
        1000,
    )
    return [
        {
            "measured_at": format_utc(reading.measured_at),
            "value": reading.value,
            "unit": unit,
            "source": reading.source,
        }
        for reading, _room, _metric, unit in rows
        if reading.source in {"device", "dataset"}
    ]


@history.get("/api/homes/<home_id>/history.csv")
@require_user()
def export_history(home_id: str):
    require_home_role(home_id, "owner", "member")
    try:
        room_id, sensor_id, metric_codes, start, end, limit = _filters(home_id)
    except ValueError as error:
        return jsonify(error=str(error)), 400
    output = io.StringIO(newline="")
    writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL, escapechar="\\")
    writer.writerow(
        ["measured_at", "received_at", "room", "metric", "value", "unit", "source"]
    )
    for reading, room_name, metric_name, unit in _query(
        home_id, room_id, sensor_id, metric_codes, start, end, min(limit, 10000)
    ):
        writer.writerow(
            safe_csv_cell(value)
            for value in (
                format_utc(reading.measured_at),
                format_utc(reading.received_at) or "",
                room_name,
                reading.metric_code,
                reading.value,
                unit,
                reading.source,
            )
        )
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": 'attachment; filename="airsense-readings.csv"'},
    )


@history.get("/api/homes/<home_id>/history.pdf")
@require_user()
def export_history_pdf(home_id: str):
    require_home_role(home_id, "owner", "member")
    try:
        room_id, sensor_id, metric_codes, start, end, limit = _filters(home_id)
    except ValueError as error:
        return jsonify(error=str(error)), 400

    db = get_session()
    home = db.get(Home, home_id)
    query = (
        select(
            Reading,
            Room.name,
            Metric.name,
            Metric.unit,
            Sensor.name,
            Sensor.reporting_interval_seconds,
        )
        .join(Room, Reading.room_id == Room.id)
        .join(Metric, Reading.metric_code == Metric.code)
        .outerjoin(Sensor, Reading.sensor_id == Sensor.id)
        .where(
            Reading.home_id == home_id,
            Reading.measured_at >= start,
            Reading.measured_at <= end,
        )
    )
    if room_id:
        query = query.where(Reading.room_id == room_id)
    if sensor_id:
        query = query.where(Reading.sensor_id == sensor_id)
    if metric_codes:
        query = query.where(Reading.metric_code.in_(metric_codes))
    rows = db.execute(
        query.order_by(Reading.measured_at.asc(), Reading.id.asc()).limit(limit)
    ).all()
    room = db.get(Room, room_id) if room_id else None
    sensor = db.get(Sensor, sensor_id) if sensor_id else None
    pdf = build_history_pdf(
        home_name=home.name,
        room_name=room.name if room else "All rooms",
        sensor_name=sensor.name if sensor else "All sensors",
        start=start,
        end=end,
        metrics=metric_codes,
        rows=rows,
        result_limit_reached=len(rows) == limit,
    )
    return Response(
        pdf,
        mimetype="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="airsense-history-report.pdf"'},
    )


def _filters(home_id: str):
    room_id = _validated_room(home_id, request.args.get("room_id"))
    sensor_id = _validated_sensor(home_id, room_id, request.args.get("sensor_id"))
    metric_values = request.args.getlist("metric")
    metric_codes = []
    for value in metric_values:
        code = value.strip()
        if not code:
            continue
        if get_session().get(Metric, code) is None and get_session().get(
            Metric, code.upper()
        ) is not None:
            code = code.upper()
        if get_session().get(Metric, code) is None:
            raise ValueError("A selected metric was not found.")
        if code not in metric_codes:
            metric_codes.append(code)
    end = _date(request.args.get("to")) if request.args.get("to") else datetime.now(timezone.utc)
    start = _date(request.args.get("from")) if request.args.get("from") else end - timedelta(days=30)
    if start >= end:
        raise ValueError("The from date must be earlier than the to date.")
    try:
        limit = int(request.args.get("limit", 500))
    except ValueError as error:
        raise ValueError("limit must be a whole number.") from error
    if not 1 <= limit <= 10000:
        raise ValueError("limit must be between 1 and 10000.")
    return room_id, sensor_id, metric_codes or None, start, end, limit


def _validated_room(home_id: str, room_id: str | None):
    if room_id and get_session().scalar(
        select(Room.id).where(Room.id == room_id, Room.home_id == home_id)
    ) is None:
        raise ValueError("room_id was not found in this home.")
    return room_id


def _validated_sensor(home_id: str, room_id: str | None, sensor_id: str | None):
    if sensor_id:
        sensor = get_session().scalar(
            select(Sensor).where(Sensor.id == sensor_id, Sensor.home_id == home_id)
        )
        if sensor is None or (room_id and sensor.room_id != room_id):
            raise ValueError("sensor_id was not found for the selected household and room.")
    return sensor_id


def _query(
    home_id: str,
    room_id: str | None,
    sensor_id: str | None,
    metrics: list[str] | None,
    start,
    end,
    limit,
):
    query = (
        select(Reading, Room.name, Metric.name, Metric.unit)
        .join(Room, Reading.room_id == Room.id)
        .join(Metric, Reading.metric_code == Metric.code)
        .where(
            Reading.home_id == home_id,
            Reading.measured_at >= start,
            Reading.measured_at <= end,
        )
    )
    if room_id:
        query = query.where(Reading.room_id == room_id)
    if sensor_id:
        query = query.where(Reading.sensor_id == sensor_id)
    if metrics:
        query = query.where(Reading.metric_code.in_(metrics))
    return get_session().execute(
        query.order_by(Reading.measured_at.asc(), Reading.id.asc()).limit(limit)
    ).all()


def _date(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("Dates must use ISO-8601 timestamps.") from error
    if parsed.tzinfo is None:
        raise ValueError("Date filters must include a timezone.")
    return normalize_utc(parsed)


def _csrf_token():
    from app.security.sessions import csrf_token

    return csrf_token()