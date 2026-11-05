# Alert lifecycle

## Rules and state

Each threshold policy is scoped to a home, room, and metric:

* **High:** a reading at or above `high_threshold` opens a High alert immediately.
* **Elevated:** a reading at or above `elevated_threshold` starts or continues a timer. The alert opens after observations satisfy `elevated_duration_seconds`; a gap greater than `max_reading_gap_seconds` resets the timer. A High reading takes precedence over Elevated.
* **Rapid rise:** a reading creates a Rapid Rise alert when its increase over the preceding sample, expressed per minute, reaches `rapid_rise_per_minute`.
* **All clear:** readings must remain below the alert's captured threshold for `all_clear_duration_seconds`. A gap greater than `max_reading_gap_seconds` resets clear progress. The alert retains its threshold snapshot if the policy later changes.

Acknowledgement is independent from resolution: an acknowledged alert remains open, continues to receive readings, and can transition to All clear. Repeated acknowledgement is idempotent and preserves the original member label and timestamp. A later breach after All clear can create a new alert.

The database has a filtered unique index on `(home_id, room_id, metric_code, level)` for alerts with `active` or `acknowledged` status. Reading processing and alert-state changes execute in the caller's database transaction. The DALTON replay tests force a later-row validation failure and verify that the batch's readings and alerts roll back without partial ingestion/alert audit events. Forced database failures across all individual ingestion paths are not tested.

## Current API

The main UI-facing, home-scoped routes include:

* `GET /api/homes/{home_id}/dashboard` — latest dashboard readings and alerts.
* `GET /api/homes/{home_id}/thresholds` and `PUT /api/homes/{home_id}/thresholds` — read/update threshold settings.
* `POST /api/homes/{home_id}/demo/readings` — submit an authenticated simulator reading.
* `POST /api/sensors/{sensor_id}/readings` — submit a device reading authenticated by `X-Device-Key`.
* `POST /api/alerts/{alert_id}/acknowledge` — acknowledge an alert as a signed-in home member.
* `GET /api/homes/{home_id}/activity` — read activity as a home owner.

Compatibility routes remain in the alerts blueprint:

* `GET /api/dashboard?home_id=...` and `GET /api/alerts?home_id=...`
* `POST /api/policies` and `POST /api/readings`
* `POST /api/alerts/{alert_id}/acknowledge`

Authenticated browser mutations require the session CSRF token. Device reading submission instead requires the sensor key. `REQUIRE_API_TOKEN` optionally adds a bearer-token gate to routes handled by the alerts blueprint when no user session is present; it is not a global API gate and does not replace membership or device authentication.

## Audit and verification

Alert creation, acknowledgement (only on the first transition), and all-clear are recorded through the shared audit service in the same database transaction. Tests in `tests/test_alert_scenarios.py`, `tests/test_audit.py`, `tests/test_database_workflow.py`, and `tests/test_dalton_replay.py` cover alert behavior, audit-event counts, and DALTON batch rollback. The latest overall backend test run passed 77 tests and 64 subtests. No browser E2E, PostgreSQL integration, or cloud deployment test is claimed.

## Data and deployment caveats

The active database tables are `threshold_policies`, `air_readings`, `air_alerts`, and `audit_logs` among the related home/user/room/sensor tables. The alert schema stores threshold snapshots and transition metadata, but does not have sensor/reading foreign-key columns described in the proposed data model.

Local SQLite is the default. PostgreSQL URL support exists, but compatibility has not been verified by an integration test. Azure SQL scripts are separate from the app's Alembic migrations. Azure hosting, HTTPS, security headers, network restrictions, Power BI, and Blob Storage have not been implemented or verified. Default CO₂ threshold values are illustrative, not health guidance; threshold citations are not persisted.
