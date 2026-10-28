-- Example-only CO2 thresholds for rooms already present in dbo.rooms.
-- These values match local demo defaults; they are illustrative, not cited
-- health guidance. Review and replace them before any non-demo use.
SET XACT_ABORT ON;
BEGIN TRANSACTION;

INSERT INTO dbo.threshold_policies (
    home_id,
    room_id,
    metric_code,
    high_threshold,
    elevated_threshold,
    elevated_duration_seconds,
    rapid_rise_per_minute,
    all_clear_duration_seconds,
    max_reading_gap_seconds,
    effective_from,
    source_title,
    source_rationale,
    is_illustrative
)
SELECT
    r.home_id,
    r.room_id,
    N'CO2',
    1500.0,
    1000.0,
    300,
    200.0,
    300,
    120,
    TODATETIMEOFFSET(SYSUTCDATETIME(), '+00:00'),
    N'AirSense local demo defaults (illustrative)',
    N'Example configuration only; not a published health or safety limit.',
    1
FROM dbo.rooms AS r
WHERE EXISTS (
    SELECT 1
    FROM dbo.metrics AS m
    WHERE m.metric_code = N'CO2'
      AND m.is_active = 1
)
AND NOT EXISTS (
    SELECT 1
    FROM dbo.threshold_policies AS p
    WHERE p.home_id = r.home_id
      AND p.room_id = r.room_id
      AND p.metric_code = N'CO2'
      AND p.effective_to IS NULL
);

COMMIT TRANSACTION;