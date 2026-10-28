# AirSense implementation status

The [AirSense Product Requirements Document](./product-requirements.md) records the proposed product scope and target architecture. This document tracks what the current branch implements; proposed requirements and target services must not be treated as completed work.

## Implemented vertical slice

| PRD requirement | Current behavior |
| --- | --- |
| FR-5.1 High | Opens an alert immediately at or above the configured high threshold. |
| FR-5.1 Elevated | Requires consecutive readings at or above the elevated threshold for the configured duration; long data gaps restart the timer. |
| FR-5.1 Rapid rise | Compares consecutive readings and opens an alert when the configured rate per minute is reached. |
| FR-5.2 Duplicate prevention | Partial unique index scopes open alerts to home, room, metric, and level. |
| FR-5.3 Acknowledgement | Stores display name and timestamp; repeated acknowledgement preserves the first actor/time. |
| FR-5.4 All-clear | Clears only after subsequent samples stay below that alert's captured threshold for its configured duration. Missing samples and long gaps restart the timer. |
| FR-5.5 Wording | Uses “above the guideline level used by AirSense”; includes the certified carbon-monoxide-alarm disclaimer. |

Threshold policies are stored per home, room, and metric. Demo defaults are illustrative and are not represented as published health guidance. The database migration is in `migrations/versions/20261027_0001_alert_lifecycle.py`; the SQLite and PostgreSQL schema share SQLAlchemy metadata.

## Not yet implemented

The product requirements document's other Must-have features—registration, login, household roles and invitations, sensor provisioning and device-key authentication, unified dataset/simulator ingestion, room dashboard and freshness, historical charts/CSV/heatmap, and owner-only audit logging—are not included in this alert slice. Should/Could/Stretch features (demo replay, email, critical alarm mode, room photos, live sensors) are also out of scope. The placeholder files for those features remain unimplemented; do not treat their presence as a completed implementation.

Until user accounts and home-level authorization are delivered, the demo relies on a shared optional bearer token to guard application routes in a hosted configuration. Acknowledgement names are caller-supplied display labels rather than verified account identities. Do not use the demo with personal household data.