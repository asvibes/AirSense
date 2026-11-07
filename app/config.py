import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

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
    MAX_CONTENT_LENGTH = 17 * 1024 * 1024
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
    AUTO_CREATE_SCHEMA = os.environ.get("AUTO_CREATE_SCHEMA", "false").lower() == "true"
    API_TOKEN = os.environ.get("AIRSENSE_API_TOKEN", "")
    REQUIRE_API_TOKEN = os.environ.get("REQUIRE_API_TOKEN", "false").lower() == "true"
    BREVO_API_KEY = os.environ.get("BREVO_API_KEY", "")
    MAIL_DEFAULT_SENDER = os.environ.get(
        "MAIL_DEFAULT_SENDER", "noreply.projecthub.mail@gmail.com"
    )
    MAIL_DEFAULT_SENDER_NAME = os.environ.get("MAIL_DEFAULT_SENDER_NAME", "AirSense")
    PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "")
    EMAIL_VERIFICATION_REQUIRED = (
        os.environ.get("EMAIL_VERIFICATION_REQUIRED", "true").lower() == "true"
    )
    OTP_EXPIRY_SECONDS = 10 * 60
    OTP_RESEND_COOLDOWN_SECONDS = 60
    OTP_MAX_ATTEMPTS = 5
