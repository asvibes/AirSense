-- AirSense Azure SQL migration 006. Requires migrations 001-005.
SET XACT_ABORT ON;
BEGIN TRANSACTION;

CREATE TABLE dbo.activity_logs (
    log_id BIGINT IDENTITY(1,1) NOT NULL,
    home_id UNIQUEIDENTIFIER NULL,
    actor_user_id UNIQUEIDENTIFIER NULL,
    action_type NVARCHAR(80) NOT NULL,
    target_type NVARCHAR(80) NOT NULL,
    target_id NVARCHAR(100) NULL,
    occurred_at DATETIMEOFFSET(0) NOT NULL
        CONSTRAINT DF_activity_logs_occurred_at
        DEFAULT TODATETIMEOFFSET(SYSUTCDATETIME(), '+00:00'),
    outcome NVARCHAR(24) NOT NULL,
    details_json NVARCHAR(MAX) NULL,
    CONSTRAINT PK_activity_logs PRIMARY KEY (log_id),
    CONSTRAINT FK_activity_logs_home FOREIGN KEY (home_id)
        REFERENCES dbo.homes (home_id),
    CONSTRAINT FK_activity_logs_actor FOREIGN KEY (actor_user_id)
        REFERENCES dbo.users (user_id),
    CONSTRAINT CK_activity_logs_action_nonempty CHECK (
        LEN(LTRIM(RTRIM(action_type))) > 0
    ),
    CONSTRAINT CK_activity_logs_target_nonempty CHECK (
        LEN(LTRIM(RTRIM(target_type))) > 0
    ),
    CONSTRAINT CK_activity_logs_outcome CHECK (
        outcome IN (N'success', N'denied', N'failure')
    ),
    CONSTRAINT CK_activity_logs_details_json CHECK (
        details_json IS NULL OR ISJSON(details_json) = 1
    )
);

CREATE INDEX IX_activity_logs_home_occurred_at
    ON dbo.activity_logs (home_id, occurred_at DESC)
    INCLUDE (actor_user_id, action_type, target_type, target_id, outcome);

CREATE INDEX IX_activity_logs_actor_occurred_at
    ON dbo.activity_logs (actor_user_id, occurred_at DESC)
    WHERE actor_user_id IS NOT NULL;

COMMIT TRANSACTION;