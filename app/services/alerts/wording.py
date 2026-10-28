import math

_METRIC_NAMES = {
    "CO": "Carbon monoxide",
    "CO2": "Carbon dioxide",
    "NO2": "Nitrogen dioxide",
}


def _format_number(value: float) -> str:
    if not math.isfinite(value):
        raise ValueError("Alert values must be finite numbers.")
    return f"{value:,.4f}".rstrip("0").rstrip(".")


def build_alert_detail(
    *,
    level: str,
    metric_name: str,
    value: float,
    threshold: float,
    unit: str,
) -> str:
    metric = metric_name.strip()
    metric = _METRIC_NAMES.get(metric.upper(), metric)
    measurement_unit = unit.strip()
    if not metric:
        raise ValueError("Metric name cannot be empty.")
    if not measurement_unit:
        raise ValueError("Measurement unit cannot be empty.")

    formatted_value = _format_number(value)
    formatted_threshold = _format_number(threshold)

    if level in ("high", "elevated"):
        condition = "reached" if level == "high" else "remained elevated at"
        return (
            f"The {metric} reading {condition} {formatted_value} "
            f"{measurement_unit}, at or above the guideline level used by AirSense "
            f"({formatted_threshold} {measurement_unit})."
        )
    if level == "rapid_rise":
        return (
            f"The {metric} level rose at {formatted_value} {measurement_unit}, "
            f"exceeding the configured rapid-rise threshold of "
            f"{formatted_threshold} {measurement_unit}."
        )
    raise ValueError(f"Unsupported alert level: {level!r}")
