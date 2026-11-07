import json
import math
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from app.timestamps import normalize_utc

MIN_SAMPLES = 30
MIN_TREND_IMPROVEMENT = 0.05
MAX_FORECAST_SECONDS = 24 * 60 * 60


def _fit_linear(samples: list[tuple[datetime, float]]) -> tuple[float, float, datetime]:
    anchor = samples[0][0]
    points = [((timestamp - anchor).total_seconds(), value) for timestamp, value in samples]
    mean_x = sum(point[0] for point in points) / len(points)
    mean_y = sum(point[1] for point in points) / len(points)
    variance = sum((x - mean_x) ** 2 for x, _ in points)
    if variance == 0:
        return 0.0, mean_y, anchor
    slope = sum((x - mean_x) * (y - mean_y) for x, y in points) / variance
    return slope, mean_y - slope * mean_x, anchor


def _metrics(actual: list[float], predicted: list[float]) -> dict[str, float | None]:
    errors = [prediction - value for value, prediction in zip(actual, predicted)]
    mae = sum(abs(error) for error in errors) / len(errors)
    rmse = math.sqrt(sum(error * error for error in errors) / len(errors))
    mean = sum(actual) / len(actual)
    total = sum((value - mean) ** 2 for value in actual)
    r_squared = 1 - sum(error * error for error in errors) / total if total else None
    return {"mae": mae, "rmse": rmse, "r2": r_squared}


def evaluate_and_fit(
    samples: Iterable[tuple[datetime, float]],
    min_samples: int = MIN_SAMPLES,
) -> dict:
    prepared = []
    excluded_count = 0
    for timestamp, value in samples:
        try:
            numeric_value = float(value)
            if not isinstance(timestamp, datetime) or not math.isfinite(numeric_value):
                raise ValueError
            prepared.append((normalize_utc(timestamp), numeric_value))
        except (TypeError, ValueError, OverflowError):
            excluded_count += 1
    ordered = sorted(prepared, key=lambda item: item[0])
    if len(ordered) < min_samples:
        return {
            "available": False,
            "reason": f"At least {min_samples} real readings are required; found {len(ordered)}.",
            "sample_count": len(ordered),
            "excluded_count": excluded_count,
        }
    if len({timestamp for timestamp, _ in ordered}) != len(ordered):
        deduplicated = {}
        for timestamp, value in ordered:
            deduplicated[timestamp] = value
        excluded_count += len(ordered) - len(deduplicated)
        ordered = sorted(deduplicated.items())
        if len(ordered) < min_samples:
            return {
                "available": False,
                "reason": f"At least {min_samples} distinct timestamped readings are required.",
                "sample_count": len(ordered),
                "excluded_count": excluded_count,
            }

    split = min(max(int(len(ordered) * 0.8), 2), len(ordered) - 1)
    training = ordered[:split]
    testing = ordered[split:]
    tested_horizon = (testing[-1][0] - training[-1][0]).total_seconds()
    if tested_horizon <= 0:
        return {
            "available": False,
            "reason": "The stored timestamps do not provide a forward test interval.",
            "sample_count": len(ordered),
            "excluded_count": excluded_count,
        }

    slope, intercept, anchor = _fit_linear(training)
    actual = [value for _, value in testing]
    trend_predictions = [
        intercept + slope * (timestamp - anchor).total_seconds()
        for timestamp, _ in testing
    ]
    baseline_predictions = [training[-1][1]] * len(testing)
    trend_metrics = _metrics(actual, trend_predictions)
    baseline_metrics = _metrics(actual, baseline_predictions)
    if baseline_metrics["mae"] == 0 or trend_metrics["mae"] >= baseline_metrics["mae"] * (
        1 - MIN_TREND_IMPROVEMENT
    ):
        return {
            "available": False,
            "reason": "The trend model did not beat the persistence baseline by at least 5% on later readings.",
            "sample_count": len(ordered),
            "excluded_count": excluded_count,
            "training_count": len(training),
            "testing_count": len(testing),
            "tested_horizon_seconds": tested_horizon,
            "metrics": {"trend": trend_metrics, "persistence": baseline_metrics},
        }

    residuals = sorted(abs(value - prediction) for value, prediction in zip(actual, trend_predictions))
    interval_index = min(len(residuals) - 1, math.ceil(len(residuals) * 0.9) - 1)
    slope, intercept, anchor = _fit_linear(ordered)
    return {
        "available": True,
        "sample_count": len(ordered),
        "excluded_count": excluded_count,
        "training_count": len(training),
        "testing_count": len(testing),
        "tested_horizon_seconds": tested_horizon,
        "metrics": {"trend": trend_metrics, "persistence": baseline_metrics},
        "model": {
            "kind": "linear_time_trend",
            "anchor": anchor.isoformat(),
            "slope_per_second": slope,
            "intercept": intercept,
            "residual_p90": residuals[interval_index],
        },
    }


def predict(model: dict, now: datetime, horizon_seconds: int, points: int = 12) -> list[dict]:
    if horizon_seconds <= 0 or horizon_seconds > MAX_FORECAST_SECONDS:
        raise ValueError("Forecast horizon must be between 1 second and 24 hours.")
    anchor = normalize_utc(datetime.fromisoformat(model["anchor"]))
    now = normalize_utc(now)
    result = []
    for index in range(1, points + 1):
        timestamp = now.timestamp() + horizon_seconds * index / points
        measured_at = datetime.fromtimestamp(timestamp, timezone.utc)
        value = model["intercept"] + model["slope_per_second"] * (
            measured_at - anchor
        ).total_seconds()
        result.append(
            {
                "measured_at": measured_at.isoformat().replace("+00:00", "Z"),
                "value": value,
                "lower": value - model["residual_p90"],
                "upper": value + model["residual_p90"],
            }
        )
    return result


def load_saved_models(path: str | Path) -> list[dict]:
    try:
        with open(path, encoding="utf-8") as file:
            document = json.load(file)
    except FileNotFoundError:
        return []
    if not isinstance(document, dict) or document.get("format_version") != 1:
        raise ValueError("Saved forecast model file has an unsupported format.")
    models = document.get("models")
    if not isinstance(models, list):
        raise ValueError("Saved forecast model file does not contain a model list.")
    return models


def save_models(path: str | Path, models: list[dict]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_path = tempfile.mkstemp(prefix="airsense-forecast-", dir=target.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump(
                {
                    "format_version": 1,
                    "trained_at": datetime.now(timezone.utc).isoformat(),
                    "models": models,
                },
                file,
                separators=(",", ":"),
            )
        os.replace(temporary_path, target)
    except Exception:
        try:
            os.unlink(temporary_path)
        except FileNotFoundError:
            pass
        raise
