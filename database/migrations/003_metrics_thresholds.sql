-- AirSense Azure SQL migration 003. Requires migrations 001 and 002.
SET XACT_ABORT ON;
BEGIN TRANSACTION;

CREATE TABLE dbo.metrics (
    metric_code NVARCHAR(32) NOT NULL,
    display_name NVARCHAR(80) NOT NULL,
    unit NVARCHAR(24) NOT NULL,
    is_active BIT NOT NULL CONSTRAINT DF_metrics_is_active DEFAULT 1,
    CONSTRAINT PK_metrics PRIMARY KEY (metric_code),
    CONSTRAINT CK_metrics_code_nonempty CHECK (
        LEN(LTRIM(RTRIM(metric_code))) > 0
    ),
    CONSTRAINT CK_metrics_display_name_nonempty CHECK (
        LEN(LTRIM(RTRIM(display_name))) > 0
    ),
    CONSTRAINT CK_metrics_unit_nonempty CHECK (LEN(LTRIM(RTRIM(unit))) > 0)
);

CREATE TABLE dbo.threshold_policies (
    policy_id BIGINT IDENTITY(1,1) NOT NULL,
    home_id UNIQUEIDENTIFIER NOT NULL,
    room_id UNIQUEIDENTIFIER NOT NULL,
    metric_code NVARCHAR(32) NOT NULL,
    high_threshold DECIMAL(12,4) NOT NULL,
    elevated_threshold DECIMAL(12,4) NOT NULL,
    elevated_duration_seconds INT NOT NULL,
    rapid_rise_per_minute DECIMAL(12,4) NOT NULL,
    all_clear_duration_seconds INT NOT NULL,
    max_reading_gap_seconds INT NOT NULL,
    elevated_since DATETIMEOFFSET(0) NULL,
    effective_from DATETIMEOFFSET(0) NOT NULL
        CONSTRAINT DF_threshold_policies_effective_from
        DEFAULT TODATETIMEOFFSET(SYSUTCDATETIME(), '+00:00'),
    effective_to DATETIMEOFFSET(0) NULL,
    updated_by UNIQUEIDENTIFIER NULL,
    source_title NVARCHAR(240) NULL,
    source_url NVARCHAR(2048) NULL,
    source_rationale NVARCHAR(1000) NULL,
    source_reviewed_at DATETIMEOFFSET(0) NULL,
    is_illustrative BIT NOT NULL
        CONSTRAINT DF_threshold_policies_is_illustrative DEFAULT 1,
    CONSTRAINT PK_threshold_policies PRIMARY KEY (policy_id),
    CONSTRAINT FK_threshold_policies_room FOREIGN KEY (home_id, room_id)
        REFERENCES dbo.rooms (home_id, room_id),
    CONSTRAINT FK_threshold_policies_metric FOREIGN KEY (metric_code)
        REFERENCES dbo.metrics (metric_code),
    CONSTRAINT FK_threshold_policies_updated_by FOREIGN KEY (updated_by)
        REFERENCES dbo.users (user_id),
    CONSTRAINT CK_threshold_policies_values CHECK (
        elevated_threshold >= 0
        AND high_threshold > elevated_threshold
        AND rapid_rise_per_minute > 0
        AND elevated_duration_seconds >= 0
        AND all_clear_duration_seconds >= 0
        AND max_reading_gap_seconds > 0
    ),
    CONSTRAINT CK_threshold_policies_effective_range CHECK (
        effective_to IS NULL OR effective_to > effective_from
    ),
    CONSTRAINT CK_threshold_policies_source_url CHECK (
        source_url IS NULL OR source_url LIKE N'https://%'
    ),
    CONSTRAINT CK_threshold_policies_source_review CHECK (
        source_reviewed_at IS NULL OR source_title IS NOT NULL
    ),
    CONSTRAINT CK_threshold_policies_cited_source CHECK (
        is_illustrative = 1
        OR (
            source_title IS NOT NULL
            AND source_url IS NOT NULL
            AND source_rationale IS NOT NULL
            AND source_reviewed_at IS NOT NULL
        )
    )
);

CREATE UNIQUE INDEX UX_threshold_policies_scope_effective_from
    ON dbo.threshold_policies (home_id, room_id, metric_code, effective_from);

CREATE UNIQUE INDEX UX_threshold_policies_current
    ON dbo.threshold_policies (home_id, room_id, metric_code)
    WHERE effective_to IS NULL;

CREATE INDEX IX_threshold_policies_updated_by
    ON dbo.threshold_policies (updated_by, effective_from);

COMMIT TRANSACTION;