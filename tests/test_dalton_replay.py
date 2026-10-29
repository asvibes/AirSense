import csv
from pathlib import Path

from app.sources.dalton_replay import load_dalton_csv
from tests.helpers import AirSenseTestCase


class DaltonReplayTests(AirSenseTestCase):
    def _write_csv(self, filename: str, rows):
        csv_path = Path(self.temp_dir.name) / filename
        with csv_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=["ts", "CO2", "Valid_CO2", "Loc", "Customer"],
            )
            writer.writeheader()
            writer.writerows(rows)
        return csv_path

    def test_load_dalton_csv_filters_invalid_co2_rows(self):
        csv_path = self._write_csv(
            "sample.csv",
            [
                {"ts": "2023-06-10 00:00:00", "CO2": "420", "Valid_CO2": 1, "Loc": "Bedroom", "Customer": "P1"},
                {"ts": "2023-06-10 00:00:05", "CO2": "999", "Valid_CO2": 0, "Loc": "Bedroom", "Customer": "P1"},
                {"ts": "2023-06-10 00:00:10", "CO2": "640", "Valid_CO2": 1, "Loc": "Bedroom", "Customer": "P1"},
            ],
        )

        rows = load_dalton_csv(csv_path, limit=10)

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["room"], "Bedroom")
        self.assertEqual(rows[0]["metric"], "CO2")
        self.assertEqual(rows[0]["unit"], "ppm")
        self.assertEqual(rows[0]["value"], 420.0)

    def test_demo_replay_route_ingests_dalton_csv(self):
        room = self.create_room("Bedroom")
        csv_path = self._write_csv(
            "replay.csv",
            [
                {"ts": "2023-06-10 00:00:00", "CO2": "825", "Valid_CO2": 1, "Loc": "Bedroom", "Customer": "P1"},
                {"ts": "2023-06-10 00:00:30", "CO2": "1100", "Valid_CO2": 1, "Loc": "Bedroom", "Customer": "P1"},
                {"ts": "2023-06-10 00:01:00", "CO2": "1300", "Valid_CO2": 0, "Loc": "Bedroom", "Customer": "P1"},
            ],
        )

        response = self.request_json(
            "POST",
            f"/api/homes/{self.home_id}/demo/replay",
            {"room_id": room["id"], "csv_path": csv_path.as_posix(), "limit": 2},
        )

        self.assertEqual(response.status_code, 201, response.get_json())
        self.assertEqual(response.get_json()["imported"], 2)
        self.assertEqual(response.get_json()["source"], "dalton_replay")
