# AirSense security checklist

Use this checklist for implementation and deployment review. A checked item should be backed by test or deployment evidence; this document is a plan, not evidence that a control is already deployed. Current limitations are summarized in [implementation status](./PRD.md).

## Identity and authorization

- [ ] Hash passwords with a password-specific algorithm (for example Argon2id, bcrypt, or a vetted framework helper); never log or store plaintext passwords.
- [ ] Use secure login/logout behavior, session/token expiry, and appropriate cookie protections if cookie sessions are used.
- [ ] Enforce role checks and room/facility membership on every protected server route.
- [ ] Deny by default; test cross-room and cross-role access attempts.
- [ ] Authenticate each sensor/gateway independently; support revocation and credential rotation.
- [ ] Do not use a shared unrestricted device-ingestion credential.

## Transport, configuration, and infrastructure

- [ ] Require HTTPS for deployed frontend and API traffic.
- [ ] Keep database credentials, signing keys, and device credentials in deployment secrets or protected configuration.
- [ ] Keep `.env` files and all real credentials out of version control; commit only placeholders in `.env.example`.
- [ ] Use least-privilege database identities and restrict database network access to required application sources.
- [ ] Keep Blob Storage containers private and grant scoped, time-limited access only when needed.
- [ ] Configure secure response headers and review CORS policy for the deployed origins.

## Input, database, and application behavior

- [ ] Validate request shape, allowed fields, types, sizes, identifiers, metric/unit, ppm range, and timezone-aware timestamps.
- [ ] Reject malformed, stale, future-dated, duplicate, or unauthorized readings according to documented rules.
- [ ] Use parameterized queries or ORM expressions; never build SQL from untrusted input.
- [ ] Escape untrusted output and avoid unsafe HTML rendering.
- [ ] Apply request/body limits and rate limits appropriate to user and device endpoints.
- [ ] Use transactions for reading/alert writes and verify rollback behavior.
- [ ] Keep historical queries bounded and protect file/report downloads with authorization.

## Audit, privacy, and operations

- [ ] Record authentication outcomes, role changes, sensor provisioning/revocation, threshold updates, and administrative actions.
- [ ] Do not log passwords, tokens, device secrets, or other raw credentials.
- [ ] Limit collected personal information to what the service needs; avoid personal health data.
- [ ] Define retention and access rules for readings, alerts, and audit events.
- [ ] Label simulated data in storage and all relevant UI/report views.
- [ ] Scan dependencies and repository content for known vulnerabilities and accidentally committed secrets.
- [ ] Prepare backup/recovery and incident response steps appropriate to deployment.

## Threat-model prompts

Document assets, actors, entry points, trust boundaries, abuse cases, mitigations, and residual risks. At minimum consider:

- A user attempting to read or alter another room's data.
- A stolen/replayed device credential or fabricated sensor reading.
- Malformed timestamps, extreme values, duplicate submissions, and request flooding.
- Database or storage credentials exposed through source control, logs, or public containers.
- Unauthorized acknowledgement, threshold changes, role changes, or audit-log access.
- Users mistaking simulated readings or threshold labels for medical/safety advice.

## Current implementation caveat

The prototype has an optional shared bearer-token guard, not full user accounts, room-level authorization, or per-device keys. Treat it as a demo only and do not enter private household data. See the [README](../Readme.md) and [implementation status](./PRD.md).