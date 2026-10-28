import unittest

from app.services.alerts.wording import build_alert_detail


class AlertWordingTests(unittest.TestCase):
    def test_high_alert_includes_metric_value_unit_and_threshold(self):
        detail = build_alert_detail(
            level="high",
            metric_name="Carbon dioxide",
            value=1650,
            threshold=1500,
            unit="ppm",
        )

        self.assertEqual(
            detail,
            "The Carbon dioxide reading reached 1,650 ppm, at or above the "
            "guideline level used by AirSense (1,500 ppm).",
        )

    def test_elevated_alert_uses_sustained_wording(self):
        detail = build_alert_detail(
            level="elevated",
            metric_name="Carbon dioxide",
            value=1125.5,
            threshold=1000,
            unit="ppm",
        )

        self.assertIn("remained elevated at 1,125.5 ppm", detail)
        self.assertIn("at or above the guideline level used by AirSense", detail)
        self.assertIn("AirSense (1,000 ppm)", detail)

    def test_metric_code_is_expanded_to_a_readable_name(self):
        detail = build_alert_detail(
            level="high",
            metric_name="CO2",
            value=1600,
            threshold=1500,
            unit="ppm",
        )

        self.assertIn("The Carbon dioxide reading", detail)

    def test_rapid_rise_alert_uses_rate_unit_and_threshold(self):
        detail = build_alert_detail(
            level="rapid_rise",
            metric_name="Carbon dioxide",
            value=240,
            threshold=200,
            unit="ppm/min",
        )

        self.assertEqual(
            detail,
            "The Carbon dioxide level rose at 240 ppm/min, exceeding the "
            "configured rapid-rise threshold of 200 ppm/min.",
        )

    def test_unknown_level_and_non_finite_values_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unsupported alert level"):
            build_alert_detail(
                level="unknown",
                metric_name="CO2",
                value=100,
                threshold=50,
                unit="ppm",
            )

        with self.assertRaisesRegex(ValueError, "finite"):
            build_alert_detail(
                level="high",
                metric_name="CO2",
                value=float("inf"),
                threshold=50,
                unit="ppm",
            )


if __name__ == "__main__":
    unittest.main()
