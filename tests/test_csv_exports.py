import csv
import io
import unittest
from datetime import datetime, timezone

from app.csv_safety import safe_csv_cell
from app.db import get_session
from app.models.reading import Reading
from app.models.room import Room
from app.timestamps import format_utc
from helpers import AirSenseTestCase


class SafeCsvCellTests(unittest.TestCase):
    def test_formula_markers_are_escaped_after_whitespace_or_controls(self):
        for value in (
            "=1+1",
            "+1+1",
            "-1+1",
            "@SUM(A1)",
            " \t=1+1",
            "\r\n@SUM(A1)",
            "\x00-1+1",
            "\ufeff+1+1",
        ):
            with self.subTest(value=value):
                self.assertEqual(safe_csv_cell(value), "'" + value.replace("\x00", ""))

    def test_ordinary_text_and_non_text_values_are_unchanged(self):
        for value in ("Bedroom", " ppm", "2026-11-05T00:00:00Z", 1400.0, None):
            with self.subTest(value=value):
                self.assertEqual(safe_csv_cell(value), value)


class CsvExportSafetyTests(AirSenseTestCase):
    def test_history_export_neutralizes_formula_room_names_and_preserves_normal_cells(self):
        formula_names = (
            "=1+1",
            "+1+1",
            "-1+1",
            "@SUM(A1)",
            " \t=1+1",
            "\r\n@SUM(A1)",
            "\x00-1+1",
        )
        base_time = datetime.now(timezone.utc)
        with self.app.app_context():
            db = get_session()
            for index, name in enumerate(("Bedroom", *formula_names)):
                room_id = f"csv-test-room-{index}"
                db.add(
                    Room(
                        id=room_id,
                        home_id=self.home_id,
                        name=name,
                        ventilation="Window",
                        ventilation_sources=["Window"],
                    )
                )
                db.flush()
                db.add(
                    Reading(
                        home_id=self.home_id,
                        room_id=room_id,
                        metric_code="CO2",
                        value=800 + index,
                        source="device",
                        measured_at=base_time.replace(microsecond=index),
                    )
                )
            db.commit()

        response = self.client.get(f"/api/homes/{self.home_id}/history.csv")
        self.assertEqual(response.status_code, 200)
        rows = list(csv.DictReader(io.StringIO(response.get_data(as_text=True))))
        self.assertEqual(
            list(rows[0]),
            ["measured_at", "received_at", "room", "metric", "value", "unit", "source"],
        )
        by_room_value = {row["value"]: row for row in rows}

        normal = by_room_value["800.0"]
        self.assertEqual(
            normal["measured_at"],
            format_utc(base_time.replace(microsecond=0)),
        )
        self.assertEqual(normal["room"], "Bedroom")
        self.assertEqual(normal["metric"], "CO2")
        self.assertEqual(normal["value"], "800.0")
        self.assertEqual(normal["unit"], "ppm")
        self.assertEqual(normal["source"], "device")

        for index, name in enumerate(formula_names, start=1):
            with self.subTest(name=name):
                self.assertEqual(
                    by_room_value[f"{800 + index}.0"]["room"],
                    "'" + name.replace("\x00", ""),
                )
