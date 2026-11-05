# AirSense data model

## Status

This document separates the **active local SQLAlchemy/Alembic schema** from the **proposed academic/cloud target**. The active schema is defined by `app/models/` and `migrations/versions/`. The Azure SQL scripts under `database/migrations/` are a separate target and are not applied by the Flask app.

The local database defaults to SQLite. Application SQLite connections enable foreign-key enforcement. PostgreSQL URL support exists, but this document does not claim PostgreSQL migration or integration testing has passed.

The active SQLite database was verified at Alembic revision `20261105_0004` on 2026-11-05. It contains 11 application tables plus Alembic's `alembic_version` table. SQLite integrity and foreign-key checks passed, and current application-table row counts match the preserved pre-`received_at` backup. The migration chain has one head: `20261027_0001` → `20261028_0002` → `20261028_0003` → `20261105_0004`.

## Active ORM schema

| Table | Active columns | Keys, constraints, and indexes |
|---|---|---|
| `homes` | `id`, `name` | PK `id`; no home name uniqueness constraint. |
| `users` | `id`, `email`, `display_name`, `password_hash`, `is_active`, `created_at` | PK `id`; unique, non-null `email`; `is_active` server default true; created time server default. Password contains a Werkzeug scrypt hash, not the raw password. |
| `home_memberships` | `home_id`, `user_id`, `role`, `joined_at` | Composite PK `(home_id, user_id)`; FKs to `homes.id` and `users.id`; indexes on both FK columns. `role` is used as `owner` or `member` by the app; no role CHECK constraint. |
| `home_invitations` | `id`, `home_id`, `email`, `role`, `token_hash`, `created_by`, `created_at`, `expires_at`, `accepted_at` | PK `id`; FKs `home_id`→`homes.id`, `created_by`→`users.id`; unique `token_hash`; default role `member`; token is stored hashed. |
| `rooms` | `id`, `home_id`, `name`, `ventilation`, `ventilation_sources` | PK `id`; FK `home_id`→`homes.id`; unique `(home_id, name)` and unique functional index `(home_id, lower(name))`; `ventilation_sources` is non-null JSON with server default `[]`. |
| `sensors` | `id`, `home_id`, `room_id`, `name`, `key_hash`, `status`, `reporting_interval_seconds`, `last_seen_at`, `created_at` | PK `id`; FKs `home_id`→`homes.id`, `room_id`→`rooms.id`; unique non-null `key_hash`; index `(home_id, room_id)`; checks status in `active/revoked` and interval from 30 through 86400 seconds; defaults active and 300 seconds. |
| `metrics` | `code`, `name`, `unit` | PK `code`; no metric-specific value-range constraint. |
| `threshold_policies` | `id`, `home_id`, `room_id`, `metric_code`, `high_threshold`, `elevated_threshold`, `elevated_duration_seconds`, `rapid_rise_per_minute`, `all_clear_duration_seconds`, `max_reading_gap_seconds`, `elevated_since` | PK `id`; FKs to home, room, metric; unique `(home_id, room_id, metric_code)`. No effective date/history or `updated_by` column. |
| `air_readings` | `id`, `home_id`, `room_id`, `sensor_id`, `metric_code`, `value`, `source`, `measured_at`, `received_at` | PK `id`; FKs to home, room, nullable sensor, metric; unique `(home_id, room_id, metric_code, measured_at)`; index on the same scope ending in `measured_at`. `received_at` is nullable for legacy rows and is set by the shared ingestion service for new readings; source/value are not guarded by DB CHECK constraints. |
| `air_alerts` | `id`, `home_id`, `room_id`, `metric_code`, `level`, `status`, `trigger_value`, `threshold_value`, `latest_value`, `threshold_unit`, `clear_duration_seconds`, `below_threshold_since`, `created_at`, `acknowledged_at`, `acknowledged_by`, `all_clear_at`, `detail` | PK `id`; FKs to home, room, metric; checks for valid level/status and transition metadata; filtered unique index on `(home_id, room_id, metric_code, level)` while status is active/acknowledged; index `(home_id, created_at)`. No sensor/reading FK or user FK for `acknowledged_by`; it stores a display name. |
| `audit_logs` | `id`, `home_id`, `actor_user_id`, `event_type`, `entity_type`, `entity_id`, `details_json`, `created_at` | PK `id`; FK `home_id`→`homes.id`, nullable FK `actor_user_id`→`users.id`; index `(home_id, created_at)`; non-null JSON text details default `{}`. |

Model definitions are in `app/models/{home,user,room,sensor,metric,threshold,reading,alert,audit}.py`; migration history is in `migrations/versions/`. The application creates the CO₂ metric if missing when schema auto-creation is enabled; normal local setup uses Alembic.

### Relationship and integrity caveats

- `sensors`, `air_readings`, `threshold_policies`, and `air_alerts` each store both home and room IDs, but their independent FKs do not enforce that the room belongs to the same home ID. `air_readings.sensor_id` is independently linked to a sensor and does not enforce that the sensor has the same home, room, or metric scope as the reading.
- Same-home consistency is checked by application query/ingestion paths, not by composite database constraints. Read-only checks of the current local data found no home/room mismatches in sensors, readings, policies, or alerts; this does not prevent future direct-SQL inconsistencies.
- Alert rows identify home, room, and metric but do not FK-link the triggering sensor or reading.
- `received_at` records server UTC time when an individual reading enters the shared ingestion service. Existing readings are not backfilled, so their receipt time remains unknown (`NULL`).
- Threshold rows are current policies, not effective-dated versions. Alerts snapshot key threshold values used for lifecycle evaluation.
- SQLite tests verify selected FK/check/default behavior, a full API-level workflow, and DALTON batch rollback after a later-row validation failure. They do not prove every normalization invariant or forced database-failure rollback in every individual ingestion path.

## Query patterns and indexes actually present

- History queries filter `air_readings` by home and bounded `measured_at`, optionally room and metric; the composite history index begins with home/room/metric/time. CSV uses the same authorization and bounded query.
- Dashboard/alert retrieval filters by home; `air_alerts(home_id, created_at)` and `audit_logs(home_id, created_at)` support common listing order/filtering.
- Sensor list queries filter by home; `sensors(home_id, room_id)` supports home/room lookup.
- Membership has indexes on `home_id` and `user_id`.
- The active Alembic schema does not define the proposed `vw_latest_room_readings` or a stored procedure/trigger. Separate Azure SQL scripts define reporting views and threshold-audit trigger, but those are not active app objects.

Fresh SQLite migration to head was compared with ORM metadata using Alembic autogenerate; no schema differences were reported. SQLite/SQLAlchemy cannot reflect the expression-based `uq_rooms_home_lower_name` index during that comparison, so that index was verified separately in `sqlite_master` as a unique `(home_id, lower(name))` index. Migration tests also cover fresh upgrade, upgrade from `20261028_0003` preserving prior readings with `received_at = NULL`, and downgrade/re-upgrade on a disposable database. Downgrading `20261105_0004` drops the `received_at` column and its values; it must not be used to roll back the live database if populated with receipt times.

## Proposed target schema (not active ORM schema)

The product requirements propose separate global `Roles`, `Users.role_id`, room manager/facility assignments, sensor metadata, reading receipt time, effective-dated/attributed thresholds, alerts linked to sensor and reading records, and richer audit outcomes. These are design proposals, not active tables/columns. Current app roles are home-scoped membership values `owner` and `member`.

The requirements also call for a reviewed ER diagram, schema/query evidence, joins, indexes, a view, a procedure or trigger where required by the course, and transaction rollback evidence. The repository has SQL scripts and query examples, plus the active-schema reference above, but no completed ER diagram. DALTON replay tests force a later-row validation failure and verify batch rollback; forced database failures across all individual ingestion paths are not tested.

The SQL Server design in `database/migrations/` is a separate, non-compatible target schema rather than a deployment of this ORM schema. It adds a global roles table, composite same-home foreign keys, effective-dated threshold provenance, additional reading/alert links and checks, `activity_logs`, and reporting views/triggers that do not exist in the active ORM schema. Apply those scripts only to a separately selected SQL Server database after review; they are one-time scripts and are not an Alembic migration path for the local database.

## Portability and cloud boundary

SQLAlchemy and Alembic provide a portable application structure, but portability is not proof of equal behavior across database engines. SQLite JSON, functional/partial indexes, foreign-key setup, timestamp behavior, lock semantics, and migration DDL should be verified against the selected hosted database before migration. Azure SQL scripts are a separate SQL Server design; they do not establish that the current app works with Azure SQL.

No hosted database migration, PostgreSQL integration test, Azure deployment, or cloud validation is claimed. Back up existing data and verify the target database URL before running any migration.
