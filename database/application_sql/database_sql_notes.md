# AirSense SQL deliverables: notes

Files: `schema.sql` (PostgreSQL 16), `schema_sqlite.sql` (SQLite), `queries.sql` (both).
Checked against repository commit `ce1a862` (10 Nov 2026), Alembic head `20261108_0008`.

## Which database is which

| | Application schema (these files) | Azure SQL scripts (`database/migrations/001..008_*.sql`) |
|---|---|---|
| Status | Implemented; what the Flask app and tests use | Proposed design; **never run on Azure SQL**; not used by the app |
| Engines | SQLite (local default), PostgreSQL 16 (Render, CI) | SQL Server / Azure SQL (T-SQL, `GO` batches) |
| Tables | 13 | Different names and columns (for example `sensor_key_hash`, UUID keys) |
| Extras | No views, triggers or procedures | Two views, one trigger, one example transaction (never executed) |

The 13 tables: `users`, `homes`, `home_memberships`, `home_invitations`, `email_challenges`, `rooms`, `sensors`, `metrics`, `air_readings`, `threshold_policies`, `air_alerts`, `audit_logs`, `rate_limit_buckets`. Alembic's own `alembic_version` table is not counted and not included.

## What was tested

| Check | Result |
|---|---|
| `schema.sql` applied to an empty PostgreSQL 16 database | Succeeds; 13 tables |
| Its `pg_dump -s` compared with the schema Alembic builds on PostgreSQL 16 | Identical apart from Alembic's own `alembic_version` table |
| `schema_sqlite.sql` applied to an empty SQLite 3.53 database | Succeeds; `integrity_check` ok, `foreign_key_check` clean |
| Its tables, columns, types, nullability, primary keys, foreign keys and indexes compared with the Alembic-built SQLite schema | Equal (column default values were checked by eye, not by script) |
| `queries.sql` on PostgreSQL 16 (`ON_ERROR_STOP`) | Runs without error |
| `queries.sql` on SQLite | Runs without error; the 15 queries and 3 views return the same row counts as PostgreSQL |
| 8 "expected to fail" constraint examples (Section 7) | Each fails with the expected constraint error on both databases |
| Dialect-specific queries (Section 8) | Run on the matching database; index plan shows `ix_readings_home_room_metric_time` |

Not tested: Azure SQL / SQL Server (the files are not for it), any PostgreSQL version other than 16, any SQLite version older than 3.25 (window functions) and 3.24 (`ON CONFLICT`), and production data. The scripts were run only on throwaway databases, and the repository was not changed.

## Database-specific differences

| Topic | PostgreSQL | SQLite |
|---|---|---|
| Auto-number keys | `SERIAL` (sequence) | `INTEGER PRIMARY KEY` |
| Timestamps | `TIMESTAMPTZ` (UTC) | `DATETIME` (text, no zone) |
| Booleans, floats, JSON | `BOOLEAN`, `DOUBLE PRECISION`, `JSON` | integer 0/1, `FLOAT`, text |
| Foreign keys | Always enforced | Only with `PRAGMA foreign_keys = ON` per connection |
| Day / hour grouping | `date()`, `date_trunc` | `date()`, `strftime` |
| Time difference | `EXTRACT(EPOCH FROM ...)` | `julianday(...)` |
| Query plan | `EXPLAIN` | `EXPLAIN QUERY PLAN` |
| Time zone | `SET TIME ZONE 'UTC'` before `queries.sql` | not needed |
| Error text | e.g. `duplicate key value violates unique constraint` | e.g. `UNIQUE constraint failed` |

## Limits of the schema (worth stating in the report)

- **Room/home consistency is not enforced by the database.** `air_readings`, `air_alerts`, `threshold_policies` and `sensors` hold both `home_id` and `room_id` as independent foreign keys, so a row could name a room from another home. The application prevents it; `queries.sql` Section 6 has checks that should return zero rows.
- **No CHECK constraints** on `air_readings.source`, `home_memberships.role`, `home_invitations.role` or `email_challenges.purpose`. The application validates them.
- **No cascades:** deleting a parent row that still has children is refused by the foreign keys.
- **Metric seed:** only `CO2` is inserted, as the application does on start-up. Other metrics are created by the application when a reading arrives.
- **Normalisation:** the schema is in 3NF for its entities, with two deliberate duplications: `home_id` alongside `room_id` (for scoped lookups) and the alert's copied `trigger_value`, `threshold_value` and `threshold_unit` (a snapshot at the time of the alert). Say this in the RDBMS write-up rather than claiming a formal normalisation proof.
- **Views are teaching examples.** The application defines none. `queries.sql` creates three and drops them at the end; drop them before any Alembic downgrade.
- **No stored procedure or trigger** exists in the application database. Those items in the course guide are only in the unrun Azure SQL track.
- The data in `queries.sql` is invented demo data.

## Suggested placement in the submission

Put `schema.sql`, `schema_sqlite.sql` and `queries.sql` in a folder such as `database/application_sql/`, so they are not confused with `database/migrations/` (Azure SQL). If the guide requires exactly two files named `schema.sql` and `queries.sql`, submit those two and attach the SQLite variant and these notes as supporting material.