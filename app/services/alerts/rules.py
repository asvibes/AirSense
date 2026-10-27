from dataclasses import dataclass

from app.models.threshold import ThresholdPolicy


@dataclass(frozen=True)
class ReadingEvaluation:
    rapid_rise_per_minute: float | None
    triggered_levels: frozenset[str]


def evaluate_reading(
    value: float,
    previous_value: float | None,
    elapsed_seconds: float | None,
    policy: ThresholdPolicy,
    elevated_sustained: bool,
) -> ReadingEvaluation:
    rise = None
    if previous_value is not None and elapsed_seconds and elapsed_seconds > 0:
        rise = (value - previous_value) * 60 / elapsed_seconds

    levels = set()
    if value >= policy.high_threshold:
        levels.add("high")
    if elevated_sustained and value >= policy.elevated_threshold:
        levels.add("elevated")
    if rise is not None and rise >= policy.rapid_rise_per_minute:
        levels.add("rapid_rise")

    return ReadingEvaluation(rise, frozenset(levels))