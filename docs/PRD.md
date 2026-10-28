# AirSense implementation status

The attached AirSense PRD (`AirSense PRD.docx`, dated October 26, 2026) is the authoritative product specification. The [AirSense Product Requirements Document](./product-requirements.md) records the proposed product scope and target architecture. This document tracks the Must-have scope implemented in the current branch; proposed requirements and target services must not be treated as completed work.

## Implemented Must-have flows

| Requirement | Current behavior |
| --- | --- |
| Registration and login | Accounts use validated email addresses and scrypt-hashed passwords. Successful registration creates an owner account and its first home. |
| Household access | Home membership is checked on home-scoped routes. Owners can invite members by single-use token; invited users must sign in with the invited email. Members can view the home's members and readings. |
| Sensor setup | Owners provision sensors for rooms, receive a one-time device key, rotate keys, and revoke sensors. Only a peppered key hash is stored. |
| Reading ingestion | Device-key-authenticated sensor readings and signed-in simulator readings are validated and sent through the alert processing path. Sensor last-seen data drives freshness state. |
| Room dashboard | The authenticated dashboard loads the selected home's rooms, latest readings, open alerts, and sensor freshness from the backend. Room ventilation notes are persisted. |
| Thresholds | Owners can update per-room CO₂ threshold settings in a single validated batch. Members may view settings. Default values remain illustrative, not health guidance. |
| History and export | Home-scoped history supports date, room, metric, CSV export, daily average bars, and a 90-day reading-coverage heatmap. |
| Audit history | Owner-only activity lists recorded home events, including account, room, invitation, threshold, sensor, and ingestion actions. Device keys and passwords are not recorded. |
| Alert lifecycle | High, sustained elevated, rapid-rise, acknowledgement, duplicate suppression, and all-clear behavior are persisted through the existing alert pipeline. |

The dashboard frontend is served by Flask with vanilla JavaScript and uses same-origin authenticated APIs. Mutating account/home requests require a CSRF token. The frontend no longer relies on local mock collections for these views.

## Out of scope or remaining limitations

* DALTON dataset import and replay are not configured. No DALTON records are generated or shown.
* Email delivery is not configured; invitations must be copied and shared manually.
* Automatic vendor integrations, live sensor discovery, and push/WebSocket updates are not implemented.
* The rate limiter is process-local and must be replaced with shared storage for multi-worker deployments.
* Threshold defaults do not have persisted authoritative citations. Confirm units, sensor range, and external guidance before any use beyond a demonstration.
* Additional Should/Could/Stretch features (critical alarm mode, room photos, and broader device integrations) remain out of scope.

Alembic migrations manage the shared SQLite/PostgreSQL schema in `migrations/versions/`. The empty files in older `database/` and `app/templates/` folders are legacy placeholders, not migrations or active application surfaces.

AirSense supports ventilation decisions; it is not a medical or safety device and does not replace a certified carbon monoxide alarm.
