# Empty-file audit

## Scope and result

The `divija` and `shreya` branch audits counted 28 and 22 tracked zero-byte files, respectively, before this merge. Those branch-specific snapshots are not a count for the merged tree: this merge populates several previously empty files. Recount before relying on either number. The audit checked imports, blueprint registration, template rendering, static references, requirements, and project documentation. Empty files are not by themselves evidence that functionality is missing.

No application behavior is inferred from filenames alone. The local SQLite database and its backup are not part of this inventory and must remain local.

## Classification and current status

- `app/services/blob_storage.py` now implements private local room-photo storage; Azure Blob Storage is still not integrated.

### Optional future feature

- `app/services/email.py` logs invitation details only in development; outbound email delivery is not configured.
- `app/sources/airgradient.py` normalizes AirGradient `rco2` push payloads through the existing device-key-authenticated ingestion endpoint; it does not poll vendor or cloud APIs.
- `app/static/manifest.webmanifest`
- `app/static/sw.js` — no installable/offline PWA behavior is registered.
- `tools/column_mapping.json` — the DALTON importer uses its documented fields; generic configurable mapping is not implemented.
- `tools/seed_demo_home.py` is an explicit CLI convenience and is not run during app startup.

### Active surfaces populated by this merge

- `app/routers/uploads.py` registers authorized private room-photo upload, retrieval, and deletion endpoints. DALTON replay remains in `app/routers/demo.py` and is processed in memory.
- `tests/conftest.py` provides pytest fixtures backed by temporary SQLite databases. Tests use both pytest fixtures and existing `unittest.TestCase` integration tests.

### Safe to remove only after reference review

These files are not active surfaces in the current Flask registration/template loading. Do not remove without a separate repository cleanup decision:

- `app/static/js/heatmap.js`
- `app/static/js/polling.js`
- `app/static/js/rotating_chart.js` — active dashboard functionality is consolidated in `app/static/js/dashboard.js`.
- `app/templates/activity_log.html`
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
- `app/templates/thresholds.html` — the active authenticated dashboard template is `app/templates/alerts.html`.

### External/manual submission artifacts

- `database/powerbi/airsense-report.pbix` — zero bytes; no finished Power BI report/data connection is present. This remains a PRD analytics deliverable.
- `infra/https_and_headers.md` — zero bytes; it is not active configuration. HTTPS/security headers must be configured and evidenced in the chosen deployment.

The historical inventory totals are branch-specific and pre-merge; they should not be treated as the merged tree's current zero-byte count.

## Functionality verified in active code

- `app/main.py` registers authentication, homes, rooms, sensors, device readings, thresholds, dashboard, history, audit, demo, alerts, and uploads blueprints.
- The authenticated UI is served from `app/templates/alerts.html` and loads `app/static/js/dashboard.js`; it calls same-origin backend routes with session credentials and CSRF tokens for mutations.
- User registration/login/logout, scrypt password hashing, CSRF, home membership, owner/member authorization, invitations, and per-sensor key provisioning/rotation/revocation are implemented. Invitation details are logged only in development; no outbound email is sent.
- Owners can update room names and ventilation sources. Room deletion is not implemented.
- Authenticated home members can upload, retrieve, and delete private JPEG, PNG, or WebP room photos (maximum 5 MB each).
- Device-key readings, simulated readings, and DALTON replay use validated server-side reading/alert processing. DALTON upload is processed in memory; no Blob persistence is implemented.
- AirGradient `rco2` pushes are normalized to CO₂ ppm and use the same device authentication, validation, rejection, and reading-processing path as other sensor readings.
- Alert evaluation/lifecycle, selected audit events, sensor freshness, history filters, CSV export, charts, heatmap, and dashboard polling are present in active application code.
- The latest full backend suite result must be updated after validating the merged tree. This is not browser E2E, PostgreSQL, or cloud deployment evidence.
- Azure SQL scripts under `database/` are separate target-schema scripts; they do not configure or migrate the active Flask database.

## Genuine gaps and boundaries

1. **Cloud/report deliverables:** The Power BI artifact is empty, Blob Storage is not integrated, and no Azure deployment/network/security evidence is present. These are deferred cloud/submission requirements, not local UI blockers.
2. **Room management:** Owners can create and update rooms. Room deletion is not implemented.
3. **Roles:** The application implements home-scoped `owner` and `member`, not the proposed facility-manager/administrator roles. No role-change flow exists.
4. **Audit:** Successful login, known-account failed login, logout, membership/invitation, sensor, threshold, reading, and alert lifecycle events are implemented and covered by selected tests. Unknown-account failed login has no home-scoped event; role changes cannot be audited until a role-change feature exists.
5. **Reading timestamps:** `air_readings` stores event time (`measured_at`) and nullable server receipt time (`received_at`). New readings receive UTC receipt timestamps through the shared ingestion service; existing rows are not backfilled.
6. **Hardware and notifications:** AirGradient `rco2` push payloads are supported through the generic device-key endpoint, but no polling/discovery, outbound email, or push/WebSocket updates are implemented. Simulator/DALTON flows are also available for local demos.
7. **Browser verification:** UI-to-API integration is evident in the active code, but no automated browser E2E evidence is available.

The API and application tests cover these active paths. The remaining empty templates and frontend scripts are not active application surfaces and should not be populated without a product requirement and explicit routing.

Threshold defaults are illustrative and do not have persisted authoritative citations. Do not represent simulated or dataset readings as physical sensor measurements, or threshold labels as medical/safety advice.

## Recommended handling

Keep the empty files classified above until the team decides scope. Do not populate them merely to eliminate zero-byte files. Treat Blob/Power BI/deployment artifacts as cloud/submission work; resolve the role, room-update, and receipt-time gaps against the assessed requirements before claiming full local PRD completion. Maintain current implementation details in [PRD.md](PRD.md) and target schema proposals separately in [data-model.md](data-model.md).
