from typing import Literal

from app.models.alert import AlertStatus


ReadingAction = Literal["open", "update", "clear", "none"]


class InvalidAlertTransition(ValueError):
    pass


def reading_action(
    status: AlertStatus | None,
    co2_ppm: float,
    threshold_ppm: float,
) -> ReadingAction:
    if status is None or status is AlertStatus.CLEARED:
        return "open" if co2_ppm > threshold_ppm else "none"

    if status in (AlertStatus.ACTIVE, AlertStatus.ACKNOWLEDGED):
        return "clear" if co2_ppm <= threshold_ppm else "update"

    raise ValueError(f"Unsupported alert status: {status!r}")


def acknowledged_status(status: AlertStatus) -> AlertStatus:
    if status is AlertStatus.ACTIVE:
        return AlertStatus.ACKNOWLEDGED
    if status is AlertStatus.ACKNOWLEDGED:
        return status
    if status is AlertStatus.CLEARED:
        raise InvalidAlertTransition("A cleared alert cannot be acknowledged.")
    raise ValueError(f"Unsupported alert status: {status!r}")