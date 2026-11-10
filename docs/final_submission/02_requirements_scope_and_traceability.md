# Requirements, scope, and implementation traceability

## Basis and interpretation

The project brief in [product-requirements.md](../../docs/product-requirements.md) describes proposed requirements. The table below checks those requirements against the current local implementation, not against a production system. The application source and tests take precedence over aspirational statements in the brief or older documents.

## Functional requirements

| Brief area | Current implementation | Status and caveat |
|---|---|---|
| User authentication | Registration, login, logout, optional email OTP verification, and password reset routes exist. Passwords are checked and stored using Werkzeug's scrypt hash. | Implemented locally. Email delivery needs external Brevo configuration and has not been verified against a live provider. |
| Roles and authorization | Home memberships use `owner` and `member`; membership and role checks are performed on protected routes. | Implemented with a narrower role model than the brief's standard user/facility manager/administrator hierarchy. There is no global administrator or role-change workflow. |
| Homes and rooms | Users can create homes; owners can create and edit rooms and ventilation sources. | Room deletion is not implemented. |
| Sensor management | Owners can provision sensors, rotate keys, and revoke sensors. A generated device key is returned at provisioning/rotation; a keyed hash is stored. | Implemented locally; no physical device deployment or hardware validation is claimed. |
| Reading ingestion | Sensor-key readings, simulator submissions, AirGradient-shaped `rco2` payloads, and environmental CSV replay use validation and ingestion services. | Implemented locally. Live sensor credentials and physical measurements are not evidenced. |
| Validation and provenance | Values, metric/unit, timestamps, and room context are validated. Sources include `device`, `simulated`, and `dataset`. | Implemented locally. Dataset records are not sensor observations; display and reporting must preserve their source labels. |
| Thresholds and alerts | Per-room/metric policy values drive high, sustained-elevated, rapid-rise, acknowledgement, duplicate suppression, and all-clear behavior. | Implemented locally. Defaults are illustrative and are not cited health or safety limits. |
| Dashboard and freshness | Authenticated dashboard endpoints provide readings, room/sensor state, alerts, and supporting data. Sensor freshness is inferred from last-seen time and reporting interval. | Implemented in code; no automated browser end-to-end run or user acceptance study is included in this evidence package. |
| History and exports | Filtered history, metrics options, CSV export, PDF generation, and descriptive analytics pages/routes are present. | Implemented locally; production load and accessibility studies are not evidenced. |
| Forecasting / AI-ML | Offline code fits a linear time trend per reading series, uses an 80/20 chronological holdout, compares it with a persistence baseline, and only marks a model available after at least a 5% MAE improvement. It requires 30 distinct timestamps and forecasts up to 24 hours. | Implemented as a simple statistical baseline. No claim is made that it is a complex AI model, clinically useful, generally accurate, or validated on representative field data. Simulated readings are excluded from training in the documented application flow. |
| Activity/audit | Selected authentication, membership, sensor, reading, threshold, and alert events are recorded. | Implemented partially; coverage is limited to implemented actions. Unknown-account login events cannot be attributed to a home-scoped user. |
| Room photos | Authenticated room photo upload, retrieval, and deletion routes exist; allowed types and size are checked and files are stored outside static assets by default. | Implemented locally; no hosted private-storage service is configured. |
| Azure SQL and Blob Storage | A separate set of SQL Server scripts exists. The Flask app's active persistence is SQLAlchemy/Alembic; no Blob Storage adapter was found. | Not integrated. The SQL scripts are a proposed, different schema, not the active application schema. |
| Power BI | `database/powerbi/airsense-report.pbix` exists but is zero bytes. | Not implemented or verified. |
| Azure deployment | No Azure resource or live deployment evidence was found. A Render configuration file exists. | Azure deployment is not evidenced. A configuration file alone does not establish that any service is running. |

## Non-functional scope

- **Security:** Relevant code controls include password hashing, CSRF checks on authenticated mutations, server-side membership checks, device-key verification, input validation, and response headers. Production HTTPS, cloud identities, network restrictions, incident handling, and deployment secrets remain deployment responsibilities.
- **Privacy:** The application stores account, household, sensor, reading, alert, and audit data. Environmental data linked to a room and time may reveal household routines even though the app is not designed to collect medical data.
- **Reliability:** Reading and alert operations use database transactions; tests cover selected rollback and migration paths. This does not prove all database-failure scenarios.
- **Performance:** Queries use relational filters and indexes in active models. No load or scale benchmark was performed.
- **Accessibility:** The repository contains responsive templates and frontend code, but no formal accessibility audit is documented.
- **Maintainability:** The application is organized as a Flask modular monolith with routers, services, repositories, models, and migrations.

## Explicitly out of scope or unverified

AirSense does not manufacture sensors, read CO2 using a phone, control HVAC, diagnose illness, guarantee safe conditions, or guarantee push notifications. The repository does not establish a deployed Azure frontend/backend, a Power BI report, Blob Storage, physical sensor performance, a formal literature review, or actual per-role demo accounts. GitHub Actions push run [42848360170](https://github.com/asvibes/AirSense/actions/runs/42848360170) and pull-request run [42848374302](https://github.com/asvibes/AirSense/actions/runs/42848374302) passed all configured jobs on commit `0fe75da`, including PostgreSQL tests and migrations. This CI evidence is for the configured PostgreSQL service, not an Azure database or deployed application.

## Traceability sources

See the active code in `app/routers/`, `app/services/`, `app/models/`, `app/ml/`, and `app/sources/`; the executable suite in `tests/`; and the evidence summary in [document 10](10_test_and_submission_evidence.md). The PRD is a requirements source, not a completion certificate.
