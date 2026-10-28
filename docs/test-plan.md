# AirSense test plan

## Purpose and status

This plan describes verification for the proposed requirements. Tests should be added alongside features; unimplemented flows must be reported as not applicable/not implemented rather than passed. The current repository's executable tests are the source of truth for implemented behavior; see [implementation status](./PRD.md).

## Unit tests

- Threshold comparisons at just-below, equal-to, and just-above boundaries.
- Duration/consecutive-sample rules, rapid-rise logic, all-clear behavior, and long data gaps.
- Input validation for types, permitted ranges, timestamps, units, and required fields.
- Sensor freshness calculations, including missing and stale readings.
- Role and room-membership permission decisions.
- Simulated/device source labelling and alert wording.

## API tests

- Valid authenticated reading ingestion persists measurement and receipt timestamps.
- Malformed, out-of-range, duplicate, stale, or future-dated payloads are rejected.
- Unauthorized or unknown devices cannot submit readings.
- Unauthenticated users cannot access protected routes.
- Standard users cannot manage rooms/sensors or alter thresholds.
- Users cannot access rooms outside their assigned scope.
- Alert creation, duplicate prevention, acknowledgement, and authorized status changes behave as specified.
- Responses use documented status codes and do not disclose secrets or internal stack traces.

## Database tests

- Primary/foreign key, uniqueness, check, and required-field constraints.
- Required indexes and expected query plans for common bounded history queries.
- Joins and latest-reading view return correct results.
- Reading plus alert changes commit atomically.
- Failed writes roll back without orphan readings or partial alerts.
- Migration upgrade and downgrade behavior, where downgrade is supported.

## Integration and end-to-end tests

- Frontend-to-API flows for login, dashboard, history, alerts, and role-gated management.
- API-to-database connectivity and transaction behavior using a test database.
- Azure SQL, Blob Storage, and Power BI connectivity only in an explicitly configured deployment/integration environment.
- Sensor or simulator ingestion through the same validation and threshold path.
- Responsive layout, keyboard access, readable status labels, empty/error/loading states, and stale/offline indicators.

## Security checks

- Cross-role and cross-room authorization tests.
- SQL injection payloads are treated as data and do not alter query structure.
- Output escaping and unsafe markup handling.
- Secret scanning and verification that example configuration contains no real credentials.
- HTTPS, CORS, security headers, database firewall, and least-privilege deployment review.
- Rate/size limit checks on public or device-facing endpoints.
- Audit events capture required actions without secrets.

## Demo and release checklist

- Label every simulated value as simulated/demo in the UI and exported reports.
- Verify that the displayed unit, timestamp, source, sensor status, and applicable threshold are clear.
- Run the repository's focused test commands and record actual results; do not claim Azure or hardware integration from local-only tests.
- Capture deployment evidence only after the deployed resource is reachable and configured.
- Confirm no medical, diagnosis, or guaranteed safety claims are made.