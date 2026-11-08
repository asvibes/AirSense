import os
import tempfile
import uuid
import unittest
from pathlib import Path
from unittest.mock import patch

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from app.db import get_session
from app.models.sensor import Sensor
from helpers import AirSenseTestCase


class DatabaseIntegrityTests(AirSenseTestCase):
    def test_sqlite_rejects_sensor_with_unknown_home_foreign_key(self):
        room = self.create_room()

        with self.app.app_context():
            session = get_session()
            session.add(
                Sensor(
                    id=str(uuid.uuid4()),
                    home_id="missing-home",
                    room_id=room["id"],
                    name="Invalid sensor",
                    key_hash="a" * 64,
                )
            )
            with self.assertRaises(IntegrityError):
                session.flush()
            session.rollback()

    def test_sensor_check_constraints_reject_invalid_values(self):
        room = self.create_room()

        with self.app.app_context():
            session = get_session()
            invalid_sensors = (
                Sensor(
                    id=str(uuid.uuid4()),
                    home_id=self.home_id,
                    room_id=room["id"],
                    name="Invalid status",
                    key_hash="b" * 64,
                    status="inactive",
                ),
                Sensor(
                    id=str(uuid.uuid4()),
                    home_id=self.home_id,
                    room_id=room["id"],
                    name="Invalid interval",
                    key_hash="c" * 64,
                    reporting_interval_seconds=29,
                ),
            )
            for sensor in invalid_sensors:
                session.add(sensor)
                with self.assertRaises(IntegrityError):
                    session.flush()
                session.rollback()

    def test_migration_server_defaults_are_present_in_model_schema(self):
        room_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())
        invitation_id = str(uuid.uuid4())
        sensor_id = str(uuid.uuid4())

        with self.app.extensions["airsense_engine"].begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO users (id, email, display_name, password_hash) "
                    "VALUES (:id, :email, :name, :password_hash)"
                ),
                {
                    "id": user_id,
                    "email": "defaults@example.test",
                    "name": "Defaults User",
                    "password_hash": "hashed",
                },
            )
            connection.execute(
                text("INSERT INTO rooms (id, home_id, name) VALUES (:id, :home_id, :name)"),
                {"id": room_id, "home_id": self.home_id, "name": "Defaults room"},
            )
            connection.execute(
                text(
                    "INSERT INTO home_invitations "
                    "(id, home_id, email, token_hash, created_by, expires_at) "
                    "VALUES (:id, :home_id, :email, :token_hash, :created_by, "
                    "CURRENT_TIMESTAMP)"
                ),
                {
                    "id": invitation_id,
                    "home_id": self.home_id,
                    "email": "invite@example.test",
                    "token_hash": "d" * 64,
                    "created_by": user_id,
                },
            )
            connection.execute(
                text(
                    "INSERT INTO sensors "
                    "(id, home_id, room_id, name, key_hash) "
                    "VALUES (:id, :home_id, :room_id, :name, :key_hash)"
                ),
                {
                    "id": sensor_id,
                    "home_id": self.home_id,
                    "room_id": room_id,
                    "name": "Defaults sensor",
                    "key_hash": "e" * 64,
                },
            )
            connection.execute(
                text(
                    "INSERT INTO audit_logs "
                    "(home_id, event_type, entity_type) "
                    "VALUES (:home_id, :event_type, :entity_type)"
                ),
                {
                    "home_id": self.home_id,
                    "event_type": "test.defaults",
                    "entity_type": "test",
                },
            )

        with self.app.extensions["airsense_engine"].connect() as connection:
            self.assertEqual(
                connection.execute(
                    text("SELECT is_active FROM users WHERE id = :id"), {"id": user_id}
                ).scalar_one(),
                1,
            )
            self.assertEqual(
                connection.execute(
                    text(
                        "SELECT role FROM home_invitations WHERE id = :id"
                    ),
                    {"id": invitation_id},
                ).scalar_one(),
                "member",
            )
            self.assertEqual(
                connection.execute(
                    text("SELECT ventilation_sources FROM rooms WHERE id = :id"),
                    {"id": room_id},
                ).scalar_one(),
                "[]",
            )
            self.assertEqual(
                connection.execute(
                    text(
                        "SELECT status, reporting_interval_seconds FROM sensors "
                        "WHERE id = :id"
                    ),
                    {"id": sensor_id},
                ).one(),
                ("active", 300),
            )
            self.assertEqual(
                connection.execute(
                    text(
                        "SELECT details_json FROM audit_logs "
                        "WHERE event_type = 'test.defaults'"
                    )
                ).scalar_one(),
                "{}",
            )


class ReadingReceivedAtMigrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repository_root = Path(__file__).resolve().parents[1]

    def _upgrade(self, database_path, revision):
        config = Config(str(self.repository_root / "alembic.ini"))
        config.set_main_option(
            "script_location", str(self.repository_root / "migrations")
        )
        database_url = f"sqlite:///{database_path.as_posix()}"
        with patch.dict(os.environ, {"DATABASE_URL": database_url}):
            command.upgrade(config, revision)

    def _downgrade(self, database_path, revision):
        config = Config(str(self.repository_root / "alembic.ini"))
        config.set_main_option(
            "script_location", str(self.repository_root / "migrations")
        )
        database_url = f"sqlite:///{database_path.as_posix()}"
        with patch.dict(os.environ, {"DATABASE_URL": database_url}):
            command.downgrade(config, revision)

    def test_fresh_database_migrates_with_nullable_received_at(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "fresh.sqlite3"
            self._upgrade(database_path, "head")

            engine = create_engine(f"sqlite:///{database_path.as_posix()}")
            try:
                columns = {
                    column["name"]: column
                    for column in inspect(engine).get_columns("air_readings")
                }
                self.assertIn("received_at", columns)
                self.assertTrue(columns["received_at"]["nullable"])
            finally:
                engine.dispose()

    def test_upgrade_from_20261028_0003_preserves_existing_readings_as_unknown(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "upgrade.sqlite3"
            self._upgrade(database_path, "20261028_0003")

            engine = create_engine(f"sqlite:///{database_path.as_posix()}")
            try:
                with engine.begin() as connection:
                    connection.execute(
                        text("INSERT INTO homes (id, name) VALUES ('home-1', 'Home')")
                    )
                    connection.execute(
                        text(
                            "INSERT INTO rooms "
                            "(id, home_id, name, ventilation, ventilation_sources) "
                            "VALUES ('room-1', 'home-1', 'Room', "
                            "'Not specified', '[\"Not specified\"]')"
                        )
                    )
                    connection.execute(
                        text(
                            "INSERT INTO air_readings "
                            "(home_id, room_id, metric_code, value, source, measured_at) "
                            "VALUES ('home-1', 'room-1', 'CO2', 700, 'simulated', "
                            "'2026-11-05 10:00:00')"
                        )
                    )

                self._upgrade(database_path, "head")
                with engine.connect() as connection:
                    reading = connection.execute(
                        text(
                            "SELECT measured_at, received_at FROM air_readings "
                            "WHERE home_id = 'home-1'"
                        )
                    ).one()
                self.assertEqual(reading.measured_at, "2026-11-05 10:00:00")
                self.assertIsNone(reading.received_at)
            finally:
                engine.dispose()


class EmailVerificationStateMigrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repository_root = Path(__file__).resolve().parents[1]

    def _upgrade(self, database_path, revision):
        config = Config(str(self.repository_root / "alembic.ini"))
        config.set_main_option(
            "script_location", str(self.repository_root / "migrations")
        )
        database_url = f"sqlite:///{database_path.as_posix()}"
        with patch.dict(os.environ, {"DATABASE_URL": database_url}):
            command.upgrade(config, revision)

    def _downgrade(self, database_path, revision):
        config = Config(str(self.repository_root / "alembic.ini"))
        config.set_main_option(
            "script_location", str(self.repository_root / "migrations")
        )
        database_url = f"sqlite:///{database_path.as_posix()}"
        with patch.dict(os.environ, {"DATABASE_URL": database_url}):
            command.downgrade(config, revision)

    def test_active_users_are_backfilled_without_reactivating_inactive_users(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "email-verification.sqlite3"
            self._upgrade(database_path, "20261108_0007")
            engine = create_engine(f"sqlite:///{database_path.as_posix()}")
            try:
                with engine.begin() as connection:
                    connection.execute(
                        text(
                            "INSERT INTO users "
                            "(id, email, display_name, password_hash, is_active) "
                            "VALUES (:active_id, :active_email, 'Active', 'hash', 1), "
                            "(:inactive_id, :inactive_email, 'Inactive', 'hash', 0)"
                        ),
                        {
                            "active_id": str(uuid.uuid4()),
                            "active_email": "migration-active@example.test",
                            "inactive_id": str(uuid.uuid4()),
                            "inactive_email": "migration-inactive@example.test",
                        },
                    )
                self._upgrade(database_path, "20261108_0008")
                with engine.connect() as connection:
                    rows = connection.execute(
                        text(
                            "SELECT email, is_active, email_verified_at "
                            "FROM users WHERE email LIKE 'migration-%' "
                            "ORDER BY email"
                        )
                    ).all()
                    by_email = {row.email: row for row in rows}
                    self.assertEqual(len(by_email), 2)
                    self.assertEqual(
                        by_email["migration-inactive@example.test"].is_active, 0
                    )
                    self.assertIsNone(
                        by_email["migration-inactive@example.test"].email_verified_at
                    )
                    self.assertEqual(
                        by_email["migration-active@example.test"].is_active, 1
                    )
                    self.assertIsNotNone(
                        by_email["migration-active@example.test"].email_verified_at
                    )

                self._downgrade(database_path, "20261108_0007")
                self.assertNotIn(
                    "email_verified_at",
                    {column["name"] for column in inspect(engine).get_columns("users")},
                )
            finally:
                engine.dispose()

    def test_downgrade_and_reupgrade_received_at_on_disposable_database(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "downgrade-upgrade.sqlite3"
            self._upgrade(database_path, "head")

            engine = create_engine(f"sqlite:///{database_path.as_posix()}")
            try:
                with engine.begin() as connection:
                    connection.execute(
                        text("INSERT INTO homes (id, name) VALUES ('home-1', 'Home')")
                    )
                    connection.execute(
                        text(
                            "INSERT INTO rooms "
                            "(id, home_id, name, ventilation, ventilation_sources) "
                            "VALUES ('room-1', 'home-1', 'Room', "
                            "'Not specified', '[\"Not specified\"]')"
                        )
                    )
                    connection.execute(
                        text(
                            "INSERT INTO air_readings "
                            "(home_id, room_id, metric_code, value, source, measured_at, "
                            "received_at) VALUES ('home-1', 'room-1', 'CO2', 700, "
                            "'simulated', '2026-11-05 10:00:00', "
                            "'2026-11-05 10:01:00')"
                        )
                    )

                self._downgrade(database_path, "20261028_0003")
                with engine.connect() as connection:
                    columns = {
                        column["name"]
                        for column in inspect(connection).get_columns("air_readings")
                    }
                    reading = connection.execute(
                        text(
                            "SELECT measured_at, value FROM air_readings "
                            "WHERE home_id = 'home-1'"
                        )
                    ).one()
                self.assertNotIn("received_at", columns)
                self.assertEqual(reading.measured_at, "2026-11-05 10:00:00")
                self.assertEqual(reading.value, 700)

                self._upgrade(database_path, "head")
                with engine.connect() as connection:
                    received_at = connection.execute(
                        text(
                            "SELECT received_at FROM air_readings "
                            "WHERE home_id = 'home-1'"
                        )
                    ).scalar_one()
                self.assertIsNone(received_at)
            finally:
                engine.dispose()
