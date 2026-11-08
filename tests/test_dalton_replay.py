import csv
from datetime import datetime, timedelta, timezone
from io import BytesIO, StringIO
from pathlib import Path

from sqlalchemy import event, select

from app.db import get_session
from app.models.alert import Alert
from app.models.audit import AuditLog
from app.models.reading import Reading
from app.models.user import RateLimitBucket
from app.services.ingestion.ingest import ingest_dataset_batch
from app.sources.dalton_replay import load_dalton_csv, parse_environmental_csv
from tests.helpers import AirSenseTestCase


class DaltonReplayTests(AirSenseTestCase):
    def test_dataset_batch_uses_bounded_scope_queries_and_one_reading_insert(self):
        room = self.create_room("Batch query room")
        start = datetime.now(timezone.utc) - timedelta(minutes=10)
        payloads = [
            {
                "room": room["name"],
                "metric": "CO2",
                "value": 400 + index,
                "unit": "ppm",
                "measured_at": (start + timedelta(seconds=index)).isoformat(),
            }
            for index in range(40)
        ]
        statements = []
        engine = self.app.extensions["airsense_engine"]

        def capture(_connection, _cursor, statement, _parameters, _context, _many):
            normalized = " ".join(statement.lower().split())
            if any(table in normalized for table in ("homes", "rooms", "metrics", "air_readings")):
                statements.append(normalized)

        event.listen(engine, "before_cursor_execute", capture)
        try:
            with self.app.app_context():
                result = ingest_dataset_batch(
                    get_session(),
                    home_id=self.home_id,
                    room_id=room["id"],
                    payloads=payloads,
                    actor_user_id=None,
                    max_future_seconds=self.app.config["MAX_FUTURE_SECONDS"],
                    defaults={
                        "high_threshold": self.app.config["HIGH_THRESHOLD"],
                        "elevated_threshold": self.app.config["ELEVATED_THRESHOLD"],
                        "rapid_rise_per_minute": self.app.config["RAPID_RISE_PER_MINUTE"],
                        "elevated_duration_seconds": self.app.config["ELEVATED_DURATION_SECONDS"],
                        "all_clear_duration_seconds": self.app.config["ALL_CLEAR_DURATION_SECONDS"],
                        "max_reading_gap_seconds": self.app.config["MAX_READING_GAP_SECONDS"],
                    },
                )
                get_session().commit()
        finally:
            event.remove(engine, "before_cursor_execute", capture)

        self.assertEqual(len(result), 40)
        self.assertEqual(sum(" from homes " in sql for sql in statements), 1)
        self.assertEqual(sum(" from rooms " in sql for sql in statements), 1)
        self.assertEqual(sum(" from metrics " in sql for sql in statements), 1)
        self.assertEqual(sum("insert into air_readings" in sql for sql in statements), 1)

    def test_dalton_zero_gap_values_are_discarded(self):
        dataset = parse_environmental_csv(
            StringIO(
                "ts,CO2,Valid_CO2,T,H\n"
                "2023/06/10 12:05:29,0,1,0,0\n"
                "2023/06/10 12:05:30,450,1,24,40\n"
            ),
            room_name="Dataset room",
        )

        self.assertEqual(
            [(reading["metric"], reading["value"]) for reading in dataset["readings"]],
            [
                ("CO2", 450),
                ("HUMIDITY", 40),
                ("TEMPERATURE", 24),
            ],
        )
        self.assertEqual(dataset["rows_skipped"], 1)

    def test_replay_rejects_non_csv_files(self):
        room = self.create_room("CSV validation room")
        response = self.client.post(
            f"/api/homes/{self.home_id}/demo/replay",
            data={
                "room_id": room["id"],
                "limit": "10",
                "csv_file": (BytesIO(b"ts,CO2\n2023-01-01T00:00:00Z,500\n"), "data.json"),
            },
            headers={"X-CSRF-Token": self.csrf},
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 400)
    def test_dalton_processed_csv_imports_documented_parameters_and_timestamps(self):
        room = self.create_room("Study Desk")
        csv_content = (
            "ts,T,H,PMS1,PMS2_5,PMS10,CO2,NO2,CO,VoC,C2H5OH,ID,Loc\n"
            "2023/06/10 12:05:29,24.1,36.4,23,39,45,283,46,249,392,438,101,Study Desk\n"
            "2023/06/10 12:05:30,24.1,36.5,23,39,45,284,47,250,391,438,101,Study Desk\n"
            "2023/06/10 12:05:31,24.1,36.4,23,39,46,284,47,249,391,437,101,Study Desk\n"
        )

        dataset = parse_environmental_csv(StringIO(csv_content), room_name=room["name"])
        expected_units = {
            "TEMPERATURE": "C",
            "HUMIDITY": "%",
            "PM1": "ug/m3",
            "PM2_5": "ug/m3",
            "PM10": "ug/m3",
            "CO2": "ppm",
            "NO2": "ppm",
            "CO": "ppm",
            "VOC": "ppb",
            "ETHANOL": "ppb",
        }
        self.assertEqual(
            {item["code"]: item["unit"] for item in dataset["parameters"]},
            expected_units,
        )
        self.assertEqual(len(dataset["readings"]), 30)
        self.assertEqual(dataset["rows_seen"], 3)
        self.assertEqual(dataset["rows_skipped"], 0)
        self.assertEqual(dataset["review_columns"], [])
        self.assertEqual(dataset["unsupported_columns"], [])
        first_by_metric = {
            reading["metric"]: reading for reading in dataset["readings"][:10]
        }
        self.assertEqual(first_by_metric["TEMPERATURE"]["value"], 24.1)
        self.assertEqual(first_by_metric["HUMIDITY"]["value"], 36.4)
        self.assertEqual(first_by_metric["PM1"]["value"], 23)
        self.assertEqual(first_by_metric["PM2_5"]["value"], 39)
        self.assertEqual(first_by_metric["PM10"]["value"], 45)
        self.assertEqual(first_by_metric["CO2"]["value"], 283)
        self.assertEqual(first_by_metric["NO2"]["value"], 0.046)
        self.assertEqual(first_by_metric["CO"]["value"], 249)
        self.assertEqual(first_by_metric["VOC"]["value"], 392)
        self.assertEqual(first_by_metric["ETHANOL"]["value"], 438)
        self.assertTrue(
            all(
                reading["measured_at"] == "2023-06-10T12:05:29Z"
                for reading in first_by_metric.values()
            )
        )

        response = self.client.post(
            f"/api/homes/{self.home_id}/demo/replay",
            data={
                "room_id": room["id"],
                "limit": "10",
                "csv_file": (BytesIO(csv_content.encode()), "dalton.csv"),
            },
            headers={"X-CSRF-Token": self.csrf},
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 201, response.get_json())
        payload = response.get_json()
        self.assertEqual(payload["source"], "dalton_replay")
        self.assertEqual(payload["imported"], 30)
        self.assertFalse(payload["timestamps_shifted"])
        self.assertEqual(payload["rows_skipped"], 0)
        self.assertEqual(payload["review_columns"], [])
        self.assertEqual(payload["unsupported_columns"], [])
        self.assertEqual(
            payload["created"][0]["measured_at"], "2023-06-10T12:05:29Z"
        )

    def test_dalton_header_aliases_are_case_insensitive(self):
        csv_text = (
            "TS,t,h,pMs1,pMs2_5,pMs10,cO2,nO2,cO,vOc,c2h5oh,ID,Loc\n"
            "2023/06/10 12:05:29,24,36,23,39,45,283,46,249,392,438,101,Room\n"
        )

        dataset = parse_environmental_csv(StringIO(csv_text), valid_only=False)

        self.assertEqual(len(dataset["readings"]), 10)
        self.assertEqual(
            {reading["metric"] for reading in dataset["readings"]},
            {
                "TEMPERATURE", "HUMIDITY", "PM1", "PM2_5", "PM10",
                "CO2", "NO2", "CO", "VOC", "ETHANOL",
            },
        )

    def test_unitless_non_dalton_measurements_are_flagged_not_assumed(self):
        dataset = parse_environmental_csv(
            StringIO("timestamp,temperature,humidity\n2023-06-10T12:05:29Z,24,36\n"),
            valid_only=False,
        )

        self.assertEqual(dataset["readings"], [])
        self.assertEqual(dataset["unsupported_columns"], [])
        self.assertEqual(
            {item["column"] for item in dataset["review_columns"]},
            {"temperature", "humidity"},
        )

    def test_environmental_csv_imports_available_parameters_and_converts_units(self):
        csv_text = (
            "Timestamp,PM2.5 (mg/m³),Temperature (°F),RH (%),CO (ppb),Mystery\n"
            "2024-06-10T00:00:00Z,0.035,77,45,400,123\n"
            "2024-06-10T00:01:00Z,0.040,,46,500,124\n"
        )

        dataset = parse_environmental_csv(StringIO(csv_text), valid_only=False)
        readings = dataset["readings"]
        by_parameter = {}
        for reading in readings:
            by_parameter.setdefault(reading["metric"], []).append(reading)

        self.assertEqual(set(by_parameter), {"PM2_5", "TEMPERATURE", "HUMIDITY", "CO"})
        self.assertEqual(by_parameter["PM2_5"][0]["value"], 35)
        self.assertEqual(by_parameter["PM2_5"][0]["unit"], "ug/m3")
        self.assertEqual(by_parameter["TEMPERATURE"][0]["value"], 25)
        self.assertEqual(by_parameter["HUMIDITY"][0]["value"], 45)
        self.assertEqual(by_parameter["CO"][0]["value"], 0.4)
        self.assertEqual(by_parameter["TEMPERATURE"][0]["measured_at"], "2024-06-10T00:00:00Z")
        self.assertIn(
            {"column": "Mystery", "reason": "Unrecognized measurement column. Add an explicit supported unit and parameter mapping before importing."},
            dataset["review_columns"],
        )
        self.assertEqual(
            [column["column"] for column in dataset["unsupported_columns"]],
            ["Mystery"],
        )

    def test_environmental_csv_reports_and_skips_duplicate_measurements(self):
        csv_text = (
            "timestamp,PM10 (ug/m3)\n"
            "2024-06-10T00:00:00Z,10\n"
            "2024-06-10T00:00:00Z,11\n"
            "2024-06-10T00:01:00Z,12\n"
        )

        dataset = parse_environmental_csv(StringIO(csv_text), valid_only=False)

        self.assertEqual([reading["value"] for reading in dataset["readings"]], [12])
        self.assertEqual(dataset["duplicate_readings"], [
            {"metric": "PM10", "measured_at": "2024-06-10T00:00:00Z"}
        ])
        self.assertEqual(dataset["rows_skipped"], 2)

    def test_environmental_csv_does_not_reject_dataset_for_invalid_optional_values(self):
        csv_text = (
            "timestamp,PM2.5 (ug/m3),Temperature (C),Humidity (%)\n"
            "2024-06-10T00:00:00Z,-1,-5,50\n"
            "2024-06-10T00:01:00Z,12,,\n"
        )

        dataset = parse_environmental_csv(StringIO(csv_text), valid_only=False)

        self.assertEqual(
            [(reading["metric"], reading["value"]) for reading in dataset["readings"]],
            [("HUMIDITY", 50), ("TEMPERATURE", -5), ("PM2_5", 12)],
        )
        self.assertEqual(dataset["rows_skipped"], 0)

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

    def test_load_dalton_csv_recognizes_case_insensitive_headers(self):
        csv_text = (
            "TS,co2,valid_co2,LOC\n"
            "2023/06/10 12:05:29,420,1,Bedroom\n"
        )

        rows = load_dalton_csv(StringIO(csv_text))

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["metric"], "CO2")
        self.assertEqual(rows[0]["measured_at"], "2023-06-10T12:05:29Z")

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
        with self.app.app_context():
            session = get_session()
            readings = list(
                session.scalars(
                    select(Reading).where(
                        Reading.home_id == self.home_id,
                        Reading.room_id == room["id"],
                    )
                )
            )
            rejection_events = list(
                session.scalars(
                    select(AuditLog).where(
                        AuditLog.home_id == self.home_id,
                        AuditLog.event_type == "reading.rejected",
                    )
                )
            )
        self.assertEqual(len(readings), 2)
        self.assertEqual(rejection_events, [])
        self.assertEqual(
            response.get_json()["created"][0]["measured_at"],
            "2023-06-10T00:00:00Z",
        )
        for imported in response.get_json()["created"]:
            self.assertTrue(imported["received_at"].endswith("Z"))
            received_at = datetime.fromisoformat(
                imported["received_at"].replace("Z", "+00:00")
            )
            self.assertLessEqual(
                abs((datetime.now(timezone.utc) - received_at).total_seconds()),
                2,
            )
        dashboard = self.client.get(
            f"/api/homes/{self.home_id}/dashboard"
        )
        self.assertEqual(dashboard.status_code, 200, dashboard.get_json())
        latest_reading = dashboard.get_json()["readings"][0]
        self.assertEqual(latest_reading["source"], "dataset")
        self.assertEqual(latest_reading["value"], 1100)

    def test_demo_replay_rate_limit_returns_429_after_ten_requests(self):
        room = self.create_room("Rate limited replay room")
        with self.client.session_transaction() as browser_session:
            user_id = browser_session["user_id"]
        with self.app.app_context():
            db = get_session()
            db.add(
                RateLimitBucket(
                    key=f"demo-replay:{self.home_id}:user:{user_id}",
                    window_started_at=datetime.now(timezone.utc),
                    count=10,
                )
            )
            db.commit()

        response = self.client.post(
            f"/api/homes/{self.home_id}/demo/replay",
            data={
                "room_id": room["id"],
                "limit": "1",
                "csv_file": (BytesIO(b"ts,CO2\n2023-01-01T00:00:00Z,500\n"), "data.csv"),
            },
            headers={"X-CSRF-Token": self.csrf},
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.get_json()["error"], "Replay rate limit exceeded.")

    def test_environmental_replay_without_co2_preserves_data_and_reports_duplicates(self):
        room = self.create_room("Bedroom")
        csv_content = (
            "timestamp,PM2.5 (ug/m3),Temperature (C),Unknown\n"
            "2024-06-10T00:00:00Z,12,-5,9\n"
            "2024-06-10T00:01:00Z,15,20,10\n"
        )

        def replay():
            return self.client.post(
                f"/api/homes/{self.home_id}/demo/replay",
                data={
                    "room_id": room["id"],
                    "limit": "10",
                    "shift_timestamps": "false",
                    "csv_file": (BytesIO(csv_content.encode()), "environment.csv"),
                },
                headers={"X-CSRF-Token": self.csrf},
                content_type="multipart/form-data",
            )

        response = replay()
        self.assertEqual(response.status_code, 201, response.get_json())
        payload = response.get_json()
        self.assertEqual(payload["source"], "environmental_csv")
        self.assertEqual(payload["imported"], 4)
        self.assertEqual(
            {parameter["code"] for parameter in payload["parameters"]},
            {"PM2_5", "TEMPERATURE"},
        )
        self.assertEqual(len(payload["review_columns"]), 1)
        self.assertEqual(payload["review_columns"][0]["column"], "Unknown")
        self.assertEqual(payload["duplicate_readings"], [])
        self.assertTrue(all(not result["created"] for result in payload["created"]))

        duplicate_response = replay()
        self.assertEqual(duplicate_response.status_code, 422)
        duplicate_payload = duplicate_response.get_json()
        self.assertEqual(duplicate_payload["imported"], 0)
        self.assertEqual(len(duplicate_payload["duplicate_readings"]), 4)
        self.assertIn("no new supported readings", duplicate_payload["error"])
        with self.app.app_context():
            readings = list(
                get_session().scalars(
                    select(Reading).where(
                        Reading.home_id == self.home_id,
                        Reading.room_id == room["id"],
                    )
                )
            )
        self.assertEqual(len(readings), 4)

    def test_environmental_replay_with_only_unsupported_columns_returns_review(self):
        room = self.create_room("Bedroom")
        csv_content = "timestamp,unknown\n2024-06-10T00:00:00Z,123\n"
        response = self.client.post(
            f"/api/homes/{self.home_id}/demo/replay",
            data={
                "room_id": room["id"],
                "limit": "10",
                "shift_timestamps": "true",
                "csv_file": (BytesIO(csv_content.encode()), "unsupported.csv"),
            },
            headers={"X-CSRF-Token": self.csrf},
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 422, response.get_json())
        self.assertEqual(response.get_json()["imported"], 0)
        self.assertEqual(response.get_json()["review_columns"][0]["column"], "unknown")

    def test_replay_rolls_back_readings_alerts_and_audit_if_later_row_fails(self):
        room = self.create_room("Bedroom")
        first_timestamp = datetime.now(timezone.utc) - timedelta(minutes=2)
        future_timestamp = datetime.now(timezone.utc) + timedelta(days=1)
        csv_content = (
            "ts,CO2,Valid_CO2,Loc\n"
            f"{first_timestamp.strftime('%Y-%m-%d %H:%M:%S')},1800,1,Bedroom\n"
            f"{future_timestamp.strftime('%Y-%m-%d %H:%M:%S')},1700,1,Bedroom\n"
        )

        response = self.client.post(
            f"/api/homes/{self.home_id}/demo/replay",
            data={
                "room_id": room["id"],
                "limit": "10",
                "shift_timestamps": "false",
                "csv_file": (BytesIO(csv_content.encode()), "failing-replay.csv"),
            },
            headers={"X-CSRF-Token": self.csrf},
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 400, response.get_json())
        self.assertIn("Failed on dataset row", response.get_json()["error"])
        self.assertIn("cannot be in the future", response.get_json()["error"])

        with self.app.app_context():
            session = get_session()
            self.assertEqual(
                list(
                    session.scalars(
                        select(Reading).where(
                            Reading.home_id == self.home_id,
                            Reading.room_id == room["id"],
                        )
                    )
                ),
                [],
            )
            self.assertEqual(
                list(
                    session.scalars(
                        select(Alert).where(
                            Alert.home_id == self.home_id,
                            Alert.room_id == room["id"],
                        )
                    )
                ),
                [],
            )
            reading_events = list(
                session.scalars(
                    select(AuditLog).where(
                        AuditLog.home_id == self.home_id,
                        AuditLog.event_type.in_(
                            ("reading.ingested", "alert.created")
                        ),
                    )
                )
            )
            self.assertEqual(reading_events, [])
            rejection_events = list(
                session.scalars(
                    select(AuditLog).where(
                        AuditLog.home_id == self.home_id,
                        AuditLog.event_type == "reading.rejected",
                    )
                )
            )
            self.assertEqual(len(rejection_events), 1)
            self.assertEqual(
                rejection_events[0].details_json,
                '{"reason":"invalid_reading","source":"dataset"}',
            )
            self.assertIsNotNone(rejection_events[0].actor_user_id)
            self.assertNotIn("1700", str(rejection_events))

    def test_successful_replay_stores_history_without_creating_live_alerts(self):
        room = self.create_room("Bedroom")
        start = datetime.now(timezone.utc) - timedelta(minutes=2)
        csv_content = (
            "ts,CO2,Valid_CO2,Loc\n"
            f"{start.strftime('%Y-%m-%d %H:%M:%S')},1800,1,Bedroom\n"
            f"{(start + timedelta(seconds=30)).strftime('%Y-%m-%d %H:%M:%S')},1700,1,Bedroom\n"
        )

        response = self.client.post(
            f"/api/homes/{self.home_id}/demo/replay",
            data={
                "room_id": room["id"],
                "limit": "10",
                "shift_timestamps": "false",
                "csv_file": (BytesIO(csv_content.encode()), "alert-replay.csv"),
            },
            headers={"X-CSRF-Token": self.csrf},
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 201, response.get_json())
        self.assertEqual(response.get_json()["imported"], 2)
        self.assertEqual(response.get_json()["created"][0]["created"], [])
        with self.app.app_context():
            session = get_session()
            readings = list(
                session.scalars(
                    select(Reading).where(
                        Reading.home_id == self.home_id,
                        Reading.room_id == room["id"],
                    )
                )
            )
            alerts = list(
                session.scalars(
                    select(Alert).where(
                        Alert.home_id == self.home_id,
                        Alert.room_id == room["id"],
                    )
                )
            )
            events = list(
                session.scalars(
                    select(AuditLog.entity_id).where(
                        AuditLog.home_id == self.home_id,
                        AuditLog.event_type == "reading.ingested",
                    )
                )
            )
        self.assertEqual(len(readings), 2)
        self.assertEqual(alerts, [])
        self.assertCountEqual(
            events,
            [str(reading.id) for reading in readings],
        )

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
        self.assertIn("Choose a CSV", missing_file.get_json()["error"])
