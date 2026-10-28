-- AirSense Azure SQL migration 008. Requires migrations 001-007.
SET XACT_ABORT ON;
BEGIN TRANSACTION;
GO

CREATE OR ALTER VIEW dbo.vw_latest_room_readings
AS
WITH ranked_readings AS (
    SELECT
        r.home_id,
        r.room_id,
        rm.name AS room_name,
        r.metric_code,
        m.display_name AS metric_name,
        m.unit,
        r.reading_id,
        r.sensor_id,
        r.value,
        r.source,
        r.measured_at,
        r.received_at,
        ROW_NUMBER() OVER (
            PARTITION BY r.home_id, r.room_id, r.metric_code
            ORDER BY r.measured_at DESC, r.reading_id DESC
        ) AS row_number
    FROM dbo.air_readings AS r
    INNER JOIN dbo.rooms AS rm
        ON rm.home_id = r.home_id
        AND rm.room_id = r.room_id
    INNER JOIN dbo.metrics AS m
        ON m.metric_code = r.metric_code
)
SELECT
    home_id,
    room_id,
    room_name,
    metric_code,
    metric_name,
    unit,
    reading_id,
    sensor_id,
    value,
    source,
    measured_at,
    received_at
FROM ranked_readings
WHERE row_number = 1;
GO

CREATE OR ALTER VIEW dbo.vw_daily_reading_coverage
AS
SELECT
    r.home_id,
    r.room_id,
    rm.name AS room_name,
    r.metric_code,
    m.display_name AS metric_name,
    m.unit,
    CONVERT(DATE, SWITCHOFFSET(r.measured_at, '+00:00')) AS reading_date_utc,
    COUNT_BIG(*) AS reading_count,
    MIN(r.value) AS minimum_value,
    MAX(r.value) AS maximum_value,
    AVG(CONVERT(DECIMAL(19,4), r.value)) AS average_value
FROM dbo.air_readings AS r
INNER JOIN dbo.rooms AS rm
    ON rm.home_id = r.home_id
    AND rm.room_id = r.room_id
INNER JOIN dbo.metrics AS m
    ON m.metric_code = r.metric_code
GROUP BY
    r.home_id,
    r.room_id,
    rm.name,
    r.metric_code,
    m.display_name,
    m.unit,
    CONVERT(DATE, SWITCHOFFSET(r.measured_at, '+00:00'));
GO

COMMIT TRANSACTION;
GO