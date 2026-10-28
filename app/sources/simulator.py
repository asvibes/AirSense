_SCENARIO_VALUES = {
    "high": 1800,
    "elevated": 1250,
    "rapid": 1600,
    "rapid_rise": 1600,
    "clear": 600,
}


def build_simulated_reading(
    *,
    room: str,
    scenario: str | None = None,
    value: object = None,
    metric: str = "CO2",
    unit: str = "ppm",
    measured_at: str | None = None,
) -> dict[str, object]:
    if scenario is not None:
        if value is not None:
            raise ValueError("Provide either scenario or value, not both.")
        if not isinstance(scenario, str):
            raise ValueError("scenario must be high, elevated, rapid, or clear.")
        normalized_scenario = scenario.strip().lower().replace(" ", "_")
        if normalized_scenario not in _SCENARIO_VALUES:
            raise ValueError("scenario must be high, elevated, rapid, or clear.")
        value = _SCENARIO_VALUES[normalized_scenario]

    payload: dict[str, object] = {
        "room": room,
        "metric": metric,
        "unit": unit,
        "value": value,
    }
    if measured_at is not None:
        payload["measured_at"] = measured_at
    return payload
