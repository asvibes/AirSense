-- AirSense Azure SQL migration 002. Requires migration 001.
SET XACT_ABORT ON;
BEGIN TRANSACTION;

CREATE TABLE dbo.rooms (
    room_id UNIQUEIDENTIFIER NOT NULL
        CONSTRAINT DF_rooms_room_id DEFAULT NEWSEQUENTIALID(),
    home_id UNIQUEIDENTIFIER NOT NULL,
    name NVARCHAR(100) NOT NULL,
    location_label NVARCHAR(160) NULL,
    created_at DATETIMEOFFSET(0) NOT NULL
        CONSTRAINT DF_rooms_created_at DEFAULT TODATETIMEOFFSET(SYSUTCDATETIME(), '+00:00'),
    is_active BIT NOT NULL CONSTRAINT DF_rooms_is_active DEFAULT 1,
    CONSTRAINT PK_rooms PRIMARY KEY (room_id),
    CONSTRAINT UQ_rooms_home_room UNIQUE (home_id, room_id),
    CONSTRAINT UQ_rooms_home_name UNIQUE (home_id, name),
    CONSTRAINT FK_rooms_home FOREIGN KEY (home_id)
        REFERENCES dbo.homes (home_id),
    CONSTRAINT CK_rooms_name_nonempty CHECK (LEN(LTRIM(RTRIM(name))) > 0)
);

CREATE TABLE dbo.sensors (
    sensor_id UNIQUEIDENTIFIER NOT NULL
        CONSTRAINT DF_sensors_sensor_id DEFAULT NEWSEQUENTIALID(),
    home_id UNIQUEIDENTIFIER NOT NULL,
    room_id UNIQUEIDENTIFIER NOT NULL,
    sensor_key_hash VARBINARY(32) NOT NULL,
    sensor_type NVARCHAR(80) NOT NULL,
    status NVARCHAR(16) NOT NULL
        CONSTRAINT DF_sensors_status DEFAULT N'active',
    created_at DATETIMEOFFSET(0) NOT NULL
        CONSTRAINT DF_sensors_created_at DEFAULT TODATETIMEOFFSET(SYSUTCDATETIME(), '+00:00'),
    last_seen_at DATETIMEOFFSET(0) NULL,
    CONSTRAINT PK_sensors PRIMARY KEY (sensor_id),
    CONSTRAINT UQ_sensors_key_hash UNIQUE (sensor_key_hash),
    CONSTRAINT UQ_sensors_scope UNIQUE (sensor_id, home_id, room_id),
    CONSTRAINT FK_sensors_room FOREIGN KEY (home_id, room_id)
        REFERENCES dbo.rooms (home_id, room_id),
    CONSTRAINT CK_sensors_key_hash_length CHECK (DATALENGTH(sensor_key_hash) = 32),
    CONSTRAINT CK_sensors_type_nonempty CHECK (
        LEN(LTRIM(RTRIM(sensor_type))) > 0
    ),
    CONSTRAINT CK_sensors_status CHECK (
        status IN (N'active', N'inactive', N'revoked')
    )
);

CREATE INDEX IX_sensors_room_status
    ON dbo.sensors (home_id, room_id, status);

COMMIT TRANSACTION;