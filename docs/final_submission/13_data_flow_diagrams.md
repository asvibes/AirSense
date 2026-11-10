# AirSense data-flow diagrams

## Diagram files

| Diagram | PNG export | Editable source |
|---|---|---|
| System architecture | [system_architecture.png](diagrams/system_architecture.png) | [system_architecture.svg](diagrams/system_architecture.svg) |
| DFD Level 0 (context) | [dfd_level_0.png](diagrams/dfd_level_0.png) | [dfd_level_0.svg](diagrams/dfd_level_0.svg) |
| DFD Level 1 (decomposition) | [dfd_level_1.png](diagrams/dfd_level_1.png) | [dfd_level_1.svg](diagrams/dfd_level_1.svg) |
| Active ORM ER diagram | [er_diagram.png](diagrams/er_diagram.png) | [er_diagram.svg](diagrams/er_diagram.svg) |

SVG files are editable vector source documents. PNGs are raster exports generated locally from those sources. The diagrams describe the inspected local code and logical data paths; they do not imply that external systems are configured or deployed.

## DFD Level 0 — context

The single process is the AirSense application. External entities and flows:

- **Home user/owner ↔ AirSense:** account/session actions, home/room/sensor/policy requests, filters and demo inputs; responses include authorized dashboard data, alerts, history, and exports.
- **Sensor client ↔ AirSense:** device-key-authenticated measurements and acceptance/rejection responses.
- **Email provider ↔ AirSense:** OTP/invitation email submission and provider response, only when credentials and sender configuration are provided.
- **Project operator ↔ offline forecast workflow:** local configuration/training operation and forecast evaluation file. The operator is an operational actor, not an implemented in-app global admin role.

The context diagram intentionally omits internal data stores. No physical sensor, email delivery, or public deployment has been independently verified.

## DFD Level 1 — process decomposition

| Process | Responsibility | Main persistent data |
|---|---|---|
| 1.0 Account and access | Registration/authentication, session and CSRF validation, home-role checks | `users`, `home_memberships`, `home_invitations`, `email_challenges` |
| 2.0 Home configuration | Home, room, sensor and threshold management | `homes`, `rooms`, `sensors`, `threshold_policies`, `metrics` |
| 3.0 Ingest and validate | Device/demo payload normalization, metric/unit/time checks, source tagging and dataset parsing | Validated reading candidates; sensor lookup |
| 4.0 Evaluate and audit | Shared reading persistence, threshold/alert lifecycle, sensor last-seen and audit event | `air_readings`, `air_alerts`, `audit_logs`, `rate_limit_buckets` |
| 5.0 Query and present | Authorized dashboard/history/analytics queries, CSV/PDF and photo routes | Reads from relational data; private local photo files |
| 6.0 Forecast evaluation | Offline device/dataset series fitting, chronological holdout comparison and JSON save | Readings plus local forecast JSON |

### Main data path

`sensor/demo input → authenticate/authorize → parse and validate → resolve home/room/metric → write reading and lifecycle/audit changes → query authorized views/exports`.

The sensor route authenticates with a device key; browser mutations use session and CSRF protection. Simulator and dataset records carry distinct `source` labels. Dataset replay does not run live alerts in the batch ingestion path. A normal sensor reading invokes the alert evaluation path within a database transaction.

## Data-store mapping and limitations

- D1 account/setup: relational user, home, membership, room, sensor, invitation, challenge and threshold data.
- D2 measurements/alerts: metric, reading and alert entities in the active ORM database.
- D3 audit/rate state: event logs and persistent rate-limit buckets.
- D4 instance files: forecast model JSON and private room photos stored through local filesystem paths.

The active default is SQLite. The repository has separate Azure SQL scripts and a `render.yaml`, but neither proves production deployment. There is no active Azure Blob Storage integration; the room-photo service is local filesystem storage. Power BI is not active.

## Symbol notes

- DFD Level 0 uses a single application process and external entities.
- DFD Level 1 uses `E` for external entity, numbered rounded rectangles for processes and `D` for data stores.
- Arrows indicate conceptual data flow. They do not specify physical network topology, deployment firewall rules, or guarantees of email delivery.
