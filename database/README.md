# Azure SQL database scripts

These scripts define a proposed Azure SQL Server schema for the AirSense academic MVP. They are separate from the application's active Alembic/SQLAlchemy schema. The Flask application uses SQLite locally; PostgreSQL migration and test jobs passed in GitHub Actions on commit `0fe75da`, but no hosted PostgreSQL deployment is established. Applying these SQL Server scripts does not configure or migrate the Flask application.

## Prerequisites

- An Azure SQL Database (or compatible SQL Server instance).
- A database principal permitted to create tables, indexes, views, and triggers.
- `sqlcmd`, Azure Data Studio, or SQL Server Management Studio. The numbered migrations use `GO` batch separators in migrations 007 and 008, so execute them with a tool that recognizes `GO`.

## Apply order

Run each migration once, in numeric order, against the same target database:

1. `migrations/001_users_homes_members.sql`
2. `migrations/002_rooms_sensors.sql`
3. `migrations/003_metrics_thresholds.sql`
4. `migrations/004_readings.sql`
5. `migrations/005_alerts.sql`
6. `migrations/006_audit_log.sql`
7. `migrations/007_triggers_threshold_audit.sql`
8. `migrations/008_views_daily_coverage.sql`

Then apply `seed/metrics.sql`. Apply `seed/default_thresholds.sql` only after adding the demo home and rooms; it inserts illustrative policies for rooms that do not already have an active CO2 policy.

Example from the repository root using Microsoft Entra authentication:

```powershell
sqlcmd -S "tcp:<server>.database.windows.net,1433" -d "<database>" -G -i "database\migrations\001_users_homes_members.sql"
```

Repeat with each migration and seed file in the order above. Use a securely configured authentication method; do not put passwords in shell history or committed scripts.

## Schema contents

- Home-scoped users and memberships with role lookup.
- Rooms and sensors; device credentials are represented only by a unique SHA-256 hash (`sensor_key_hash`), never by a raw secret.
- Metric definitions and effective-dated room threshold policies with provenance fields.
- Timestamped readings and source labels (`device`, `dataset`, `simulated`).
- Alert lifecycle and a filtered unique index that prevents duplicate open alerts per home, room, metric, and level.
- Activity log and a trigger that audits threshold policy inserts, updates, and deletes.
- `vw_latest_room_readings` and `vw_daily_reading_coverage` reporting views.

The `queries/reading_transaction_example.sql` file demonstrates an atomic reading/high-alert insert. It is not a production ingestion implementation: it covers only the immediate high-threshold case, expects a registered sensor ID to be supplied, and does not authenticate the device. Production ingestion must enforce device authentication, authorization, validation, and all lifecycle rules in the application.

## Important limitations

- The threshold values in `seed/default_thresholds.sql` mirror local demo defaults and are illustrative, not published health guidance. Replace and document them before non-demo use.
- Azure SQL deployment, firewall configuration, secrets, backups, and Power BI connectivity are not configured by these scripts.
- `database/powerbi/airsense-analytics-report.html` is a standalone descriptive report generated from the explicitly synthetic `airsense-synthetic-readings.csv` dataset. Regenerate and verify it from the repository root with `python tools/generate_analytics_report.py` and `python tools/generate_analytics_report.py --check`.
- `database/powerbi/airsense-report.pbix` remains an empty placeholder. The HTML report satisfies the guide's "analytics report, as a file or a link" format, but it is not a Power BI report, has no live application/database connection, and is not evidence of an Azure analytics integration.
- These scripts are one-time migrations, not an idempotent migration runner. The numbered table-creation scripts fail if their objects already exist; the seed scripts only insert missing rows, and the view/trigger scripts use `CREATE OR ALTER`. The migrations shown contain no drop/reset/truncate operations, but they create and modify objects and must be applied only once, in order, to a separately selected SQL Server database after review. Back up the target and verify its identity before applying them. They are a distinct proposed schema, not a byte-for-byte representation of the active ORM schema: role representation, same-home composite relationships, threshold history/provenance, reading and alert constraints/links, audit table, and reporting objects differ.
