-- =============================================================================
-- AirSense - application schema (PostgreSQL 16)                    schema.sql
-- =============================================================================
-- WHAT THIS IS
--   The relational schema of the AirSense Flask application: 13 tables, as
--   defined by the SQLAlchemy models in app/models/ and produced by the eight
--   Alembic migrations in migrations/versions/ (head: 20261108_0008).
--   Verified at repository commit ce1a862 by comparing this file with the
--   schema Alembic builds on PostgreSQL 16 (see database_sql_notes.md).
--
-- WHAT THIS IS NOT
--   * It is NOT the Azure SQL / SQL Server schema. That is a separate, proposed
--     design in database/migrations/001..008_*.sql. It has different table
--     and column names, was never run on Azure SQL, and is not used by the app.
--   * It is not a replacement for Alembic. The application and its tests use
--     Alembic (`python -m alembic upgrade head`). This script is a readable,
--     reviewable copy of the same schema for the RDBMS submission.
--
-- WHERE TO RUN IT
--   An EMPTY PostgreSQL database only, e.g.  psql -d airsense_demo -f schema.sql
--   Do not run it against a database already managed by Alembic (the tables
--   would already exist). SQLite (the app's local default) uses
--   schema_sqlite.sql instead; differences are listed at the end of this file.
--
-- DESIGN NOTES
--   * Application-generated text keys (homes.id, rooms.id, users.id, ...) are
--     VARCHAR, not UUID or serial numbers. Auto-numbered keys exist only on
--     air_readings, air_alerts, threshold_policies and audit_logs.
--   * Enumerated values (readings.source, memberships.role, email purpose) are
--     validated by the application, not by CHECK constraints. Only alert level,
--     alert status, sensor status and the sensor reporting interval have
--     database CHECKs.
--   * air_readings / air_alerts / threshold_policies / sensors carry both
--     home_id and room_id. The database checks each key exists, but it does not
--     enforce that the room belongs to that home (no composite foreign key).
--     The application guarantees this.
--   * Timestamps are TIMESTAMP WITH TIME ZONE; the app stores UTC.
-- =============================================================================

BEGIN;

-- ---------------------------------------------------------------------------
-- 1. Identity and access
-- ---------------------------------------------------------------------------

CREATE TABLE users (
    id                 VARCHAR(36)  NOT NULL,
    email              VARCHAR(254) NOT NULL,
    display_name       VARCHAR(120) NOT NULL,
    password_hash      VARCHAR(256) NOT NULL,          -- scrypt hash, never plaintext
    is_active          BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at         TIMESTAMPTZ  NOT NULL DEFAULT now(),
    session_version    INTEGER      NOT NULL DEFAULT 0, -- bumped to sign out other sessions
    email_verified_at  TIMESTAMPTZ,                     -- NULL = not verified
    CONSTRAINT users_pkey      PRIMARY KEY (id),
    CONSTRAINT users_email_key UNIQUE (email)
);

CREATE TABLE homes (
    id    VARCHAR(64)  NOT NULL,
    name  VARCHAR(120) NOT NULL,
    CONSTRAINT homes_pkey PRIMARY KEY (id)
);

-- Many-to-many between users and homes, with a role (application values:
-- 'owner' or 'member'). Composite primary key.
CREATE TABLE home_memberships (
    home_id    VARCHAR(64) NOT NULL,
    user_id    VARCHAR(36) NOT NULL,
    role       VARCHAR(16) NOT NULL,
    joined_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT home_memberships_pkey PRIMARY KEY (home_id, user_id),
    FOREIGN KEY (home_id) REFERENCES homes (id),
    FOREIGN KEY (user_id) REFERENCES users (id)
);
CREATE INDEX ix_home_memberships_home_id ON home_memberships (home_id);
CREATE INDEX ix_home_memberships_user_id ON home_memberships (user_id);

-- Invitation tokens are stored only as a hash (token_hash), single use.
CREATE TABLE home_invitations (
    id          VARCHAR(36)  NOT NULL,
    home_id     VARCHAR(64)  NOT NULL,
    email       VARCHAR(254) NOT NULL,
    role        VARCHAR(16)  NOT NULL DEFAULT 'member',
    token_hash  VARCHAR(64)  NOT NULL,
    created_by  VARCHAR(36)  NOT NULL,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),
    expires_at  TIMESTAMPTZ  NOT NULL,
    accepted_at TIMESTAMPTZ,
    CONSTRAINT home_invitations_pkey          PRIMARY KEY (id),
    CONSTRAINT home_invitations_token_hash_key UNIQUE (token_hash),
    FOREIGN KEY (home_id)    REFERENCES homes (id),
    FOREIGN KEY (created_by) REFERENCES users (id)
);

-- One-time email codes (purpose 'email_verification' or 'password_reset') and
-- the follow-on password-reset token. Only hashes are stored.
CREATE TABLE email_challenges (
    id                      VARCHAR(36)  NOT NULL,
    user_id                 VARCHAR(36),               -- NULL before the account exists
    email                   VARCHAR(254) NOT NULL,
    purpose                 VARCHAR(32)  NOT NULL,
    otp_hash                VARCHAR(64)  NOT NULL,
    created_at              TIMESTAMPTZ  NOT NULL DEFAULT now(),
    expires_at              TIMESTAMPTZ  NOT NULL,
    last_sent_at            TIMESTAMPTZ  NOT NULL,
    attempts                INTEGER      NOT NULL DEFAULT 0,
    consumed_at             TIMESTAMPTZ,
    reset_token_hash        VARCHAR(64),
    reset_token_expires_at  TIMESTAMPTZ,
    reset_token_used_at     TIMESTAMPTZ,
    CONSTRAINT email_challenges_pkey PRIMARY KEY (id),
    CONSTRAINT uq_email_challenges_reset_token_hash UNIQUE (reset_token_hash),
    FOREIGN KEY (user_id) REFERENCES users (id)
);
CREATE INDEX ix_email_challenges_email   ON email_challenges (email);
CREATE INDEX ix_email_challenges_purpose ON email_challenges (purpose);

-- ---------------------------------------------------------------------------
-- 2. Rooms and sensors
-- ---------------------------------------------------------------------------

CREATE TABLE rooms (
    id                  VARCHAR(64)  NOT NULL,
    home_id             VARCHAR(64)  NOT NULL,
    name                VARCHAR(100) NOT NULL,
    ventilation         VARCHAR(80)  NOT NULL DEFAULT 'Not specified',
    ventilation_sources JSON         NOT NULL DEFAULT '[]'::json,
    CONSTRAINT rooms_pkey PRIMARY KEY (id),
    CONSTRAINT uq_rooms_home_name UNIQUE (home_id, name),
    FOREIGN KEY (home_id) REFERENCES homes (id)
);
-- Room names are also unique per home ignoring letter case.
CREATE UNIQUE INDEX uq_rooms_home_lower_name ON rooms (home_id, lower(name));

-- The raw device key is never stored; key_hash is a peppered hash.
CREATE TABLE sensors (
    id                         VARCHAR(36)  NOT NULL,
    home_id                    VARCHAR(64)  NOT NULL,
    room_id                    VARCHAR(64)  NOT NULL,
    name                       VARCHAR(120) NOT NULL,
    key_hash                   VARCHAR(64)  NOT NULL,
    status                     VARCHAR(16)  NOT NULL DEFAULT 'active',
    reporting_interval_seconds INTEGER      NOT NULL DEFAULT 300,
    last_seen_at               TIMESTAMPTZ,
    created_at                 TIMESTAMPTZ  NOT NULL DEFAULT now(),
    CONSTRAINT sensors_pkey PRIMARY KEY (id),
    CONSTRAINT sensors_key_hash_key UNIQUE (key_hash),
    CONSTRAINT ck_sensors_status CHECK (status IN ('active', 'revoked')),
    CONSTRAINT ck_sensors_reporting_interval
        CHECK (reporting_interval_seconds BETWEEN 30 AND 86400),
    FOREIGN KEY (home_id) REFERENCES homes (id),
    FOREIGN KEY (room_id) REFERENCES rooms (id)
);
CREATE INDEX ix_sensors_home_room ON sensors (home_id, room_id);

-- ---------------------------------------------------------------------------
-- 3. Metrics, readings, thresholds, alerts
-- ---------------------------------------------------------------------------

-- Lookup table of measurable parameters (e.g. CO2 / ppm).
CREATE TABLE metrics (
    code  VARCHAR(32) NOT NULL,
    name  VARCHAR(80) NOT NULL,
    unit  VARCHAR(24) NOT NULL,
    CONSTRAINT metrics_pkey PRIMARY KEY (code)
);

-- source (application values): 'device', 'dataset' or 'simulated'.
-- sensor_id is NULL for dataset and simulated rows.
CREATE TABLE air_readings (
    id          SERIAL           NOT NULL,
    home_id     VARCHAR(64)      NOT NULL,
    room_id     VARCHAR(64)      NOT NULL,
    metric_code VARCHAR(32)      NOT NULL,
    value       DOUBLE PRECISION NOT NULL,
    source      VARCHAR(24)      NOT NULL,
    measured_at TIMESTAMPTZ      NOT NULL,
    sensor_id   VARCHAR(36),
    received_at TIMESTAMPTZ,                 -- server receive time (added in migration 0004)
    CONSTRAINT air_readings_pkey PRIMARY KEY (id),
    -- Duplicate readings (same home, room, metric and instant) are rejected.
    CONSTRAINT uq_readings_home_room_metric_time
        UNIQUE (home_id, room_id, metric_code, measured_at),
    FOREIGN KEY (home_id)     REFERENCES homes (id),
    FOREIGN KEY (room_id)     REFERENCES rooms (id),
    FOREIGN KEY (metric_code) REFERENCES metrics (code),
    CONSTRAINT fk_air_readings_sensor_id_sensors
        FOREIGN KEY (sensor_id) REFERENCES sensors (id)
);
CREATE INDEX ix_readings_home_room_metric_time
    ON air_readings (home_id, room_id, metric_code, measured_at);

-- One alert policy per home, room and metric.
CREATE TABLE threshold_policies (
    id                         SERIAL           NOT NULL,
    home_id                    VARCHAR(64)      NOT NULL,
    room_id                    VARCHAR(64)      NOT NULL,
    metric_code                VARCHAR(32)      NOT NULL,
    high_threshold             DOUBLE PRECISION NOT NULL,
    elevated_threshold         DOUBLE PRECISION NOT NULL,
    elevated_duration_seconds  INTEGER          NOT NULL,
    rapid_rise_per_minute      DOUBLE PRECISION NOT NULL,
    all_clear_duration_seconds INTEGER          NOT NULL,
    max_reading_gap_seconds    INTEGER          NOT NULL,
    elevated_since             TIMESTAMPTZ,
    CONSTRAINT threshold_policies_pkey PRIMARY KEY (id),
    CONSTRAINT uq_threshold_policy_scope UNIQUE (home_id, room_id, metric_code),
    FOREIGN KEY (home_id)     REFERENCES homes (id),
    FOREIGN KEY (room_id)     REFERENCES rooms (id),
    FOREIGN KEY (metric_code) REFERENCES metrics (code)
);

-- Alert lifecycle: active -> acknowledged -> all_clear (or active -> all_clear).
CREATE TABLE air_alerts (
    id                     SERIAL           NOT NULL,
    home_id                VARCHAR(64)      NOT NULL,
    room_id                VARCHAR(64)      NOT NULL,
    metric_code            VARCHAR(32)      NOT NULL,
    level                  VARCHAR(24)      NOT NULL,
    status                 VARCHAR(24)      NOT NULL,
    trigger_value          DOUBLE PRECISION NOT NULL,
    threshold_value        DOUBLE PRECISION NOT NULL,
    latest_value           DOUBLE PRECISION NOT NULL,
    threshold_unit         VARCHAR(24)      NOT NULL,
    clear_duration_seconds INTEGER          NOT NULL,
    below_threshold_since  TIMESTAMPTZ,
    created_at             TIMESTAMPTZ      NOT NULL,
    acknowledged_at        TIMESTAMPTZ,
    acknowledged_by        VARCHAR(120),
    all_clear_at           TIMESTAMPTZ,
    detail                 TEXT             NOT NULL,
    CONSTRAINT air_alerts_pkey PRIMARY KEY (id),
    CONSTRAINT ck_alerts_level
        CHECK (level IN ('high', 'elevated', 'rapid_rise')),
    CONSTRAINT ck_alerts_status
        CHECK (status IN ('active', 'acknowledged', 'all_clear')),
    -- The timestamp/user columns must agree with the status.
    CONSTRAINT ck_alerts_transition_metadata CHECK (
        (status = 'active' AND acknowledged_at IS NULL AND acknowledged_by IS NULL
                           AND all_clear_at IS NULL)
     OR (status = 'acknowledged' AND acknowledged_at IS NOT NULL
                           AND acknowledged_by IS NOT NULL AND all_clear_at IS NULL)
     OR (status = 'all_clear' AND all_clear_at IS NOT NULL
                           AND ((acknowledged_at IS NULL AND acknowledged_by IS NULL)
                             OR (acknowledged_at IS NOT NULL AND acknowledged_by IS NOT NULL)))),
    FOREIGN KEY (home_id)     REFERENCES homes (id),
    FOREIGN KEY (room_id)     REFERENCES rooms (id),
    FOREIGN KEY (metric_code) REFERENCES metrics (code)
);
CREATE INDEX ix_alerts_home_created_at ON air_alerts (home_id, created_at);
-- At most ONE open alert per home, room, metric and level (partial unique index).
CREATE UNIQUE INDEX uq_open_alert_home_room_metric_level
    ON air_alerts (home_id, room_id, metric_code, level)
    WHERE status IN ('active', 'acknowledged');

-- ---------------------------------------------------------------------------
-- 4. Platform tables
-- ---------------------------------------------------------------------------

-- Append-only record of security-relevant events (e.g. rejected device keys).
CREATE TABLE audit_logs (
    id            SERIAL       NOT NULL,
    home_id       VARCHAR(64)  NOT NULL,
    actor_user_id VARCHAR(36),                 -- NULL for device or system events
    event_type    VARCHAR(80)  NOT NULL,
    entity_type   VARCHAR(40)  NOT NULL,
    entity_id     VARCHAR(64),
    details_json  TEXT         NOT NULL DEFAULT '{}',
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
    CONSTRAINT audit_logs_pkey PRIMARY KEY (id),
    FOREIGN KEY (home_id)       REFERENCES homes (id),
    FOREIGN KEY (actor_user_id) REFERENCES users (id)
);
CREATE INDEX ix_audit_home_created ON audit_logs (home_id, created_at);

-- Counters behind the database-backed rate limiter (shared by all workers).
CREATE TABLE rate_limit_buckets (
    key               VARCHAR(255) NOT NULL,
    window_started_at TIMESTAMPTZ  NOT NULL,
    count             INTEGER      NOT NULL DEFAULT 0,
    CONSTRAINT rate_limit_buckets_pkey PRIMARY KEY (key)
);

-- ---------------------------------------------------------------------------
-- 5. Reference data the application creates itself
-- ---------------------------------------------------------------------------
-- app/db.py inserts the CO2 metric on start-up if it is missing. Other metrics
-- are created by the application the first time a reading for them arrives.
-- Only CO2 is inserted here; no demo homes, users or readings are created.

INSERT INTO metrics (code, name, unit) VALUES ('CO2', 'Carbon dioxide', 'ppm');

COMMIT;

-- =============================================================================
-- NOT INCLUDED (not part of the application)
--   * alembic_version: Alembic's bookkeeping table, not one of the 13 tables.
--   * Views, triggers, stored procedures, roles or grants. The application
--     defines none. (The separate Azure SQL scripts include two views and one
--     trigger; they were never run and are not used by the app.)
--   * Room photos: they are files on disk, not database rows.
--
-- TABLE SUMMARY (13)
--   users, homes, home_memberships, home_invitations, email_challenges,
--   rooms, sensors, metrics, air_readings, threshold_policies, air_alerts,
--   audit_logs, rate_limit_buckets
--
-- DIFFERENCES FROM THE SQLITE SCHEMA (schema_sqlite.sql)
--   * Auto-number keys: SERIAL here; INTEGER PRIMARY KEY in SQLite.
--   * Timestamps: TIMESTAMPTZ here; DATETIME (stored without zone) in SQLite.
--   * Floats: DOUBLE PRECISION here; FLOAT in SQLite.
--   * Booleans: BOOLEAN TRUE/FALSE here; integer 1/0 in SQLite.
--   * JSON column (rooms.ventilation_sources): JSON here; stored as text in SQLite.
--   * Foreign keys are enforced by default in PostgreSQL; in SQLite only when
--     PRAGMA foreign_keys = ON (the application turns it on per connection).
-- =============================================================================