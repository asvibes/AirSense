-- AirSense Azure SQL migration 007. Requires migration 006.
SET XACT_ABORT ON;
BEGIN TRANSACTION;
GO

CREATE OR ALTER TRIGGER dbo.TR_threshold_policies_activity_log
ON dbo.threshold_policies
AFTER INSERT, UPDATE, DELETE
AS
BEGIN
    SET NOCOUNT ON;

    IF EXISTS (
        SELECT 1
        FROM dbo.threshold_policies AS earlier
        INNER JOIN dbo.threshold_policies AS later
            ON later.home_id = earlier.home_id
            AND later.room_id = earlier.room_id
            AND later.metric_code = earlier.metric_code
            AND earlier.policy_id < later.policy_id
        WHERE (earlier.effective_to IS NULL
               OR later.effective_from < earlier.effective_to)
          AND (later.effective_to IS NULL
               OR earlier.effective_from < later.effective_to)
    )
        THROW 51004, 'Threshold policy effective periods cannot overlap.', 1;

    INSERT INTO dbo.activity_logs (
        home_id,
        actor_user_id,
        action_type,
        target_type,
        target_id,
        outcome,
        details_json
    )
    SELECT
        COALESCE(i.home_id, d.home_id),
        COALESCE(i.updated_by, d.updated_by),
        CASE
            WHEN d.policy_id IS NULL THEN N'threshold.created'
            WHEN i.policy_id IS NULL THEN N'threshold.deleted'
            ELSE N'threshold.updated'
        END,
        N'threshold_policy',
        CONVERT(NVARCHAR(100), COALESCE(i.policy_id, d.policy_id)),
        N'success',
        (
            SELECT
                JSON_QUERY((
                    SELECT
                        d.high_threshold AS high_threshold,
                        d.elevated_threshold AS elevated_threshold,
                        d.rapid_rise_per_minute AS rapid_rise_per_minute,
                        d.effective_from AS effective_from,
                        d.effective_to AS effective_to,
                        d.source_title AS source_title,
                        d.is_illustrative AS is_illustrative
                    WHERE d.policy_id IS NOT NULL
                    FOR JSON PATH, WITHOUT_ARRAY_WRAPPER
                )) AS [old],
                JSON_QUERY((
                    SELECT
                        i.high_threshold AS high_threshold,
                        i.elevated_threshold AS elevated_threshold,
                        i.rapid_rise_per_minute AS rapid_rise_per_minute,
                        i.effective_from AS effective_from,
                        i.effective_to AS effective_to,
                        i.source_title AS source_title,
                        i.is_illustrative AS is_illustrative
                    WHERE i.policy_id IS NOT NULL
                    FOR JSON PATH, WITHOUT_ARRAY_WRAPPER
                )) AS [new]
            FOR JSON PATH, WITHOUT_ARRAY_WRAPPER
        )
    FROM inserted AS i
    FULL OUTER JOIN deleted AS d
        ON d.policy_id = i.policy_id;
END;
GO

COMMIT TRANSACTION;
GO