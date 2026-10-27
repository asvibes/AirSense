from datetime import datetime

from app.models.alert import AlertStatus


class InvalidAlertTransition(ValueError):
    pass


def acknowledge_status(status: str) -> str:
    if status == AlertStatus.ACTIVE.value:
        return AlertStatus.ACKNOWLEDGED.value
    if status == AlertStatus.ACKNOWLEDGED.value:
        return status
    if status == AlertStatus.ALL_CLEAR.value:
        raise InvalidAlertTransition("An all-clear alert cannot be acknowledged.")
    raise ValueError(f"Unsupported alert status: {status!r}")


def all_clear_progress(
    *,
    value: float,
    threshold: float,
    below_since: datetime | None,
    measured_at: datetime,
    previous_reading_at: datetime | None,
    max_reading_gap_seconds: int,
    clear_duration_seconds: int,
) -> tuple[datetime | None, bool]:
    if value >= threshold:
        return None, False

    if (
        below_since is None
        or previous_reading_at is None
        or (measured_at - previous_reading_at).total_seconds()
        > max_reading_gap_seconds
    ):
        return measured_at, False

    sustained_seconds = (measured_at - below_since).total_seconds()
    return below_since, sustained_seconds >= clear_duration_seconds
