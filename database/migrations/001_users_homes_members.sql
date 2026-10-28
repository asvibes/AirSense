-- AirSense Azure SQL migration 001. Apply once, before the other numbered migrations.
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
SET ANSI_PADDING ON;
SET ANSI_WARNINGS ON;
SET ARITHABORT ON;
SET CONCAT_NULL_YIELDS_NULL ON;
SET XACT_ABORT ON;
BEGIN TRANSACTION;

CREATE TABLE dbo.roles (
    role_id SMALLINT IDENTITY(1,1) NOT NULL,
    role_code NVARCHAR(32) NOT NULL,
    display_name NVARCHAR(80) NOT NULL,
    CONSTRAINT PK_roles PRIMARY KEY (role_id),
    CONSTRAINT UQ_roles_role_code UNIQUE (role_code),
    CONSTRAINT CK_roles_role_code CHECK (
        role_code IN (N'standard_user', N'facility_manager', N'administrator')
    )
);

INSERT INTO dbo.roles (role_code, display_name)
VALUES
    (N'standard_user', N'Standard user'),
    (N'facility_manager', N'Facility manager'),
    (N'administrator', N'Administrator');

CREATE TABLE dbo.users (
    user_id UNIQUEIDENTIFIER NOT NULL
        CONSTRAINT DF_users_user_id DEFAULT NEWSEQUENTIALID(),
    email NVARCHAR(254) NOT NULL,
    display_name NVARCHAR(120) NOT NULL,
    password_hash NVARCHAR(255) NOT NULL,
    normalized_email AS LOWER(LTRIM(RTRIM(email))) PERSISTED,
    created_at DATETIMEOFFSET(0) NOT NULL
        CONSTRAINT DF_users_created_at DEFAULT TODATETIMEOFFSET(SYSUTCDATETIME(), '+00:00'),
    is_active BIT NOT NULL CONSTRAINT DF_users_is_active DEFAULT 1,
    CONSTRAINT PK_users PRIMARY KEY (user_id),
    CONSTRAINT CK_users_email_nonempty CHECK (LEN(LTRIM(RTRIM(email))) > 0),
    CONSTRAINT CK_users_display_name_nonempty CHECK (
        LEN(LTRIM(RTRIM(display_name))) > 0
    ),
    CONSTRAINT CK_users_password_hash_nonempty CHECK (
        LEN(LTRIM(RTRIM(password_hash))) > 0
    )
);

CREATE UNIQUE INDEX UX_users_normalized_email
    ON dbo.users (normalized_email);

CREATE TABLE dbo.homes (
    home_id UNIQUEIDENTIFIER NOT NULL
        CONSTRAINT DF_homes_home_id DEFAULT NEWSEQUENTIALID(),
    name NVARCHAR(120) NOT NULL,
    created_at DATETIMEOFFSET(0) NOT NULL
        CONSTRAINT DF_homes_created_at DEFAULT TODATETIMEOFFSET(SYSUTCDATETIME(), '+00:00'),
    CONSTRAINT PK_homes PRIMARY KEY (home_id),
    CONSTRAINT UQ_homes_home_id UNIQUE (home_id),
    CONSTRAINT CK_homes_name_nonempty CHECK (LEN(LTRIM(RTRIM(name))) > 0)
);

CREATE TABLE dbo.home_memberships (
    home_id UNIQUEIDENTIFIER NOT NULL,
    user_id UNIQUEIDENTIFIER NOT NULL,
    role_id SMALLINT NOT NULL,
    joined_at DATETIMEOFFSET(0) NOT NULL
        CONSTRAINT DF_home_memberships_joined_at
        DEFAULT TODATETIMEOFFSET(SYSUTCDATETIME(), '+00:00'),
    CONSTRAINT PK_home_memberships PRIMARY KEY (home_id, user_id),
    CONSTRAINT FK_home_memberships_home FOREIGN KEY (home_id)
        REFERENCES dbo.homes (home_id),
    CONSTRAINT FK_home_memberships_user FOREIGN KEY (user_id)
        REFERENCES dbo.users (user_id),
    CONSTRAINT FK_home_memberships_role FOREIGN KEY (role_id)
        REFERENCES dbo.roles (role_id)
);

CREATE INDEX IX_home_memberships_user
    ON dbo.home_memberships (user_id, home_id);

COMMIT TRANSACTION;