-- Seed the supported CO2 metric. Other metrics remain inactive until ingestion,
-- thresholds, UI, and validation are implemented for them.
SET XACT_ABORT ON;
BEGIN TRANSACTION;

INSERT INTO dbo.metrics (metric_code, display_name, unit, is_active)
SELECT N'CO2', N'Carbon dioxide', N'ppm', 1
WHERE NOT EXISTS (
    SELECT 1
    FROM dbo.metrics
    WHERE metric_code = N'CO2'
);

INSERT INTO dbo.metrics (metric_code, display_name, unit, is_active)
SELECT N'CO', N'Carbon monoxide', N'ppm', 0
WHERE NOT EXISTS (
    SELECT 1
    FROM dbo.metrics
    WHERE metric_code = N'CO'
);

INSERT INTO dbo.metrics (metric_code, display_name, unit, is_active)
SELECT N'NO2', N'Nitrogen dioxide', N'ppm', 0
WHERE NOT EXISTS (
    SELECT 1
    FROM dbo.metrics
    WHERE metric_code = N'NO2'
);

COMMIT TRANSACTION;