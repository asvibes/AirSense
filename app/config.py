import os
from pathlib import Path


def _database_url() -> str:
    value = os.environ.get("DATABASE_URL")
    if value:
        if value.startswith("postgres://"):
            return value.replace("postgres://", "postgresql+psycopg://", 1)
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+psycopg://", 1)
        return value

    database = Path(__file__).resolve().parent.parent / "instance" / "airsense.sqlite3"
    return f"sqlite:///{database.as_posix()}"


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "local-development-key-change-me")
    APP_ENV = os.environ.get("APP_ENV", "development")
    DEVICE_KEY_PEPPER = os.environ.get("AIRSENSE_DEVICE_KEY_PEPPER", "")
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "false").lower() == "true"
    PERMANENT_SESSION_LIFETIME = 60 * 60 * 24 * 14
    MAX_CONTENT_LENGTH = 2 * 1024 * 1024
    DATABASE_URL = _database_url()
    HIGH_THRESHOLD = float(os.environ.get("AIRSENSE_HIGH_THRESHOLD", "1500"))
    ELEVATED_THRESHOLD = float(os.environ.get("AIRSENSE_ELEVATED_THRESHOLD", "1000"))
    ELEVATED_DURATION_SECONDS = int(
        os.environ.get("AIRSENSE_ELEVATED_DURATION_SECONDS", "300")
    )
    RAPID_RISE_PER_MINUTE = float(
        os.environ.get("AIRSENSE_RAPID_RISE_PER_MINUTE", "200")
    )
    ALL_CLEAR_DURATION_SECONDS = int(
        os.environ.get("AIRSENSE_ALL_CLEAR_DURATION_SECONDS", "300")
    )
    MAX_READING_GAP_SECONDS = int(
        os.environ.get("AIRSENSE_MAX_READING_GAP_SECONDS", "120")
    )
    MAX_FUTURE_SECONDS = int(os.environ.get("AIRSENSE_MAX_FUTURE_SECONDS", "60"))
    AUTO_CREATE_SCHEMA = os.environ.get("AUTO_CREATE_SCHEMA", "true").lower() == "true"
    API_TOKEN = os.environ.get("AIRSENSE_API_TOKEN", "")
    REQUIRE_API_TOKEN = os.environ.get("REQUIRE_API_TOKEN", "false").lower() == "true"
