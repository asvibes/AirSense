import csv
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import TextIO


def _coerce_bool(raw_value: object) -> bool:
    if raw_value is None:
        return False
    if isinstance(raw_value, bool):
        return raw_value
    return str(raw_value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _parse_timestamp(value: str) -> datetime:
    text = value.strip()
    if not text:
        raise ValueError("DALTON timestamps must not be empty.")
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _read_dalton_csv(
    handle: TextIO,
    *,
    source_name: str,
    room_name: str | None,
    limit: int | None,
    valid_co2_only: bool,
) -> list[dict[str, object]]:
    reader = csv.DictReader(handle)
    if reader.fieldnames is None:
        raise ValueError(f"DALTON CSV has no header row: {source_name}")
    if reader.fieldnames and reader.fieldnames[0].startswith("\ufeff"):
        reader.fieldnames[0] = reader.fieldnames[0].lstrip("\ufeff")

    required_columns = {"ts", "CO2", "Valid_CO2"}
    missing = sorted(required_columns - set(reader.fieldnames))
    if missing:
        raise ValueError(
            f"DALTON CSV is missing required columns: {', '.join(missing)}. "
            f"Expected at least ts, CO2, and Valid_CO2."
        )

    rows: list[dict[str, object]] = []
    for row in reader:
        if not row or not row.get("ts"):
            continue
        if valid_co2_only and not _coerce_bool(row.get("Valid_CO2")):
            continue

        raw_co2 = row.get("CO2")
        if raw_co2 is None or str(raw_co2).strip() == "":
            continue
        try:
            value = float(raw_co2)
            measured_at = _parse_timestamp(row["ts"])
        except (TypeError, ValueError, OverflowError):
            continue
        if not math.isfinite(value) or value <= 0:
            continue

        rows.append(
            {
                "room": (room_name or row.get("Loc") or "DALTON room").strip()
                or "DALTON room",
                "metric": "CO2",
                "unit": "ppm",
                "value": value,
                "measured_at": measured_at.isoformat(),
            }
        )
        if limit is not None and len(rows) >= limit:
            break

    rows.sort(key=lambda item: item["measured_at"])
    return rows


def load_dalton_csv(
    csv_source: str | Path | TextIO,
    *,
    room_name: str | None = None,
    limit: int | None = None,
    valid_co2_only: bool = True,
) -> list[dict[str, object]]:
    if limit is not None and (
        isinstance(limit, bool) or not isinstance(limit, int) or limit < 1
    ):
        raise ValueError("limit must be a positive integer.")

    if hasattr(csv_source, "read"):
        return _read_dalton_csv(
            csv_source,
            source_name=getattr(csv_source, "name", "uploaded file"),
            room_name=room_name,
            limit=limit,
            valid_co2_only=valid_co2_only,
        )

    path = Path(csv_source)
    if not path.exists():
        raise FileNotFoundError(f"DALTON CSV was not found: {path}")

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return _read_dalton_csv(
            handle,
            source_name=str(path),
            room_name=room_name,
            limit=limit,
            valid_co2_only=valid_co2_only,
        )
