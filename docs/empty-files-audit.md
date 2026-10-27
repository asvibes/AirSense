# Empty tracked-file audit

## Git history

The current branch descends from `bbf7ad6` (`Added files empty`), which added the repository's placeholder files with zero-byte blobs. The earlier tracked history contains no recoverable application implementation. Commit `7366b0c` contains the first alert slice from the previous work; that code was preserved and then extended. No prior implementation was overwritten during this task.

## Current inventory

The following **83 tracked files were still zero bytes after the alert work**. They are listed explicitly to distinguish unfinished scope from code that is implemented. The alert application, its models, repository, routes, migration, UI, and lifecycle tests are no longer empty.

### Models

- `app/models/audit.py`
- `app/models/sensor.py`
- `app/models/user.py`

### Routers

- `app/routers/audit.py`
- `app/routers/auth.py`
- `app/routers/dashboard.py`
- `app/routers/demo.py`
- `app/routers/history.py`
- `app/routers/homes.py`
- `app/routers/rooms.py`
- `app/routers/sensor_readings.py`
- `app/routers/sensors.py`
- `app/routers/thresholds.py`
- `app/routers/uploads.py`

### Schemas and security

- `app/schemas/alert.py`
- `app/schemas/auth.py`
- `app/schemas/reading.py`
- `app/schemas/sensor.py`
- `app/security/dependencies.py`
- `app/security/device_keys.py`
- `app/security/passwords.py`
- `app/security/rate_limit.py`
- `app/security/sessions.py`

### Services and data sources

- `app/services/alerts/wording.py`
- `app/services/audit.py`
- `app/services/blob_storage.py`
- `app/services/email.py`
- `app/services/freshness.py`
- `app/services/ingestion/ingest.py`
- `app/services/ingestion/rejections.py`
- `app/services/ingestion/validate.py`
- `app/services/provisioning.py`
- `app/sources/airgradient.py`
- `app/sources/dalton_replay.py`
- `app/sources/simulator.py`

### Frontend assets and templates

- `app/static/js/heatmap.js`
- `app/static/js/polling.js`
- `app/static/js/rotating_chart.js`
- `app/static/manifest.webmanifest`
- `app/static/sw.js`
- `app/templates/activity_log.html`
- `app/templates/auth/join.html`
- `app/templates/auth/login.html`
- `app/templates/auth/register.html`
- `app/templates/base.html`
- `app/templates/components/certified_alarm_notice.html`
- `app/templates/components/freshness.html`
- `app/templates/components/room_card.html`
- `app/templates/components/source_badge.html`
- `app/templates/dashboard.html`
- `app/templates/demo_panel.html`
- `app/templates/history.html`
- `app/templates/members.html`
- `app/templates/room_detail.html`
- `app/templates/rooms.html`
- `app/templates/sensors.html`
- `app/templates/thresholds.html`

### Database and analytics

- `database/migrations/001_users_homes_members.sql`
- `database/migrations/002_rooms_sensors.sql`
- `database/migrations/003_metrics_thresholds.sql`
- `database/migrations/004_readings.sql`
- `database/migrations/005_alerts.sql`
- `database/migrations/006_audit_log.sql`
- `database/migrations/007_triggers_threshold_audit.sql`
- `database/migrations/008_views_daily_coverage.sql`
- `database/powerbi/airsense-report.pbix`
- `database/seed/default_thresholds.sql`
- `database/seed/metrics.sql`

The implemented alert schema is managed by Alembic at `migrations/versions/20261027_0001_alert_lifecycle.py`; the empty legacy SQL files above are not applied by the app.

### Documentation, infrastructure, tests, and tools

- `docs/architecture.md`
- `docs/dalton-notes.md`
- `docs/data-model.md`
- `docs/security-checklist.md`
- `docs/test-plan.md`
- `docs/threshold-sources.md`
- `infra/https_and_headers.md`
- `tests/conftest.py`
- `tests/test_access_control.py`
- `tests/test_audit.py`
- `tests/test_ingestion.py`
- `tests/test_provisioning.py`
- `tools/column_mapping.json`
- `tools/dalton_prep.py`
- `tools/seed_demo_home.py`

These remaining files correspond to unimplemented PRD features or empty legacy artifacts; they are not claimed as working features. See [PRD status](./PRD.md) for scope and deployment limitations.
