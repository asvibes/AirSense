# AirSense Product Requirements Document

**Product:** Indoor CO2 Monitoring and Ventilation Insights Platform  
**Version:** 1.0  
**Project type:** Academic full-stack project  
**Date:** October 2026

## Document purpose

This document defines AirSense product goals, users, scope, requirements, workflows, proposed data model and architecture, security expectations, and acceptance criteria. It is a proposed implementation plan, not a statement that all features or services are already built. Refer to [implementation status](./PRD.md) for what the current branch implements.

## 1. Product overview

AirSense is a web application that receives carbon dioxide (CO2) measurements from connected environmental sensors, stores and evaluates readings, and presents room-level status, alerts, and historical trends. The application is the monitoring and analysis layer; it does not manufacture sensors or claim that a phone measures CO2 directly.

### 1.1 Problem statement

Indoor occupants and facility managers may not have an easy way to view CO2 readings across rooms, identify periods of elevated readings, or review historical patterns. Sensor readings can be fragmented or difficult to interpret. AirSense centralizes measurements, applies configurable threshold rules, and makes room conditions and trends easier to understand.

### 1.2 Product goal

Provide a simple, secure interface for monitoring CO2 measurements from connected sensors, identifying readings that cross configured thresholds, and reviewing room-level history and analytics.

### 1.3 Intended users

- **Standard user / room occupant:** views permitted rooms, current readings, history, and alerts.
- **Facility manager:** manages assigned rooms and sensors, configures thresholds, and reviews room-level trends.
- **System administrator:** manages user access, roles, and system-level configuration.

## 2. Scope

### 2.1 In scope for the proposed MVP

- Authentication and role-based authorization.
- Room and sensor registration and management.
- Secure API for ingesting sensor readings, with validation and timestamps.
- Current CO2 reading and rule-based ventilation status per room.
- Configurable threshold values and alerts when configured rules are met.
- Historical readings, time-range filters, and charts.
- Activity logging for security-sensitive and administrative actions.
- Azure-hosted relational database, non-relational file storage, and a Power BI analytical report.
- Test or simulated readings during development if physical hardware is unavailable.

### 2.2 Out of scope for the first version

- Manufacturing or designing a physical CO2 sensor.
- Using a phone camera or phone hardware as a direct CO2 measurement device.
- Medical diagnosis, disease prediction, or guarantees about health outcomes.
- AI-based prediction of future CO2 levels unless separately implemented and validated.
- Automated control of HVAC or ventilation equipment.
- Guaranteed real-time notifications through SMS or paid third-party services.

## 3. Product principles and limitations

- AirSense consumes measurements from a connected sensor or a clearly labelled simulator; it does not measure CO2 on its own.
- Actual concentration readings require an appropriate CO2 sensor, such as an NDIR-based sensor. A generic temperature/humidity sensor is not a CO2 sensor.
- Ventilation labels are rule-based interpretations of measured CO2 and configured thresholds, not medical assessments or a complete indoor-air-quality score.
- The UI should display the reading, unit (ppm), timestamp, sensor status, and threshold used so users can interpret data in context.
- Simulated readings must be visibly labelled as demo or simulated data.

## 4. Functional requirements

| ID | Requirement |
| --- | --- |
| FR-01 Authentication | Users can register or sign in securely and sign out. Passwords are stored with a password-specific hashing method, never as plain text or a fast unsalted hash. |
| FR-02 Role-based access | The application supports at least standard-user and administrator/facility-manager permissions. Every protected API checks authorization on the server. |
| FR-03 Room management | Authorized users can create and update rooms and associate them with permitted users or facilities. |
| FR-04 Sensor management | Authorized users can register sensors, assign them to rooms, mark them active/inactive, and view their last received reading. |
| FR-05 Reading ingestion | The backend exposes a documented API accepting sensor identifier, CO2 value in ppm, and measurement timestamp. It validates device identity, value, timestamp, and request format before storage. |
| FR-06 Reading history | Users can view readings for a permitted room over a selected time range and see a time-series chart. |
| FR-07 Status evaluation | The backend compares valid readings with room threshold rules and returns a documented status such as Normal, Elevated, or High. |
| FR-08 Alerts | When a configured rule is met, the application creates an alert with room, sensor, measured value, threshold, timestamp, and status. Repeated readings must not create uncontrolled duplicate alerts. |
| FR-09 Threshold configuration | Authorized users can view and update thresholds. Changes are validated and written to the activity log. |
| FR-10 Dashboard | The main dashboard shows current or most recent readings, room status, recent alerts, and sensor freshness/last-seen information. |
| FR-11 Analytics | A Power BI report uses stored historical data to show trends, room comparisons, averages, and counts of threshold events. It may be accessed separately from the web application. |
| FR-12 File/report storage | Azure Blob Storage stores generated reports or supporting files where needed; it does not replace the relational operational database. |
| FR-13 Activity log | The system records important actions, including sign-in events, sensor registration, threshold changes, role changes, and administrative updates, without logging passwords or secrets. |
| FR-14 Demo data | Authorized users can load clearly marked simulated readings for development and testing when no physical sensor is connected. |

## 5. Non-functional requirements

| Quality | Requirement |
| --- | --- |
| Security | Use HTTPS in deployment, password-specific hashing, server-side authorization, validated inputs, secret configuration outside source control, and database network restrictions. |
| Privacy | Collect only data needed to manage accounts, rooms, sensors, readings, alerts, and audit events. Avoid collecting personal health data. |
| Reliability | Reject malformed readings safely and preserve valid records. Use transactions for database operations that change multiple related records. |
| Performance | Paginate or time-filter historical readings and index commonly searched columns such as room/sensor IDs and measurement timestamps. |
| Usability | Show clear units, timestamps, empty/loading/error states, and sensor-offline or stale-data indicators. |
| Maintainability | Organize frontend, backend, database scripts, and configuration; document setup, API contracts, and environment variables. |
| Scalability | Start with a modular monolith (proposed React frontend, Flask API, and one relational database). Use indexes and bounded queries before considering caching or service separation. |
| Accessibility | Use readable contrast, labelled form controls, keyboard-accessible navigation, and responsive layouts. |

## 6. Roles and permissions

| Role | Permissions |
| --- | --- |
| Standard user | View assigned rooms, current readings, permitted history, and alerts. |
| Facility manager | Manage assigned rooms and sensors; configure thresholds; review alerts and room analytics. |
| Administrator | Manage user roles and system configuration; review activity logs; perform administrative actions. |
| Sensor/device identity | Submit readings only for its registered device identity; cannot access user-facing endpoints. |

## 7. Proposed system architecture

### 7.1 Data flow

1. A CO2 sensor or clearly labelled simulator produces a measurement.
2. A connected gateway/device sends the reading to a Flask REST API over a secure connection.
3. The API authenticates the device, validates the payload, and writes a timestamped reading to Azure SQL.
4. The backend evaluates threshold rules and creates an alert when the configured condition is met.
5. The web frontend requests authorized data from the Flask API and displays room status, readings, history, and alerts.
6. Power BI connects to an appropriate read-only dataset/source for historical reporting. Azure Blob Storage holds generated reports or supporting files.

The proposed deployment is a React frontend, Flask REST API, and Azure SQL Database. Sensor ingestion uses a device-specific backend endpoint. Blob Storage handles files, while Power BI provides a separate analytics/reporting layer. This is a target architecture, not the current prototype architecture; see [architecture](./architecture.md).

### 7.2 Proposed API

| Method | Endpoint | Purpose |
| --- | --- | --- |
| POST | `/api/auth/register` | Create an account if public registration is enabled. |
| POST | `/api/auth/login` | Authenticate a user and establish a secure session/token. |
| POST | `/api/sensor-readings` | Accept a reading from an authenticated/registered sensor. |
| GET | `/api/rooms` | List rooms the signed-in user may access. |
| POST | `/api/rooms` | Create a room (manager/admin only). |
| GET | `/api/rooms/{room_id}/readings` | Return time-filtered readings for an authorized room. |
| GET | `/api/rooms/{room_id}/status` | Return the latest reading, timestamp, and threshold-based status. |
| GET | `/api/alerts` | List alerts visible to the signed-in user. |
| PATCH | `/api/alerts/{alert_id}` | Update alert acknowledgement/status (authorized roles only). |
| GET | `/api/sensors` | List authorized sensors and their last-seen status. |
| POST | `/api/sensors` | Register a sensor (manager/admin only). |
| PATCH | `/api/rooms/{room_id}/thresholds` | Update room thresholds (manager/admin only). |
| GET | `/api/admin/activity-logs` | Retrieve permitted audit records (admin only). |

These are proposed resource contracts and are not a promise that corresponding endpoints currently exist.

## 8. Proposed relational data model

The final schema should be reviewed for third normal form (3NF), documented in an ER diagram, and submitted as a schema script plus query file.

| Table | Example columns / relationships |
| --- | --- |
| Users | `user_id` PK, name, unique email, `password_hash`, `role_id` FK, `created_at`, `is_active` |
| Roles | `role_id` PK, unique `role_name` |
| Rooms | `room_id` PK, room name, location label, `manager_user_id` FK, `created_at` |
| Sensors | `sensor_id` PK, device-key hash/credential reference, `room_id` FK, sensor type, status, `last_seen_at` |
| CO2Readings | `reading_id` PK, `sensor_id` FK, `co2_ppm`, `measured_at`, `received_at` |
| Thresholds | `threshold_id` PK, `room_id` FK, elevated/high ppm, `effective_from`, `updated_by` FK |
| Alerts | `alert_id` PK, `room_id`/`sensor_id`/`reading_id` FKs, threshold value, severity, `created_at`, status, nullable `acknowledged_by` FK |
| ActivityLogs | `log_id` PK, nullable `user_id` FK, action type, target type/ID, `occurred_at`, outcome |

Required database evidence includes primary and foreign keys, appropriate UNIQUE/CHECK/NOT NULL constraints, indexes for room/sensor/measurement time and common filters, multi-table joins, a view (for example, latest reading per room), a stored procedure or trigger, and at least one transaction. One example transaction inserts a validated reading and creates its corresponding alert when a threshold rule is crossed.

## 9. DP-900 / data services plan

- **Structured data:** Users, roles, rooms, sensors, CO2 readings, thresholds, alerts, and activity logs in Azure SQL Database.
- **Unstructured files:** Generated reports or supporting documents in Azure Blob Storage, with access controls and no secrets in public containers.
- **Analytics:** Power BI report for time trends, room comparisons, daily averages, and alert counts using a controlled/read-only data connection.
- **Submission evidence:** Data-classification note, Azure resource screenshots, and the analytics report.

## 10. Cloud security plan

- **Authentication:** Secure login; password hashing with a suitable password-hashing function, such as Argon2id, bcrypt, or a framework password-hashing helper.
- **Authorization:** Enforce role and room-level access checks on every protected backend route.
- **Transport:** HTTPS for deployed web/API traffic; do not transmit credentials over plain HTTP.
- **Secrets:** Store database credentials, signing keys, and device credentials in deployment configuration/secret settings; exclude `.env` files from version control.
- **Input handling:** Validate type, range, size, timestamps, IDs, and allowed fields; use parameterized SQL/ORM queries, escape output, and avoid unsafe HTML rendering.
- **Database perimeter:** Configure Azure SQL firewall/network rules for the deployment environment and use least-privilege database credentials.
- **Device trust:** Authenticate each registered sensor or gateway; do not expose a shared unrestricted ingestion endpoint.
- **Audit:** Log login outcomes, role changes, sensor changes, threshold updates, and administrative actions without recording passwords or raw secrets.
- **Threat model:** Document assets, trust boundaries, threats, mitigations, and residual risks in a concise threat model.

## 11. Analytics and status logic

Status categories must be configurable and documented. For the MVP, the application can compare a reading with room-specific thresholds and label it Normal, Elevated, or High. Threshold values must be selected from credible guidance and project requirements rather than presented as universal medical safety boundaries.

If a rule requires a duration (for example, a reading remains above a threshold), the backend should evaluate consecutive/time-window readings rather than create an alert from a single sample. Power BI measures may include average CO2 by room/day, maximum recorded CO2, number of threshold events, and time above a configured threshold when the data supports that calculation. These are descriptive analytics, not AI predictions.

## 12. UI / UX requirements

- Login and account pages.
- Overview dashboard with room cards, latest CO2 value in ppm, timestamp, status, and sensor freshness.
- Room detail page with historical chart and date/time filters.
- Alerts page with severity, room, value, timestamp, and acknowledgement state.
- Room/sensor management pages for authorized roles.
- Threshold configuration form with validation and confirmation of changes.
- Activity-log view restricted to administrators.
- Responsive, calm, readable interface; status labels must not rely on color alone.
- Loading, empty, error, offline/stale-sensor, and simulated-data states.

## 13. Trade-off decision

The initial target architecture is a modular monolith consisting of a React frontend, one Flask API backend, and Azure SQL. This is simpler to build, deploy, test, and explain for a small academic team than splitting the system into microservices. Historical queries will be time-filtered and indexed; dashboard responses may be cached only if needed and with a short freshness window. The trade-off is less independent backend scaling than separate services, in exchange for lower deployment and operational complexity for the MVP.

## 14. Acceptance criteria

- A user can sign in and can only access rooms/actions allowed by their role.
- A valid sensor reading is stored with sensor identity and measurement/received timestamps.
- Malformed or unauthorized readings are rejected and do not alter stored data.
- The dashboard displays the latest valid reading and makes stale data visible.
- Configured threshold rules create an alert that can be viewed and acknowledged.
- Historical readings can be filtered and displayed in a chart.
- The relational schema has at least five related tables and satisfies the course's 3NF expectation.
- The submitted SQL/query file demonstrates joins, indexes, a view, a stored procedure or trigger, and a transaction.
- Azure SQL is hosted on Azure; Blob Storage is used for files; a Power BI analytical report is produced.
- Security evidence demonstrates HTTPS, password hashing, RBAC, secret handling, input validation, database network restrictions, and activity logging.
- The repository includes setup instructions, environment variable examples without secret values, schema/query scripts, test instructions, and architecture/threat-model documents.

## 15. Testing plan

- **Unit tests:** Threshold evaluation, input validation, and permission checks.
- **API tests:** Valid reading ingestion, malformed payload rejection, unauthenticated request rejection, and role restrictions.
- **Database tests:** Constraints, joins, transaction rollback/commit behavior, and alert creation.
- **Integration tests:** Backend-to-Azure-SQL connectivity and frontend-to-API flows.
- **Security checks:** Injection-payload handling, output escaping, secret scanning, HTTPS configuration, and database firewall configuration.
- **Demo test:** Show a clearly labelled simulated reading if hardware is unavailable; do not present simulated data as a physical measurement.

See the [test plan](./test-plan.md) for status-aware verification guidance.

## 16. Deployment and submission deliverables

- Deployed frontend and backend on suitable Azure services within available student/free credits.
- Azure SQL schema script and query file.
- ER diagram and design document with architecture and data flow.
- API list and setup/README documentation.
- Data-classification note, Azure resource screenshots, and Power BI report.
- One-page threat model and completed security checklist.
- Test evidence, demo account(s) per role, and full commit history.

## 17. Suggested milestones

| Phase | Outcome |
| --- | --- |
| 1 — Foundation | Finalize scope, roles, requirements, ER diagram, API contracts, and UI wireframes. |
| 2 — Core application | Implement authentication, room/sensor management, reading ingestion, storage, and dashboard. |
| 3 — Alerts and history | Implement threshold evaluation, alerts, filters, charts, and activity logging. |
| 4 — Cloud and security | Deploy to Azure; configure Azure SQL and Blob Storage, HTTPS, secrets, and database firewall. |
| 5 — Analytics and evidence | Build Power BI report, run tests, capture resource screenshots, and finish threat model/checklist. |
| 6 — Final review | Verify rubric requirements, README, demo accounts, schema/query files, and viva explanations. |

## 18. Assumptions and open decisions

- The project is a software platform that consumes sensor data; physical hardware availability is not guaranteed.
- Simulated readings can support development, but the UI and demo must label them accurately.
- Exact CO2 thresholds and duration rules must be chosen, documented, and justified before implementation.
- Azure resource availability, free-tier limits, and student credits must be confirmed before deployment.
- Power BI may be a separate report rather than embedded in the frontend.
- Email/SMS notifications and advanced forecasting are optional and must not be promised unless time and services allow.
