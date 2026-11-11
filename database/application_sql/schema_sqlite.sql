-- =============================================================================
-- AirSense - application schema (SQLite 3)                  schema_sqlite.sql
-- =============================================================================
-- The same 13 tables as schema.sql, for SQLite, which is the application's
-- default local database (instance/airsense.sqlite3). Matches the schema built
-- by the Alembic migrations (head 20261108_0008) at commit ce1a862.
--
-- NOT the Azure SQL scripts in database/migrations/ (separate, never run, not
-- used by the app). Run on an EMPTY database:
--     sqlite3 airsense_demo.db < schema_sqlite.sql
--
-- SQLite differences from schema.sql (PostgreSQL):
--   * INTEGER PRIMARY KEY auto-numbers instead of SERIAL.
--   * DATETIME / FLOAT / BOOLEAN / JSON are SQLite type names with flexible
--     storage (text, real, 0/1, text). The app stores UTC datetimes without a
--     time-zone marker.
--   * Foreign keys are only enforced when PRAGMA foreign_keys = ON is set on
--     each connection (the application does this). It is set below.
--   * CHECK constraints, UNIQUE, partial and expression indexes are supported
--     (SQLite 3.9+ for expression indexes).
-- =============================================================================

PRAGMA foreign_keys = ON;
BEGIN;

CREATE TABLE users (
    id                VARCHAR(36)  NOT NULL,
    email             VARCHAR(254) NOT NULL,
    display_name      VARCHAR(120) NOT NULL,
    password_hash     VARCHAR(256) NOT NULL,
    is_active         BOOLEAN      NOT NULL DEFAULT 1,
    created_at        DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    session_version   INTEGER      NOT NULL DEFAULT 0,
    email_verified_at DATETIME,
    PRIMARY KEY (id),
    UNIQUE (email)
);

CREATE TABLE homes (
    id   VARCHAR(64)  NOT NULL,
    name VARCHAR(120) NOT NULL,
    PRIMARY KEY (id)
);

CREATE TABLE home_memberships (
    home_id   VARCHAR(64) NOT NULL,
    user_id   VARCHAR(36) NOT NULL,
    role      VARCHAR(16) NOT NULL,
    joined_at DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (home_id, user_id),
    FOREIGN KEY (home_id) REFERENCES homes (id),
    FOREIGN KEY (user_id) REFERENCES users (id)
);
CREATE INDEX ix_home_memberships_home_id ON home_memberships (home_id);
CREATE INDEX ix_home_memberships_user_id ON home_memberships (user_id);

CREATE TABLE home_invitations (
    id          VARCHAR(36)  NOT NULL,
    home_id     VARCHAR(64)  NOT NULL,
    email       VARCHAR(254) NOT NULL,
    role        VARCHAR(16)  NOT NULL DEFAULT 'member',
    token_hash  VARCHAR(64)  NOT NULL,
    created_by  VARCHAR(36)  NOT NULL,
    created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at  DATETIME     NOT NULL,
    accepted_at DATETIME,
    PRIMARY KEY (id),
    UNIQUE (token_hash),
    FOREIGN KEY (home_id)    REFERENCES homes (id),
    FOREIGN KEY (created_by) REFERENCES users (id)
);

CREATE TABLE email_challenges (
    id                     VARCHAR(36)  NOT NULL,
    user_id                VARCHAR(36),
    email                  VARCHAR(254) NOT NULL,
    purpose                VARCHAR(32)  NOT NULL,
    otp_hash               VARCHAR(64)  NOT NULL,
    created_at             DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at             DATETIME     NOT NULL,
    last_sent_at           DATETIME     NOT NULL,
    attempts               INTEGER      NOT NULL DEFAULT 0,
    consumed_at            DATETIME,
    reset_token_hash       VARCHAR(64),
    reset_token_expires_at DATETIME,
    reset_token_used_at    DATETIME,
    PRIMARY KEY (id),
    CONSTRAINT uq_email_challenges_reset_token_hash UNIQUE (reset_token_hash),
    FOREIGN KEY (user_id) REFERENCES users (id)
);
CREATE INDEX ix_email_challenges_email   ON email_challenges (email);
CREATE INDEX ix_email_challenges_purpose ON email_challenges (purpose);

CREATE TABLE rooms (
    id                  VARCHAR(64)  NOT NULL,
    home_id             VARCHAR(64)  NOT NULL,
    name                VARCHAR(100) NOT NULL,
    ventilation         VARCHAR(80)  NOT NULL DEFAULT 'Not specified',
    ventilation_sources JSON         NOT NULL DEFAULT '[]',
    PRIMARY KEY (id),
    CONSTRAINT uq_rooms_home_name UNIQUE (home_id, name),
    FOREIGN KEY (home_id) REFERENCES homes (id)
);
CREATE UNIQUE INDEX uq_rooms_home_lower_name ON rooms (home_id, lower(name));

CREATE TABLE sensors (
    id                         VARCHAR(36)  NOT NULL,
    home_id                    VARCHAR(64)  NOT NULL,
    room_id                    VARCHAR(64)  NOT NULL,
    name                       VARCHAR(120) NOT NULL,
    key_hash                   VARCHAR(64)  NOT NULL,
    status                     VARCHAR(16)  NOT NULL DEFAULT 'active',
    reporting_interval_seconds INTEGER      NOT NULL DEFAULT 300,
    last_seen_at               DATETIME,
    created_at                 DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE (key_hash),
    CONSTRAINT ck_sensors_status CHECK (status IN ('active', 'revoked')),
    CONSTRAINT ck_sensors_reporting_interval
        CHECK (reporting_interval_seconds BETWEEN 30 AND 86400),
    FOREIGN KEY (home_id) REFERENCES homes (id),
    FOREIGN KEY (room_id) REFERENCES rooms (id)
);
CREATE INDEX ix_sensors_home_room ON sensors (home_id, room_id);

CREATE TABLE metrics (
    code VARCHAR(32) NOT NULL,
    name VARCHAR(80) NOT NULL,
    unit VARCHAR(24) NOT NULL,
    PRIMARY KEY (code)
);

CREATE TABLE air_readings (
    id          INTEGER     NOT NULL,
    home_id     VARCHAR(64) NOT NULL,
    room_id     VARCHAR(64) NOT NULL,
    metric_code VARCHAR(32) NOT NULL,
    value       FLOAT       NOT NULL,
    source      VARCHAR(24) NOT NULL,
    measured_at DATETIME    NOT NULL,
    sensor_id   VARCHAR(36),
    received_at DATETIME,
    PRIMARY KEY (id),
    CONSTRAINT uq_readings_home_room_metric_time
        UNIQUE (home_id, room_id, metric_code, measured_at),
    CONSTRAINT fk_air_readings_sensor_id_sensors
        FOREIGN KEY (sensor_id) REFERENCES sensors (id),
    FOREIGN KEY (home_id)     REFERENCES homes (id),
    FOREIGN KEY (room_id)     REFERENCES rooms (id),
    FOREIGN KEY (metric_code) REFERENCES metrics (code)
);
CREATE INDEX ix_readings_home_room_metric_time
    ON air_readings (home_id, room_id, metric_code, measured_at);

CREATE TABLE threshold_policies (
    id                         INTEGER     NOT NULL,
    home_id                    VARCHAR(64) NOT NULL,
    room_id                    VARCHAR(64) NOT NULL,
    metric_code                VARCHAR(32) NOT NULL,
    high_threshold             FLOAT       NOT NULL,
    elevated_threshold         FLOAT       NOT NULL,
    elevated_duration_seconds  INTEGER     NOT NULL,
    rapid_rise_per_minute      FLOAT       NOT NULL,
    all_clear_duration_seconds INTEGER     NOT NULL,
    max_reading_gap_seconds    INTEGER     NOT NULL,
    elevated_since             DATETIME,
    PRIMARY KEY (id),
    CONSTRAINT uq_threshold_policy_scope UNIQUE (home_id, room_id, metric_code),
    FOREIGN KEY (home_id)     REFERENCES homes (id),
    FOREIGN KEY (room_id)     REFERENCES rooms (id),
    FOREIGN KEY (metric_code) REFERENCES metrics (code)
);

CREATE TABLE air_alerts (
    id                     INTEGER     NOT NULL,
    home_id                VARCHAR(64) NOT NULL,
    room_id                VARCHAR(64) NOT NULL,
    metric_code            VARCHAR(32) NOT NULL,
    level                  VARCHAR(24) NOT NULL,
    status                 VARCHAR(24) NOT NULL,
    trigger_value          FLOAT       NOT NULL,
    threshold_value        FLOAT       NOT NULL,
    latest_value           FLOAT       NOT NULL,
    threshold_unit         VARCHAR(24) NOT NULL,
    clear_duration_seconds INTEGER     NOT NULL,
    below_threshold_since  DATETIME,
    created_at             DATETIME    NOT NULL,
    acknowledged_at        DATETIME,
    acknowledged_by        VARCHAR(120),
    all_clear_at           DATETIME,
    detail                 TEXT        NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT ck_alerts_level  CHECK (level IN ('high', 'elevated', 'rapid_rise')),
    CONSTRAINT ck_alerts_status CHECK (status IN ('active', 'acknowledged', 'all_clear')),
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
CREATE UNIQUE INDEX uq_open_alert_home_room_metric_level
    ON air_alerts (home_id, room_id, metric_code, level)
    WHERE status IN ('active', 'acknowledged');

CREATE TABLE audit_logs (
    id            INTEGER      NOT NULL,
    home_id       VARCHAR(64)  NOT NULL,
    actor_user_id VARCHAR(36),
    event_type    VARCHAR(80)  NOT NULL,
    entity_type   VARCHAR(40)  NOT NULL,
    entity_id     VARCHAR(64),
    details_json  TEXT         NOT NULL DEFAULT '{}',
    created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    FOREIGN KEY (home_id)       REFERENCES homes (id),
    FOREIGN KEY (actor_user_id) REFERENCES users (id)
);
CREATE INDEX ix_audit_home_created ON audit_logs (home_id, created_at);

CREATE TABLE rate_limit_buckets (
    "key"             VARCHAR(255) NOT NULL,
    window_started_at DATETIME     NOT NULL,
    count             INTEGER      NOT NULL DEFAULT 0,
    PRIMARY KEY ("key")
);

-- The application inserts the CO2 metric on start-up if it is missing.
INSERT INTO metrics (code, name, unit) VALUES ('CO2', 'Carbon dioxide', 'ppm');

COMMIT;
-- alembic_version (Alembic's own bookkeeping table) is not one of the 13 tables
-- and is not created here.