# Data classification and threat model

## Purpose and boundary

This note classifies data represented by the current local application and summarizes threats at a student-project level. It is based on the models, authentication/ingestion routes, and configuration. It is not a formal privacy impact assessment, legal determination, or independent penetration test.

## Data classification

| Data | Examples in the application | Suggested classification | Handling notes |
|---|---|---|---|
| Account identity | Email, display name, account state, verification time | Confidential | Restrict to authenticated, authorized use; avoid including real identities in screenshots or reports. |
| Authentication material | Scrypt password hash, OTP hash, reset-token hash, session version, session cookie | Restricted secret / confidential | Never publish hashes or cookies. Use private secrets in deployment. Challenge hashes and expiry state exist in the database. |
| Device credentials | One-time raw device key and stored keyed hash | Restricted secret | Raw key is returned during provisioning/rotation; store only the hash. Treat the response as a secret. |
| Home and room context | Home/room names, ventilation sources, membership and invitations | Confidential | Names and membership can identify household relationships and occupancy context. Invitation token hashes are persisted. |
| Environmental readings | Metric, value, unit, measured/received timestamps, home/room/sensor links, source | Confidential | Readings linked to a room and time can reveal household activity patterns. Preserve `device`, `simulated`, and `dataset` labels. |
| Alerts and policy | Threshold values, alert detail, status and acknowledgement | Confidential | Policies are advisory application settings; defaults are illustrative. Do not present alerts as medical diagnosis or certified warning. |
| Audit records | Event type, actor, entity, timestamp, details JSON | Confidential | Avoid storing secrets in details. Access and retention policy should be decided for any real deployment. |
| Uploaded room photos | JPEG/PNG/WebP bytes and room association | Confidential, potentially personal | Application stores photos outside static assets by default and checks access; hosted storage and retention are not evidenced. |
| Forecast outputs | Series identifiers, trend parameters, evaluation metrics, forecast intervals | Confidential when linked to home/room/sensor | Model output inherits the sensitivity of the source readings and should not be treated as validated health insight. |
| Configuration and deployment secrets | Secret key, device-key pepper, database/email credentials | Restricted secret | Keep out of source control, logs, screenshots, and reports. |

The product is not designed to collect personal health records, but a household's measurement history may be sensitive indirectly. No data retention, deletion, or backup schedule was verified in this source review.

## DP-900 data-format classification

The sensitivity labels above describe confidentiality. They are separate from the following data-format classification:

| Data format | AirSense examples | Current storage / status |
|---|---|---|
| Structured | Account, home, room, sensor, metric, threshold, reading, alert, and membership records | Relational SQLAlchemy tables; SQLite is the local default, and PostgreSQL test/migration CI passed. Azure relational hosting is not verified. |
| Semi-structured | Device/API JSON payloads; JSON-valued ventilation-source and audit-detail fields | JSON is accepted or stored within the application/database. No separate Azure Cosmos DB or other non-relational service is configured. |
| Unstructured | Uploaded room photographs | Private local filesystem implementation; no Azure Blob Storage integration or cloud persistence is verified. |

The SQL Server scripts under `database/migrations/` are a proposed Azure SQL coursework target, not proof of a hosted relational database. The tracked Power BI file is zero bytes, so it is not an analytics report.

## One-page threat model

| Asset / trust boundary | Entry points | Threat scenario | Existing mitigation in local code | Residual risk / action |
|---|---|---|---|
| User account and session | Registration/login/recovery pages and `/api/auth/*`; signed-session browser requests | Credential guessing, stolen cookie, CSRF | Scrypt password hashing, rate-limit buckets, session version, HttpOnly/SameSite settings, CSRF checks | Verify production HTTPS/cookie behavior and operational rate limits; do not treat code review as penetration testing. |
| Home/room data | Home-scoped `/api/homes/<home_id>/*` requests and browser pages | A user accesses another household's routes or resources | Home membership and role checks in request paths; unauthorized home membership may be hidden as 404 | Test all routes and same-home integrity; active database lacks some composite same-home foreign keys. |
| Sensor endpoint | `POST /api/sensors/<sensor_id>/readings`, sensor provisioning and key rotation | Attacker guesses/steals a device key or replays invalid data | Random device keys, keyed hashes, constant-time comparison, sensor revocation, validation and rate limits | Protect one-time provisioning response and pepper; hardware key storage/replay threat review is not available. |
| Reading/alert integrity | Device JSON, owner demo-reading requests, threshold updates | Malformed, stale, future, unit-confused, or duplicate readings | Payload validation, unit normalization, time bounds, unique reading key, transactional processing and alert constraints | Threshold values require documented provenance; real sensor accuracy and deployments are unverified. |
| CSV replay | Multipart CSV/TXT upload to the owner-only replay route | Oversized or malformed input, unsafe spreadsheet output | File and row limits, parser validation, duplicate handling, CSV cell-safety logic | Fuzzing and resource-exhaustion tests are not claimed. |
| Email and invitations | OTP/recovery/invitation routes and outbound Brevo API request | Token disclosure, account enumeration, failed delivery | Hashed invitation/challenge tokens, invited-email check, generic OTP response, expiry and attempt state | Provider setup, sender authentication, delivery, and secret/log handling need live verification. Invitation creation also returns a one-time token in its JSON response. |
| Private uploads | Room-photo multipart upload and authorized photo retrieval/deletion routes | Unauthorized file retrieval or path traversal | Home membership checks, private directory, filename/content checks, response safety headers | Filesystem permissions, persistence, backups, and production storage controls are not verified. |
| Database/deployment | Database URL and credentials, migrations, local instance files, Render configuration | Database exposure, lost data, leaked credentials | ORM use, SQLite FK enforcement, migration tooling, environment-based settings | Azure network rules, least privilege, backups/restore, monitoring, production secrets, and incident response remain unverified. |

## Assumptions and limitations

This analysis assumes the code paths inspected are the deployed code, an assumption that cannot be confirmed without deployment evidence. Threat likelihood and impact have not been independently measured. No third-party security assessment, cloud configuration export, privacy notice, consent flow, retention schedule, or incident-response procedure was found in the repository.
