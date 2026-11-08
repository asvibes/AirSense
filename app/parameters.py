import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Parameter:
    code: str
    name: str
    unit: str
    aliases: tuple[str, ...]
    conversions: dict[str, tuple[float, float]]


PARAMETERS = (
    Parameter("CO2", "Carbon dioxide", "ppm", ("co2", "carbon dioxide", "rco2"), {"ppm": (1, 0), "ppb": (0.001, 0)}),
    Parameter("PM1", "PM1", "ug/m3", ("pm1", "pms1"), {"ug/m3": (1, 0), "mg/m3": (1000, 0)}),
    Parameter("PM2_5", "PM2.5", "ug/m3", ("pm2.5", "pm2_5", "pm25", "pm2.5um", "pms2_5", "pms25"), {"ug/m3": (1, 0), "mg/m3": (1000, 0)}),
    Parameter("PM10", "PM10", "ug/m3", ("pm10", "pm10.0", "pms10"), {"ug/m3": (1, 0), "mg/m3": (1000, 0)}),
    Parameter("TEMPERATURE", "Temperature", "C", ("temperature", "temp", "ambient temperature", "t"), {"c": (1, 0), "f": (5 / 9, -32 * 5 / 9), "k": (1, -273.15)}),
    Parameter("HUMIDITY", "Humidity", "%", ("humidity", "relative humidity", "rh", "h"), {"%": (1, 0), "fraction": (100, 0)}),
    Parameter("CO", "Carbon monoxide", "ppm", ("co", "carbon monoxide"), {"ppm": (1, 0), "ppb": (0.001, 0)}),
    Parameter("NO2", "Nitrogen dioxide", "ppm", ("no2", "nitrogen dioxide"), {"ppm": (1, 0), "ppb": (0.001, 0)}),
    Parameter("VOC", "Volatile organic compounds", "ppb", ("voc", "tvoc", "volatile organic compounds"), {"ppb": (1, 0), "ppm": (1000, 0)}),
    Parameter("ETHANOL", "Ethyl alcohol", "ppb", ("c2h5oh", "ethanol", "ethyl alcohol"), {"ppb": (1, 0), "ppm": (1000, 0)}),
)

# Broad engineering sanity bounds, not health or regulatory thresholds.
PLAUSIBLE_RANGES = {
    "CO2": (0.0, 100_000.0),
    "PM1": (0.0, 1_000_000.0),
    "PM2_5": (0.0, 1_000_000.0),
    "PM10": (0.0, 1_000_000.0),
    "TEMPERATURE": (-100.0, 100.0),
    "HUMIDITY": (0.0, 100.0),
    "CO": (0.0, 100_000.0),
    "NO2": (0.0, 100_000.0),
    "VOC": (0.0, 1_000_000.0),
    "ETHANOL": (0.0, 1_000_000.0),
}

_ALIASES = {
    re.sub(r"[^a-z0-9]", "", alias.lower()): parameter
    for parameter in PARAMETERS
    for alias in (parameter.code, *parameter.aliases)
}
_UNIT_ALIASES = {
    "ppm": "ppm",
    "partspermillion": "ppm",
    "ppb": "ppb",
    "partsperbillion": "ppb",
    "ugm3": "ug/m3",
    "mgm3": "mg/m3",
    "c": "c",
    "degc": "c",
    "celsius": "c",
    "f": "f",
    "degf": "f",
    "fahrenheit": "f",
    "k": "k",
    "kelvin": "k",
    "percent": "%",
    "pct": "%",
    "%": "%",
    "fraction": "fraction",
    "bqm3": "Bq/m3",
    "pa": "Pa",
    "hpa": "hPa",
    "lux": "lux",
    "ms": "m/s",
    "db": "dB",
}
_UNIT_SUFFIX = re.compile(
    r"(?:\s*\(([^()]*)\)|\s*\[([^\[\]]*)\]|[\s_-]+([a-zA-Z%°µμ/³²]+))\s*$"
)
_TIMESTAMP_COLUMNS = {
    "ts", "time", "timestamp", "datetime", "measuredat", "measurementtime",
    "recordedat", "date",
}
_LOCATION_COLUMNS = {
    "room", "location", "loc", "roomname", "sensor", "sensorid", "deviceid",
    "customer", "site", "home", "id", "index",
}


def normalize_header(value: str) -> str:
    normalized = value.lower().translate(
        str.maketrans({"₀": "0", "₁": "1", "₂": "2", "₃": "3", "₅": "5"})
    )
    return re.sub(r"[^a-z0-9]", "", normalized)


def parameter_for_code(code: str) -> Parameter | None:
    if code.strip().lower().replace(" ", "") in {"pm1.0", "pm1_0"}:
        return _ALIASES["pm1"]
    return _ALIASES.get(normalize_header(code))


def plausible_range_for(code: str) -> tuple[float, float] | None:
    return PLAUSIBLE_RANGES.get(canonical_metric_code(code))


def canonical_metric_code(code: str) -> str:
    parameter = parameter_for_code(code)
    if parameter:
        return parameter.code
    return code.upper().replace(".", "_")


def parse_unit(value: str | None) -> str | None:
    if not value:
        return None
    unit = value.strip().lower().replace("μ", "u").replace("µ", "u")
    unit = unit.replace("³", "3").replace("²", "2").replace("°", "")
    compact = re.sub(r"[^a-z0-9%]", "", unit)
    if compact in _UNIT_ALIASES:
        return _UNIT_ALIASES[compact]
    if "/" in unit:
        numerator, denominator = (part.strip() for part in unit.split("/", 1))
        numerator = re.sub(r"[^a-z0-9%]", "", numerator)
        denominator = re.sub(r"[^a-z0-9]", "", denominator)
        if (numerator, denominator) in {("ug", "m3"), ("mg", "m3")}:
            return f"{numerator}/m3"
        if (numerator, denominator) == ("bq", "m3"):
            return "Bq/m3"
    normalized = unit.replace(" ", "")
    if normalized in {"pa", "hpa", "lux", "m/s", "db"}:
        return _UNIT_ALIASES[normalized.replace("/", "")]
    return None


def resolve_column(header: str) -> tuple[Parameter | None, str | None, str]:
    raw = header.strip()
    explicit_unit = None
    base = raw
    match = _UNIT_SUFFIX.search(raw)
    if match:
        candidate = next((part for part in match.groups() if part is not None), None)
        parsed_unit = parse_unit(candidate)
        prefix = raw[:match.start()].strip()
        if parsed_unit and prefix:
            base, explicit_unit = prefix, parsed_unit
    parameter = parameter_for_code(base)
    return parameter, explicit_unit, base


def normalize_value(
    value: float, parameter: Parameter, unit: str | None
) -> tuple[float, str, bool]:
    assumed = unit is None
    source_unit = unit or parse_unit(parameter.unit) or parameter.unit
    conversions = parameter.conversions
    if source_unit not in conversions:
        raise ValueError(f"Unit {source_unit!r} is not supported for {parameter.name}.")
    factor, offset = conversions[source_unit]
    normalized = value * factor + offset
    if parameter.code == "TEMPERATURE" and normalized < -273.15:
        raise ValueError(f"{parameter.name} cannot be below absolute zero.")
    if parameter.code != "TEMPERATURE" and normalized < 0:
        raise ValueError(f"{parameter.name} cannot be negative.")
    return normalized, parameter.unit, assumed


def custom_metric(header: str, unit: str | None) -> tuple[str, str] | None:
    if unit is None:
        return None
    code = re.sub(r"[^A-Za-z0-9_-]", "_", header.strip()).strip("_").upper()
    code = re.sub(r"_+", "_", code)
    if not code or len(code) > 32 or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,31}", code):
        return None
    if unit not in {
        "ppm", "ppb", "ug/m3", "mg/m3", "c", "f", "k", "%", "fraction",
        "Bq/m3", "Pa", "hPa", "lux", "m/s", "dB",
    }:
        return None
    return code, unit


def is_metadata_column(header: str) -> bool:
    normalized = normalize_header(header)
    return normalized in _TIMESTAMP_COLUMNS | _LOCATION_COLUMNS or normalized.startswith("valid")
