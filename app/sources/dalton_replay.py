import csv
import math
from datetime import datetime, timezone
from pathlib import Path


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


def load_dalton_csv(
    csv_path: str | Path,
    *,
    room_name: str | None = None,
    limit: int | None = None,
    valid_co2_only: bool = True,
) -> list[dict[str, object]]:
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"DALTON CSV was not found: {path}")

    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"DALTON CSV has no header row: {path}")

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
            except (TypeError, ValueError):
                continue
            if not math.isfinite(value) or value < 0:
                continue

            rows.append(
                {
                    "room": (room_name or row.get("Loc") or "DALTON room").strip()
                    or "DALTON room",
                    "metric": "CO2",
                    "unit": "ppm",
                    "value": value,
                    "measured_at": _parse_timestamp(row["ts"]).isoformat(),
                }
            )
            if limit is not None and len(rows) >= limit:
                break

    return rows
