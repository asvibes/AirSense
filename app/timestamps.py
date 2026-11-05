from datetime import datetime, timezone


def normalize_utc(value: datetime) -> datetime:
    if value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def format_utc(value: datetime | None) -> str | None:
    if value is None:
        return None
    return normalize_utc(value).isoformat().replace("+00:00", "Z")
