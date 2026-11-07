import csv
import math
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import TextIO

from app.parameters import (
    custom_metric,
    is_metadata_column,
    normalize_header,
    normalize_value,
    resolve_column,
)
from app.timestamps import format_utc

_VALID_VALUES = {"1", "true", "yes", "y", "on"}
_TIMESTAMP_COLUMNS = {
    "ts", "time", "timestamp", "datetime", "measuredat", "measurementtime",
    "recordedat", "date",
}


def _coerce_bool(raw_value: object) -> bool:
    if raw_value is None:
        return False
    if isinstance(raw_value, bool):
        return raw_value
    return str(raw_value).strip().lower() in _VALID_VALUES


def _parse_timestamp(value: str) -> datetime:
    text = value.strip()
    if not text:
        raise ValueError("Dataset timestamps must not be empty.")
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _numeric(value: object) -> float | None:
    if value is None or not str(value).strip():
        return None
    try:
        number = float(str(value).strip())
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def _open_csv(source: str | Path | TextIO):
    if hasattr(source, "read"):
        return source, False
    path = Path(source)
    if not path.exists():
        raise FileNotFoundError(f"Dataset file was not found: {path}")
    return path.open("r", encoding="utf-8-sig", newline=""), True


def parse_environmental_csv(
    csv_source: str | Path | TextIO,
    *,
    room_name: str | None = None,
    limit: int | None = None,
    valid_only: bool = True,
) -> dict[str, object]:
    if limit is not None and (
        isinstance(limit, bool) or not isinstance(limit, int) or limit < 1
    ):
        raise ValueError("limit must be a positive integer.")

    handle, should_close = _open_csv(csv_source)
    try:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError("Dataset CSV has no header row.")
        headers = [header.strip().lstrip("\ufeff") for header in reader.fieldnames]
        reader.fieldnames = headers

        time_columns = [header for header in headers if normalize_header(header) in _TIMESTAMP_COLUMNS]
        if not time_columns:
            raise ValueError("Dataset CSV must include a timestamp column (for example, ts or timestamp).")
        if len(time_columns) > 1:
            raise ValueError(
                f"Dataset has ambiguous timestamp columns: {', '.join(time_columns)}."
            )
        location_columns = [
            header for header in headers
            if normalize_header(header) in {"room", "location", "loc", "roomname"}
        ]
        location_column = location_columns[0] if location_columns else None

        columns: list[dict[str, object]] = []
        valid_columns: dict[str, str] = {}
        review_columns: list[dict[str, str]] = []
        unknown_columns: list[str] = []
        unknown_value_columns: set[str] = set()
        metric_columns: dict[str, list[str]] = {}

        for header in headers:
            normalized = normalize_header(header)
            if header == time_columns[0] or header == location_column:
                continue
            if normalized.startswith("valid"):
                parameter, _, _ = resolve_column(header[5:].lstrip(" _-"))
                if parameter:
                    valid_columns[parameter.code] = header
                continue
            if is_metadata_column(header):
                continue

            parameter, source_unit, base_header = resolve_column(header)
            if parameter:
                column = {
                    "header": header,
                    "code": parameter.code,
                    "name": parameter.name,
                    "unit": source_unit,
                    "parameter": parameter,
                    "custom": False,
                }
                columns.append(column)
                metric_columns.setdefault(parameter.code, []).append(header)
                continue

            custom = custom_metric(base_header, source_unit)
            if custom:
                code, unit = custom
                columns.append(
                    {
                        "header": header,
                        "code": code,
                        "name": base_header.strip().replace("_", " "),
                        "unit": unit,
                        "parameter": None,
                        "custom": True,
                    }
                )
                metric_columns.setdefault(code, []).append(header)
                continue

            unknown_columns.append(header)

        duplicate_headers = {
            code: metric_headers
            for code, metric_headers in metric_columns.items()
            if len(metric_headers) > 1
        }
        for code, metric_headers in duplicate_headers.items():
            for header in metric_headers:
                review_columns.append(
                    {
                        "column": header,
                        "reason": f"Multiple columns map to {code}; resolve the duplicate before importing.",
                    }
                )
        columns = [
            column for column in columns
            if len(metric_columns[str(column["code"])]) == 1
        ]
        supported_columns = []
        for column in columns:
            parameter = column["parameter"]
            if parameter and column["unit"] and column["unit"] not in parameter.conversions:
                review_columns.append(
                    {
                        "column": str(column["header"]),
                        "reason": f"Unit {column['unit']!r} is not supported for {parameter.name}.",
                    }
                )
            else:
                supported_columns.append(column)
        columns = supported_columns

        parsed_rows: list[dict[str, object]] = []
        assumed_units: set[str] = set()
        skipped_rows = 0
        rows_seen = 0
        for row in reader:
            if limit is not None and rows_seen >= limit:
                break
            rows_seen += 1
            raw_timestamp = row.get(time_columns[0])
            if raw_timestamp is None or not str(raw_timestamp).strip():
                skipped_rows += 1
                continue
            try:
                measured_at = format_utc(_parse_timestamp(str(raw_timestamp)))
            except (TypeError, ValueError, OverflowError):
                skipped_rows += 1
                continue

            row_readings = 0
            for column in columns:
                code = str(column["code"])
                header = str(column["header"])
                validity_column = valid_columns.get(code)
                if valid_only and validity_column:
                    if not _coerce_bool(row.get(validity_column)):
                        continue

                value = _numeric(row.get(header))
                if value is None:
                    continue
                if column["custom"]:
                    if value < 0:
                        continue
                    unit = str(column["unit"])
                    normalized_value = value
                else:
                    parameter = column["parameter"]
                    try:
                        normalized_value, unit, assumed = normalize_value(
                            value, parameter, column["unit"]
                        )
                    except ValueError:
                        continue
                    if assumed:
                        assumed_units.add(header)
                if not math.isfinite(normalized_value):
                    continue
                location = str(row.get(location_column) or "").strip() if location_column else ""
                parsed_rows.append(
                    {
                        "room": (room_name or location or "Dataset room").strip(),
                        "metric": code,
                        "metric_name": str(column["name"]),
                        "unit": unit,
                        "value": normalized_value,
                        "measured_at": measured_at,
                    }
                )
                row_readings += 1
            if row_readings == 0:
                skipped_rows += 1
            for header in unknown_columns:
                if _numeric(row.get(header)) is not None:
                    unknown_value_columns.add(header)

        for header in sorted(unknown_value_columns):
            review_columns.append(
                {
                    "column": header,
                    "reason": "Unrecognized measurement column. Add an explicit supported unit and parameter mapping before importing.",
                }
            )
        for header in sorted(assumed_units):
            review_columns.append(
                {
                    "column": header,
                    "reason": "No unit was provided; the parameter's conventional unit was assumed. Verify against the dataset documentation.",
                }
            )

        counts = Counter(
            (str(reading["metric"]), str(reading["measured_at"]))
            for reading in parsed_rows
        )
        duplicate_keys = {key for key, count in counts.items() if count > 1}
        duplicate_readings = [
            {"metric": code, "measured_at": measured_at}
            for code, measured_at in sorted(duplicate_keys)
        ]
        if duplicate_keys:
            parsed_rows = [
                reading
                for reading in parsed_rows
                if (str(reading["metric"]), str(reading["measured_at"]))
                not in duplicate_keys
            ]
            skipped_rows += sum(counts[key] for key in duplicate_keys)

        parameters: dict[str, dict[str, object]] = {}
        for reading in parsed_rows:
            code = str(reading["metric"])
            summary = parameters.setdefault(
                code,
                {
                    "code": code,
                    "name": reading["metric_name"],
                    "unit": reading["unit"],
                    "readings": 0,
                },
            )
            summary["readings"] = int(summary["readings"]) + 1
        parsed_rows.sort(key=lambda item: (str(item["measured_at"]), str(item["metric"])))
        return {
            "readings": parsed_rows,
            "parameters": list(parameters.values()),
            "review_columns": review_columns,
            "duplicate_readings": duplicate_readings,
            "rows_seen": rows_seen,
            "rows_skipped": skipped_rows,
        }
    finally:
        if should_close:
            handle.close()


def load_dalton_csv(
    csv_source: str | Path | TextIO,
    *,
    room_name: str | None = None,
    limit: int | None = None,
    valid_co2_only: bool = True,
) -> list[dict[str, object]]:
    handle, should_close = _open_csv(csv_source)
    try:
        reader = csv.DictReader(handle)
        headers = {
            header.strip().lstrip("\ufeff")
            for header in (reader.fieldnames or [])
        }
        if not {"ts", "CO2"}.issubset(headers):
            raise ValueError("DALTON CSV must include ts and CO2 columns.")
        if valid_co2_only and "Valid_CO2" not in headers:
            raise ValueError("DALTON CSV must include Valid_CO2 when validity filtering is enabled.")
        handle.seek(0)
        result = parse_environmental_csv(
            handle,
            room_name=room_name,
            limit=limit,
            valid_only=valid_co2_only,
        )
        return [
            {
                key: reading[key]
                for key in ("room", "metric", "unit", "value", "measured_at")
            }
            for reading in result["readings"]
            if reading["metric"] == "CO2" and float(reading["value"]) > 0
        ]
    finally:
        if should_close:
            handle.close()
