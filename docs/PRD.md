# AirSense implementation status

## Status and source of truth

[product-requirements.md](product-requirements.md) describes the proposed product and submission target; it is not evidence that every requirement is implemented. This document summarizes the current local Flask application. Azure deployment, Power BI, Blob Storage, and other cloud services are not represented as complete.

The latest full local test run passed **77 tests and 64 subtests**. Tests cover selected routes, services, database constraints/defaults, audit behavior, timestamps, CSV export safety, migration upgrade/downgrade on disposable SQLite databases, and an API-level end-to-end database workflow. There is no automated browser E2E result, PostgreSQL integration result, or cloud deployment/integration test result.

## Implemented local functionality

| Area | Current implementation |
|---|---|
| Authentication | Registration, login, logout, session cookies, CSRF protection for authenticated mutations, and Werkzeug scrypt password hashes. Registration creates an owner and first home. |
| Household authorization | Home-scoped `owner` and `member` roles are checked server-side. Owners manage invitations, sensors, rooms creation, and thresholds; members can view household data and submit simulator readings. |
| Invitations | Owners create single-use, expiring invitations; acceptance is limited to the invited email. Delivery is manual; no email service is configured. |
| Sensors | Owners provision sensors for rooms, receive a one-time device key, rotate keys, or revoke sensors. The application stores a peppered key hash. |
| Ingestion | Device-key-authenticated readings and signed-in simulator/DALTON readings are validated and processed through threshold/alert logic. Sensor last-seen data feeds freshness state. |
| Demo lab | Custom/scenario readings and processed DALTON CSV replay are supported; replay is limited to 1,000 valid CO₂ rows and labels imported data as dataset/recorded. Dataset files are not bundled. |
| Dashboard | Flask serves an authenticated HTML/vanilla-JavaScript interface using same-origin APIs. It presents rooms, readings, alerts, sensor freshness, thresholds, members/activity, history charts/filters, CSV export, coverage heatmap, and simulator/replay actions. |
| Thresholds and alerts | Per-room CO₂ policy reads/updates; high, sustained elevated, rapid-rise, duplicate suppression, acknowledgement, and all-clear behavior. Threshold values are illustrative, not health guidance. |
| Audit | Registration, known-account login success/failure, logout, home/room/membership/invitation, sensor, threshold, reading rejection/ingestion, and alert lifecycle events are recorded in applicable home logs. Audit details avoid passwords and raw device/invitation secrets. |
| Database | SQLAlchemy models/Alembic revisions cover 11 application tables: homes, accounts/memberships/invitations, rooms, sensors, metrics, threshold policies, readings, alerts, and audit logs. Local SQLite is at revision `20261105_0004`; `received_at` is present and nullable. SQLite integrity/FK checks pass and current row counts match the pre-migration backup. Same-home consistency across independently referenced home/room/sensor IDs is not enforced by composite database constraints. |

## Incomplete local PRD requirements

- **Room management:** The owner-authorized room update API and dashboard editing for room name and ventilation sources are implemented. Room deletion is not implemented.
- **Role model:** Only home-scoped `owner` and `member` roles exist. The proposed standard-user/facility-manager/administrator roles, global administration, and role-change workflow are not implemented.
- **Reading receipt time:** `air_readings` persists `measured_at` and nullable `received_at`. New readings receive a server-generated UTC timestamp when they enter the shared ingestion service. Existing rows are not backfilled and retain a null receipt time.
- **Audit edge cases:** Known-account failed sign-ins, successful sign-ins, and logout are audited against that user's homes. Unknown-account failures have no home-scoped event. Role-change events cannot exist until role changes are implemented.
- **Browser verification:** The UI calls the backend in code, but no automated or recorded browser E2E verification has been completed.
- **Schema/documentation deliverables:** [data-model.md](data-model.md) documents the active ORM schema, but no completed ER diagram, project-specific threat model, or data-classification note is present.
- **Transaction rollback evidence:** A forced later-row validation failure in DALTON replay is tested to roll back the batch's readings and alerts and leave no partial ingestion/alert audit events. Forced database failures across all individual ingestion paths are not tested.
- **Threshold provenance:** Defaults are illustrative and authoritative citations are not persisted.

## Deferred cloud and submission requirements

- **Azure hosting and database:** No cloud deployment is claimed. SQLite is the local default; PostgreSQL URL handling exists, but PostgreSQL compatibility has not been integration-tested. Separate SQL Server scripts under `database/migrations/` do not configure the active Flask app's Alembic schema.
- **Database migration verification:** The active Alembic chain has one head, `20261105_0004`. Fresh upgrade, upgrade from `20261028_0003`, and downgrade/re-upgrade are tested using disposable SQLite databases only. Downgrading the receipt-time revision drops the `received_at` column and any values in it.
- **Blob Storage:** No active integration; DALTON uploads are processed in memory and CSV export is streamed.
- **Power BI:** `database/powerbi/airsense-report.pbix` is a zero-byte placeholder; no finished report or connection exists.
- **Deployment security evidence:** HTTPS, security headers, hosted database network restrictions, least-privilege hosted identity, private Blob access, and Azure resource evidence remain unconfigured/unverified.
- **Operational extensions:** Email delivery, automatic vendor integrations/live discovery, push/WebSocket updates, room photos, and installable/offline PWA behavior are not current features.

AirSense supports ventilation decisions; it is not a medical or safety device and does not replace a certified carbon monoxide alarm.
