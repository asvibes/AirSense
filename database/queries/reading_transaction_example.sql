-- Demonstration only: set @SensorId to a registered sensor and review the
-- threshold policy before running. The caller must authenticate the device;
-- this script is not an ingestion API or a replacement for alert evaluation.
SET XACT_ABORT ON;

DECLARE @SensorId UNIQUEIDENTIFIER = NULL;
DECLARE @Value DECIMAL(12,4) = 1600.0;
DECLARE @MeasuredAt DATETIMEOFFSET(3) =
    TODATETIMEOFFSET(SYSUTCDATETIME(), '+00:00');
DECLARE @HomeId UNIQUEIDENTIFIER;
DECLARE @RoomId UNIQUEIDENTIFIER;
DECLARE @SensorStatus NVARCHAR(16);
DECLARE @HighThreshold DECIMAL(12,4);
DECLARE @ClearDurationSeconds INT;
DECLARE @ThresholdUnit NVARCHAR(24);
DECLARE @ReadingId BIGINT;

IF @SensorId IS NULL
    THROW 51000, 'Set @SensorId to an existing registered sensor before running.', 1;

IF @Value < 0 OR @Value > 100000
    THROW 51001, 'The sample value is outside the supported demo range.', 1;

BEGIN TRY
    BEGIN TRANSACTION;

    SELECT
        @HomeId = s.home_id,
        @RoomId = s.room_id,
        @SensorStatus = s.status
    FROM dbo.sensors AS s WITH (UPDLOCK, HOLDLOCK)
    WHERE s.sensor_id = @SensorId;

    IF @HomeId IS NULL OR @SensorStatus <> N'active'
        THROW 51002, 'The sensor does not exist or is not active.', 1;

    SELECT TOP (1)
        @HighThreshold = p.high_threshold,
        @ClearDurationSeconds = p.all_clear_duration_seconds,
        @ThresholdUnit = m.unit
    FROM dbo.threshold_policies AS p
    INNER JOIN dbo.metrics AS m
        ON m.metric_code = p.metric_code
    WHERE p.home_id = @HomeId
      AND p.room_id = @RoomId
      AND p.metric_code = N'CO2'
      AND p.effective_from <= @MeasuredAt
      AND (p.effective_to IS NULL OR @MeasuredAt < p.effective_to)
    ORDER BY p.effective_from DESC;

    IF @HighThreshold IS NULL
        THROW 51003, 'No applicable CO2 threshold policy exists for this room.', 1;

    INSERT INTO dbo.air_readings (
        home_id,
        room_id,
        sensor_id,
        metric_code,
        value,
        source,
        measured_at
    )
    VALUES (
        @HomeId,
        @RoomId,
        @SensorId,
        N'CO2',
        @Value,
        N'device',
        @MeasuredAt
    );

    SET @ReadingId = CONVERT(BIGINT, SCOPE_IDENTITY());

    IF @Value >= @HighThreshold
       AND NOT EXISTS (
           SELECT 1
           FROM dbo.air_alerts AS a WITH (UPDLOCK, HOLDLOCK)
           WHERE a.home_id = @HomeId
             AND a.room_id = @RoomId
             AND a.metric_code = N'CO2'
             AND a.level = N'high'
             AND a.status IN (N'active', N'acknowledged')
       )
    BEGIN
        INSERT INTO dbo.air_alerts (
            home_id,
            room_id,
            metric_code,
            trigger_reading_id,
            level,
            status,
            trigger_value,
            threshold_value,
            latest_value,
            threshold_unit,
            clear_duration_seconds,
            created_at,
            detail
        )
        VALUES (
            @HomeId,
            @RoomId,
            N'CO2',
            @ReadingId,
            N'high',
            N'active',
            @Value,
            @HighThreshold,
            @Value,
            @ThresholdUnit,
            @ClearDurationSeconds,
            @MeasuredAt,
            N'Demonstration high-threshold alert created with the reading.'
        );
    END;

    COMMIT TRANSACTION;

    SELECT
        @ReadingId AS reading_id,
        @HomeId AS home_id,
        @RoomId AS room_id,
        @Value AS value,
        @MeasuredAt AS measured_at;
END TRY
BEGIN CATCH
    IF XACT_STATE() <> 0
        ROLLBACK TRANSACTION;
    THROW;
END CATCH;
