-- AirSense Azure SQL migration 005. Requires migrations 001-004.
SET XACT_ABORT ON;
BEGIN TRANSACTION;

CREATE TABLE dbo.air_alerts (
    alert_id BIGINT IDENTITY(1,1) NOT NULL,
    home_id UNIQUEIDENTIFIER NOT NULL,
    room_id UNIQUEIDENTIFIER NOT NULL,
    metric_code NVARCHAR(32) NOT NULL,
    trigger_reading_id BIGINT NULL,
    level NVARCHAR(24) NOT NULL,
    status NVARCHAR(24) NOT NULL
        CONSTRAINT DF_air_alerts_status DEFAULT N'active',
    trigger_value DECIMAL(12,4) NOT NULL,
    threshold_value DECIMAL(12,4) NOT NULL,
    latest_value DECIMAL(12,4) NOT NULL,
    threshold_unit NVARCHAR(24) NOT NULL,
    clear_duration_seconds INT NOT NULL,
    below_threshold_since DATETIMEOFFSET(0) NULL,
    created_at DATETIMEOFFSET(0) NOT NULL
        CONSTRAINT DF_air_alerts_created_at
        DEFAULT TODATETIMEOFFSET(SYSUTCDATETIME(), '+00:00'),
    acknowledged_at DATETIMEOFFSET(0) NULL,
    acknowledged_by_user_id UNIQUEIDENTIFIER NULL,
    acknowledged_by NVARCHAR(120) NULL,
    all_clear_at DATETIMEOFFSET(0) NULL,
    detail NVARCHAR(MAX) NOT NULL,
    CONSTRAINT PK_air_alerts PRIMARY KEY (alert_id),
    CONSTRAINT FK_air_alerts_room FOREIGN KEY (home_id, room_id)
        REFERENCES dbo.rooms (home_id, room_id),
    CONSTRAINT FK_air_alerts_metric FOREIGN KEY (metric_code)
        REFERENCES dbo.metrics (metric_code),
    CONSTRAINT FK_air_alerts_trigger_reading FOREIGN KEY (
        trigger_reading_id,
        home_id,
        room_id,
        metric_code
    )
        REFERENCES dbo.air_readings (
            reading_id,
            home_id,
            room_id,
            metric_code
        ),
    CONSTRAINT FK_air_alerts_acknowledged_user FOREIGN KEY (acknowledged_by_user_id)
        REFERENCES dbo.users (user_id),
    CONSTRAINT CK_air_alerts_level CHECK (
        level IN (N'high', N'elevated', N'rapid_rise')
    ),
    CONSTRAINT CK_air_alerts_status CHECK (
        status IN (N'active', N'acknowledged', N'all_clear')
    ),
    CONSTRAINT CK_air_alerts_clear_duration CHECK (clear_duration_seconds >= 0),
    CONSTRAINT CK_air_alerts_detail_nonempty CHECK (
        LEN(LTRIM(RTRIM(detail))) > 0
    ),
    CONSTRAINT CK_air_alerts_transition_metadata CHECK (
        (status = N'active'
            AND acknowledged_at IS NULL
            AND acknowledged_by_user_id IS NULL
            AND acknowledged_by IS NULL
            AND all_clear_at IS NULL)
        OR
        (status = N'acknowledged'
            AND acknowledged_at IS NOT NULL
            AND (acknowledged_by_user_id IS NOT NULL OR acknowledged_by IS NOT NULL)
            AND all_clear_at IS NULL)
        OR
        (status = N'all_clear'
            AND all_clear_at IS NOT NULL
            AND (
                (acknowledged_at IS NULL
                    AND acknowledged_by_user_id IS NULL
                    AND acknowledged_by IS NULL)
                OR
                (acknowledged_at IS NOT NULL
                    AND (acknowledged_by_user_id IS NOT NULL OR acknowledged_by IS NOT NULL))
            ))
    )
);

CREATE UNIQUE INDEX UX_air_alerts_open_home_room_metric_level
    ON dbo.air_alerts (home_id, room_id, metric_code, level)
    WHERE status IN (N'active', N'acknowledged');

CREATE INDEX IX_air_alerts_home_created_at
    ON dbo.air_alerts (home_id, created_at DESC)
    INCLUDE (room_id, metric_code, level, status, latest_value);

CREATE INDEX IX_air_alerts_room_status_created_at
    ON dbo.air_alerts (home_id, room_id, status, created_at DESC);

COMMIT TRANSACTION;