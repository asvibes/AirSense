import csv
import io
from datetime import datetime, timedelta, timezone

from flask import Blueprint, Response, jsonify, request
from sqlalchemy import select

from app.db import get_session
from app.models.metric import Metric
from app.models.reading import Reading
from app.models.room import Room
from app.security.sessions import require_home_role, require_user


history = Blueprint("history", __name__)


@history.get("/api/homes/<home_id>/history")
@require_user()
def readings_history(home_id: str):
    require_home_role(home_id, "owner", "member")
    try:
        room_id, metric_code, start, end, limit = _filters(home_id)
    except ValueError as error:
        return jsonify(error=str(error)), 400
    rows = _query(home_id, room_id, metric_code, start, end, limit)
    return jsonify(
        readings=[
            {
                "id": reading.id,
                "room_id": reading.room_id,
                "room": room_name,
                "metric": reading.metric_code,
                "metric_name": metric_name,
                "value": reading.value,
                "unit": unit,
                "source": reading.source,
                "measured_at": _utc(reading.measured_at).isoformat().replace("+00:00", "Z"),
            }
            for reading, room_name, metric_name, unit in rows
        ],
        range={"from": start.isoformat(), "to": end.isoformat()},
    )


@history.get("/api/homes/<home_id>/history.csv")
@require_user()
def export_history(home_id: str):
    require_home_role(home_id, "owner", "member")
    try:
        room_id, metric_code, start, end, limit = _filters(home_id)
    except ValueError as error:
        return jsonify(error=str(error)), 400
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["measured_at", "room", "metric", "value", "unit", "source"])
    for reading, room_name, metric_name, unit in _query(
        home_id, room_id, metric_code, start, end, min(limit, 10000)
    ):
        writer.writerow(
            [
                _utc(reading.measured_at).isoformat().replace("+00:00", "Z"),
                room_name,
                reading.metric_code,
                reading.value,
                unit,
                reading.source,
            ]
        )
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": 'attachment; filename="airsense-readings.csv"'},
    )


def _filters(home_id: str):
    db = get_session()
    room_id = request.args.get("room_id")
    metric_code = request.args.get("metric", "").upper() or None
    if room_id and db.scalar(
        select(Room.id).where(Room.id == room_id, Room.home_id == home_id)
    ) is None:
        raise ValueError("room_id was not found in this home.")
    if metric_code and db.get(Metric, metric_code) is None:
        raise ValueError("metric was not found.")
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
    return room_id, metric_code, start, end, limit


def _query(home_id: str, room_id: str | None, metric: str | None, start, end, limit):
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
    if metric:
        query = query.where(Reading.metric_code == metric)
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
    return parsed.astimezone(timezone.utc)


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)