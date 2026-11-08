# AirSense security checklist

This checklist separates controls present in the local application from controls that require deployment evidence. A code-level control is not proof of secure production configuration. Coverage is selective and does not establish every checklist item.

## Implemented locally (code evidence; tests cover selected paths)

- [x] Passwords are validated and hashed using Werkzeug's scrypt password-hashing implementation; plaintext passwords are not stored.
- [x] Flask session cookies are configured HttpOnly and SameSite; session lifetime is configured. Secure-cookie mode is enabled for production configuration.
- [x] Session-authenticated mutations require CSRF validation.
- [x] Security response headers include content-type protection, clickjacking protection, referrer policy, permissions policy, and a CSP; HSTS is conditional on secure production requests.
- [x] Authentication, device, invitation, simulator, and replay abuse limits use persistent database-backed buckets shared across workers.
- [x] Forwarded client headers are ignored by default; `TRUSTED_PROXY_HOPS` must explicitly configure a known proxy chain before proxy-derived client data is trusted.
- [x] Email verification state is stored separately from account activation; the migration backfills only legacy active users and never reactivates inactive accounts.
- [x] Home-scoped routes enforce membership and owner/member permissions server-side. Selected access-control tests cover unauthenticated access, home isolation, and member restrictions.
- [x] Each provisioned sensor has a separate random device key; only a peppered hash is stored. Owners can rotate keys and revoke sensors. The one-time key response is secret.
- [x] Reading payloads are validated for expected structure, metric/unit syntax, finite non-negative value, timestamp format/timezone, future timestamps, sensor identity, and room match. Database uniqueness prevents duplicate home/room/metric/timestamp readings.
- [x] ORM expressions are used by application database queries. Dashboard-rendered values are HTML-escaped by the frontend helper.
- [x] History queries require home membership, use a time range, and cap results. CSV export is home-authorized and streamed; it is not stored in Blob Storage.
- [x] CSV export prefixes text cells whose first non-whitespace/control character is a spreadsheet formula marker with a text apostrophe; numeric readings, timestamps, headers, and ordinary text remain unchanged.
- [x] Audit details for implemented events avoid storing passwords, invitation tokens, or raw device keys. Tests check selected audit cases.
- [x] Rejected readings after authenticated device validation or authenticated simulator/DALTON ingestion are recorded as `reading.rejected` with only a fixed reason code and source; raw payloads and credentials are excluded. DALTON batch rollback is followed by one rejection event, not partial reading/alert events.
- [x] Failed device authentication for an existing sensor is recorded as `sensor.authentication_failed` in that sensor's home, with no supplied credential in the event. Unknown sensor IDs have no home-scoped event because there is no trustworthy home context.
- [x] Known-account login failures, successful login, and logout are audited against the user's home memberships. Unknown-account login failures and unauthenticated/invalid requests without a trusted home context do not create household audit events.
- [ ] Rejections before a reading reaches shared ingestion (for example malformed simulator requests, missing/invalid DALTON files, invalid CSV rows filtered during parsing, unknown rooms, and rate-limited requests) are not recorded as household audit events. Operational security monitoring for those request-level failures is not implemented.

## Incomplete or unverified locally

- [ ] Implement and audit the PRD's facility-manager/administrator roles and role-change action. Current roles are home-scoped `owner` and `member`.
- [ ] Add/verify an end-to-end browser flow for login, dashboard, and role-gated actions. The current suite tests backend/API/service behavior, not browser E2E.
- [ ] Extend rollback tests to cover forced database failures across individual ingestion paths. DALTON replay tests already force a later-row validation failure and verify no partial readings, alerts, or ingestion/alert audit events remain.
- [ ] Verify metric-specific value ranges; the general reading validator accepts any finite non-negative number, rather than enforcing a universal CO₂ range in the database.
- [ ] Decide and document retention, account deletion, audit retention, backup/recovery, and incident-response policy.
- [ ] Run dependency vulnerability and secret scanning in CI and record results. No result is claimed here.
- [ ] Complete a project-specific threat model and data-classification note. The prompts below are not themselves a completed threat model.

## Deployment controls (future/unverified)

- [ ] Require and verify HTTPS for deployed frontend and API traffic.
- [ ] Store signing, database, and device secrets in protected deployment configuration; verify there are no real credentials in the Git index.
- [ ] Use a least-privilege hosted database identity and restrict database network access to required application sources.
- [ ] Keep any Blob Storage container private and grant scoped/time-limited access. Blob integration is not implemented.
- [ ] Verify HTTPS, HSTS behavior, CSP compatibility, and CORS policy on the deployed host.
- [ ] Verify the production host's session-cookie, proxy, rate-limiting, request-size, backup, and recovery settings.
- [ ] If hosted PostgreSQL or Azure SQL is selected, run compatibility and migration checks against that actual backend. No PostgreSQL or cloud integration test has passed as part of the current evidence.
- [ ] If Power BI is delivered, use a controlled/read-only data connection and verify report access and data handling.

## Threat-model prompts

The following are prompts for the threat-model deliverable, not completed findings:

- A user attempts to read or alter another home's data, change a role, or acknowledge an alert without permission.
- A stolen/replayed device key or fabricated sensor submits readings.
- Malformed timestamps, extreme values, duplicate submissions, or request flooding affect processing.
- Database/storage credentials are exposed through source control, logs, or public containers.
- A user mistakes simulated readings or threshold labels for medical/safety advice.
- Backups, audit records, or user information are retained longer or exposed more broadly than intended.

Document assets, actors, entry points, trust boundaries, abuse cases, mitigations, and residual risks before marking the threat-model requirement complete. AirSense is a ventilation-support demo, not a medical or safety device; it does not replace a certified carbon monoxide alarm.
