import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.ml.forecasting import evaluate_and_fit, load_saved_models, predict, save_models


class ForecastingServiceTests(unittest.TestCase):
    def test_requires_enough_timestamped_real_samples(self):
        samples = [
            (datetime(2025, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=index), 400)
            for index in range(10)
        ]
        result = evaluate_and_fit(samples)
        self.assertFalse(result["available"])
        self.assertIn("At least", result["reason"])

    def test_constant_series_does_not_claim_to_beat_persistence(self):
        samples = [
            (datetime(2025, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=index), 400)
            for index in range(40)
        ]
        result = evaluate_and_fit(samples)
        self.assertFalse(result["available"])
        self.assertIn("persistence baseline", result["reason"])
        self.assertEqual(result["metrics"]["persistence"]["mae"], 0)

    def test_trend_uses_later_holdout_and_produces_forecast_interval(self):
        start = datetime(2025, 1, 1, tzinfo=timezone.utc)
        samples = [
            (start + timedelta(minutes=index * 5), 400 + index * 2 + (index % 3) * .1)
            for index in range(60)
        ]
        result = evaluate_and_fit(samples)
        self.assertTrue(result["available"], result)
        self.assertEqual(result["training_count"], 48)
        self.assertEqual(result["testing_count"], 12)
        self.assertLess(result["metrics"]["trend"]["mae"], result["metrics"]["persistence"]["mae"])
        forecast = predict(
            result["model"],
            start + timedelta(hours=5),
            600,
            points=3,
        )
        self.assertEqual(len(forecast), 3)
        self.assertLessEqual(forecast[0]["lower"], forecast[0]["value"])
        self.assertGreaterEqual(forecast[0]["upper"], forecast[0]["value"])

    def test_preprocessing_sorts_and_deduplicates_timestamps(self):
        start = datetime(2025, 1, 1, tzinfo=timezone.utc)
        samples = [
            (start + timedelta(minutes=index), 500 + index)
            for index in reversed(range(40))
        ]
        samples.append((start + timedelta(minutes=5), 505))
        samples.append((start, float("nan")))
        samples.append((None, 500))
        result = evaluate_and_fit(samples)
        self.assertTrue(result["available"], result)
        self.assertEqual(result["sample_count"], 40)
        self.assertEqual(result["excluded_count"], 3)
        self.assertEqual(result["training_count"], 32)

    def test_model_artifact_round_trips_as_json(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "forecast_models.json"
            save_models(path, [{"metric": "CO2", "available": False}])
            self.assertEqual(load_saved_models(path)[0]["metric"], "CO2")


if __name__ == "__main__":
    unittest.main()
