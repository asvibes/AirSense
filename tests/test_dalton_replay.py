import csv
from datetime import datetime, timezone
from io import BytesIO, StringIO
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
                {"ts": "2023-06-10 00:00:15", "CO2": "0", "Valid_CO2": 1, "Loc": "Bedroom", "Customer": "P1"},
            ],
        )

        rows = load_dalton_csv(csv_path, limit=10)

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["room"], "Bedroom")
        self.assertEqual(rows[0]["metric"], "CO2")
        self.assertEqual(rows[0]["unit"], "ppm")
        self.assertEqual(rows[0]["value"], 420.0)

    def test_load_dalton_csv_handles_bom_invalid_timestamps_and_unsorted_rows(self):
        csv_text = (
            "\ufeffts,CO2,Valid_CO2,Loc\n"
            "2023-06-10 00:00:10,640,1,Bedroom\n"
            "not-a-timestamp,700,1,Bedroom\n"
            "2023-06-10 00:00:00,420,1,Bedroom\n"
        )

        rows = load_dalton_csv(StringIO(csv_text), limit=10)

        self.assertEqual([row["value"] for row in rows], [420.0, 640.0])

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

        response = self.client.post(
            f"/api/homes/{self.home_id}/demo/replay",
            data={
                "room_id": room["id"],
                "limit": "2",
                "shift_timestamps": "false",
                "csv_file": (BytesIO(csv_path.read_bytes()), "replay.csv"),
            },
            headers={"X-CSRF-Token": self.csrf},
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 201, response.get_json())
        self.assertEqual(response.get_json()["imported"], 2)
        self.assertEqual(response.get_json()["source"], "dalton_replay")
        self.assertFalse(response.get_json()["timestamps_shifted"])
        self.assertEqual(response.get_json()["source_file"], "replay.csv")
        self.assertEqual(
            response.get_json()["created"][0]["measured_at"],
            "2023-06-10T00:00:00Z",
        )
        dashboard = self.client.get(
            f"/api/homes/{self.home_id}/dashboard"
        )
        self.assertEqual(dashboard.status_code, 200, dashboard.get_json())
        latest_reading = dashboard.get_json()["readings"][0]
        self.assertEqual(latest_reading["source"], "dataset")
        self.assertEqual(latest_reading["value"], 1100)

    def test_demo_replay_shifts_timestamps_and_rejects_missing_file(self):
        room = self.create_room("Bedroom")
        csv_content = (
            "ts,CO2,Valid_CO2,Loc\n"
            "2023-06-10 00:00:00,825,1,Bedroom\n"
            "2023-06-10 00:00:30,1100,1,Bedroom\n"
        )
        response = self.client.post(
            f"/api/homes/{self.home_id}/demo/replay",
            data={
                "room_id": room["id"],
                "limit": "2",
                "shift_timestamps": "true",
                "csv_file": (BytesIO(csv_content.encode()), "replay.csv"),
            },
            headers={"X-CSRF-Token": self.csrf},
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 201, response.get_json())
        self.assertTrue(response.get_json()["timestamps_shifted"])
        latest = datetime.fromisoformat(
            response.get_json()["created"][-1]["measured_at"].replace("Z", "+00:00")
        )
        self.assertLessEqual(
            (datetime.now(timezone.utc) - latest).total_seconds(),
            2,
        )

        missing_file = self.request_json(
            "POST",
            f"/api/homes/{self.home_id}/demo/replay",
            {"room_id": room["id"]},
        )
        self.assertEqual(missing_file.status_code, 400)
        self.assertIn("Choose a DALTON CSV", missing_file.get_json()["error"])
