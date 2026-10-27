from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Mapping


class AlertStatus(str, Enum):
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    CLEARED = "cleared"


@dataclass(frozen=True)
class Alert:
    id: int
    room_name: str
    status: AlertStatus
    trigger_co2_ppm: float
    threshold_ppm: float
    latest_co2_ppm: float
    created_at: str
    acknowledged_at: str | None
    acknowledged_by: str | None
    cleared_at: str | None

    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> "Alert":
        values = dict(row)
        values["status"] = AlertStatus(values["status"])
        return cls(**values)

    def to_dict(self) -> dict[str, Any]:
        values = asdict(self)
        values["status"] = self.status.value
        return values