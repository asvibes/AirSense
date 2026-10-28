-- AirSense Azure SQL migration 004. Requires migrations 001-003.
SET XACT_ABORT ON;
BEGIN TRANSACTION;

CREATE TABLE dbo.air_readings (
    reading_id BIGINT IDENTITY(1,1) NOT NULL,
    home_id UNIQUEIDENTIFIER NOT NULL,
    room_id UNIQUEIDENTIFIER NOT NULL,
    sensor_id UNIQUEIDENTIFIER NULL,
    metric_code NVARCHAR(32) NOT NULL,
    value DECIMAL(12,4) NOT NULL,
    source NVARCHAR(24) NOT NULL,
    measured_at DATETIMEOFFSET(3) NOT NULL,
    received_at DATETIMEOFFSET(3) NOT NULL
        CONSTRAINT DF_air_readings_received_at
        DEFAULT TODATETIMEOFFSET(SYSUTCDATETIME(), '+00:00'),
    CONSTRAINT PK_air_readings PRIMARY KEY (reading_id),
    CONSTRAINT UQ_air_readings_home_room_metric_time
        UNIQUE (home_id, room_id, metric_code, measured_at),
    CONSTRAINT UQ_air_readings_scope
        UNIQUE (reading_id, home_id, room_id, metric_code),
    CONSTRAINT FK_air_readings_room FOREIGN KEY (home_id, room_id)
        REFERENCES dbo.rooms (home_id, room_id),
    CONSTRAINT FK_air_readings_sensor FOREIGN KEY (sensor_id, home_id, room_id)
        REFERENCES dbo.sensors (sensor_id, home_id, room_id),
    CONSTRAINT FK_air_readings_metric FOREIGN KEY (metric_code)
        REFERENCES dbo.metrics (metric_code),
    CONSTRAINT CK_air_readings_source CHECK (
        source IN (N'device', N'dataset', N'simulated')
    ),
    CONSTRAINT CK_air_readings_device_sensor CHECK (
        source <> N'device' OR sensor_id IS NOT NULL
    ),
    CONSTRAINT CK_air_readings_value CHECK (
        value >= -100000 AND value <= 100000
    ),
    CONSTRAINT CK_air_readings_time_order CHECK (received_at >= measured_at)
);

CREATE INDEX IX_air_readings_home_room_metric_time
    ON dbo.air_readings (home_id, room_id, metric_code, measured_at DESC)
    INCLUDE (value, source, sensor_id, received_at);

CREATE INDEX IX_air_readings_sensor_time
    ON dbo.air_readings (sensor_id, measured_at DESC)
    INCLUDE (home_id, room_id, metric_code, value, source, received_at)
    WHERE sensor_id IS NOT NULL;

COMMIT TRANSACTION;