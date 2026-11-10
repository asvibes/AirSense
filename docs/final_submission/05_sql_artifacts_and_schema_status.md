# SQL artifacts and schema status

## Two distinct database designs

The repository has two database tracks:

1. **Active application database:** SQLAlchemy models in `app/models/` with Alembic migrations in `migrations/versions/`. Local development defaults to SQLite.
2. **Proposed Azure SQL coursework target:** Numbered SQL Server scripts in `database/migrations/`, described by `database/README.md`.

The Azure SQL scripts are not called by Flask's Alembic configuration, are not the same schema as the active ORM, and do not prove an Azure SQL database was created or migrated. Do not run these SQL Server scripts against the local SQLite database.

## Existing SQL Server schema scripts

| Order | Repository file | Purpose (as declared/implemented in script) |
|---:|---|---|
| 1 | `database/migrations/001_users_homes_members.sql` | Roles, users, homes, and memberships |
| 2 | `database/migrations/002_rooms_sensors.sql` | Rooms and sensors |
| 3 | `database/migrations/003_metrics_thresholds.sql` | Metric definitions and threshold policies |
| 4 | `database/migrations/004_readings.sql` | Reading storage |
| 5 | `database/migrations/005_alerts.sql` | Alert storage and constraints |
| 6 | `database/migrations/006_audit_log.sql` | Activity/audit log |
| 7 | `database/migrations/007_triggers_threshold_audit.sql` | Threshold audit triggers |
| 8 | `database/migrations/008_views_daily_coverage.sql` | Latest-reading and daily-coverage views |

The declared seeds are `database/seed/metrics.sql` and `database/seed/default_thresholds.sql`. The README requires migrations in numeric order and notes that `GO` separators require a SQL Server-aware client. These scripts are one-time migrations, not a tested idempotent runner.

## Existing query example

`database/queries/reading_transaction_example.sql` demonstrates a SQL Server transaction inserting a reading and, for an immediate high-threshold case, a corresponding alert. It has a placeholder sensor ID and intentionally documents that it does **not** authenticate a device, implement the full application alert lifecycle, or replace the ingestion API. Review the script and configure a test database before any execution.

## Differences from the active application

| Topic | Active ORM/Alembic | Proposed SQL Server scripts |
|---|---|---|
| Roles | Home-scoped string values `owner` and `member` | Separate global role lookup with standard-user, facility-manager, administrator codes |
| Email challenges and rate limits | Active ORM models and migrations exist | Not represented as equivalent active Flask integrations in the SQL target |
| Threshold history | Current policy row per home/room/metric | SQL target describes effective-dated/provenance fields |
| Scope relationships | Several independent foreign keys; no same-home composite key in active schema | SQL target includes stronger composite same-home relationships |
| Reporting views | Dashboard/history query through application code | SQL target defines latest-reading and daily-coverage views |
| Runtime use | SQLite default; PostgreSQL URL support not integration-tested | Azure SQL files are not wired into the runtime |

The Azure SQL scripts should therefore be treated as a proposed design artifact needing review and reconciliation before use, not as the authoritative live schema.

## Completion status

- SQL Server scripts and a query example: **present in the repository**.
- Azure SQL deployment, schema application, and connectivity evidence: **not verified**.
- Migration test evidence: local SQLite migration tests only; no Azure SQL migration test is claimed.
- Backups, network rules, credentials, and production database identity: **not verified**.

See [database/README.md](../../database/README.md) for prerequisites and warnings, and [document 4](04_er_diagram_and_database_design.md) for the active ORM schema.
