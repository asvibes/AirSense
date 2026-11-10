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

## RDBMS rubric coverage review

This is a source review of the proposed SQL Server scripts, not a database execution or deployment test.

| Rubric requirement | Evidence in proposed SQL Server artifacts | Review status |
|---|---|---|
| At least five related tables | Migrations 001–006 define roles, users, homes, home memberships, rooms, sensors, metrics, threshold policies, air readings, air alerts, and activity logs. Foreign keys connect these entities. | Present in scripts (11 tables). |
| Primary keys, foreign keys, and constraints | Each created table declares a primary key; the scripts declare 17 foreign-key constraints, 30 check constraints, unique constraints/indexes, and defaults for relevant fields and states. | Present in scripts; not executed against Azure SQL. |
| Search-column indexes | The six table-creation scripts declare 13 explicit indexes covering normalized user email, memberships by user, sensor room/status, threshold policy scope/effective dates, readings by room/metric/time and sensor/time, alerts by home/time and room/status/time, and audit rows by home/time and actor/time. | Present in scripts. Index suitability/performance was not benchmarked. |
| Joins | `008_views_daily_coverage.sql` joins readings to rooms and metrics in both views; `reading_transaction_example.sql` joins threshold policies to metrics. | Present in scripts. |
| View | Migration 008 creates `vw_latest_room_readings` and `vw_daily_reading_coverage`. | Present in scripts. |
| Stored procedure or trigger | Migration 007 creates `TR_threshold_policies_activity_log`, which validates overlapping effective periods and writes activity records. | Trigger present; no stored procedure is defined. The rubric allows either. |
| Transaction | All eight migration scripts wrap changes in transactions; the query example uses `TRY/CATCH`, commits on success, and rolls back on error. | Present in scripts; transaction behavior has not been run on SQL Server/Azure SQL. |
| Third Normal Form | The artifacts separate core entity and lookup tables, but the repository contains no formal functional-dependency analysis or normalization test. | Not formally verified; do not claim a completed 3NF assessment. |
| Schema script and query hand-in | Numbered schema scripts, seed scripts, views/trigger, and a transaction example are under `database/`. | Files present as proposed artifacts; confirm with faculty whether these satisfy the required hand-in format. |

These SQL Server artifacts are not the active Flask ORM schema, are not connected to the application, and have not been applied to a verified Azure SQL database. The review establishes that relevant SQL constructs are present in source only.

## Differences from the active application

| Topic | Active ORM/Alembic | Proposed SQL Server scripts |
|---|---|---|
| Roles | Home-scoped string values `owner` and `member` | Separate global role lookup with standard-user, facility-manager, administrator codes |
| Email challenges and rate limits | Active ORM models and migrations exist | Not represented as equivalent active Flask integrations in the SQL target |
| Threshold history | Current policy row per home/room/metric | SQL target describes effective-dated/provenance fields |
| Scope relationships | Several independent foreign keys; no same-home composite key in active schema | SQL target includes stronger composite same-home relationships |
| Reporting views | Dashboard/history query through application code | SQL target defines latest-reading and daily-coverage views |
| Runtime use | SQLite default; PostgreSQL migrations and Python tests passed in CI on `0fe75da` | Azure SQL files are not wired into the runtime |

The Azure SQL scripts should therefore be treated as a proposed design artifact needing review and reconciliation before use, not as the authoritative live schema.

## Completion status

- SQL Server scripts and a query example: **present in the repository**.
- The SQL Server artifacts demonstrate related tables, keys/constraints, joins, a view, a trigger, and a transaction: **present in proposed scripts**.
- Formal verification of Third Normal Form against either schema: **not documented or independently verified**.
- Azure SQL deployment, schema application, and connectivity evidence: **not verified**.
- Migration test evidence: SQLite and PostgreSQL CI migrations passed; no Azure SQL migration test is claimed.
- Backups, network rules, credentials, and production database identity: **not verified**.

See [database/README.md](../../database/README.md) for prerequisites and warnings, and [document 4](04_er_diagram_and_database_design.md) for the active ORM schema.
