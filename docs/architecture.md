# AirSense architecture

## Status and scope

This document describes the proposed target architecture and distinguishes it from the current prototype. The current branch is a Flask application with a server-served HTML/CSS/vanilla-JavaScript preview and a relational SQLAlchemy backend. The preview currently uses browser-local illustrative values and does not call the backend APIs. Accounts, household authorization, real device provisioning, Azure services, and Power BI are not implemented; see [implementation status](./PRD.md).

The proposed academic MVP is a modular monolith with a web frontend, Flask REST API, Azure SQL Database, Azure Blob Storage for files, and a separate Power BI report. A React frontend is a proposed direction, not a description of the current UI.

## Proposed components

| Component | Responsibility |
| --- | --- |
| Web frontend | Authenticated room dashboard, history, alerts, threshold controls, and administration views. |
| Flask API | User and device authentication, authorization, validation, ingestion, status evaluation, alert lifecycle, and audit events. |
| Azure SQL Database | Operational relational data: accounts, roles, rooms, sensors, readings, thresholds, alerts, and audit records. |
| Sensor/gateway | Sends measurements to a device-specific, authenticated ingestion endpoint. |
| Simulator | Supplies clearly labelled demo readings through the same validation/evaluation path as device readings. |
| Azure Blob Storage | Stores reports or supporting files; it is not the operational database. |
| Power BI | Reads a controlled, preferably read-only historical dataset for descriptive reporting. |

## Proposed reading flow

1. A physical CO2 sensor or labelled simulator produces a value and measurement time.
2. A registered device authenticates to the ingestion endpoint over HTTPS.
3. The API validates identity, payload, value range, and timestamp. Invalid requests are rejected without changing stored data.
4. In a database transaction, the API stores the reading and evaluates the applicable room threshold policy.
5. An alert is created or updated according to the documented lifecycle and duplicate-prevention rules.
6. Authorized frontend requests retrieve bounded dashboard, history, and alert data.
7. A controlled analytics connection exposes historical records to Power BI.

## Trust boundaries and controls

- **Browser to API:** HTTPS, user session/token validation, server-side role and room checks, CSRF protection when cookie sessions are used, and input validation.
- **Device to ingestion API:** Per-device credentials, revocation/rotation, request size and rate limits, timestamp/range validation, and no access to user routes.
- **API to database:** Parameterized ORM/SQL access, least-privilege credentials, network restrictions, migrations, and transactions for related writes.
- **Analytics and file storage:** Read-only analytics credentials where possible; private containers and short-lived scoped access for files.
- **Secrets/configuration:** Deployment secret settings, never committed to source control or included in logs.

## Proposed API surface

The candidate endpoints are listed in the [product requirements](./product-requirements.md#72-proposed-api). Endpoint names, session/token choice, pagination shape, and error schema should be finalized in an API contract before implementation. This list is not a claim that those endpoints exist today.

## Deployment and operational decisions

- Begin with one modular API application and one relational database rather than microservices.
- Use time-bounded/paginated history queries and indexes before considering caching.
- Make stale-sensor logic explicit and return the last measurement time and freshness status to clients.
- Keep simulated data distinguishable from device measurements in storage and presentation.
- Confirm student credits, regional availability, Azure resource costs, and Power BI licensing before choosing deployment services.
- Deploy HTTPS and database firewall/network restrictions before using real household data.

## Current prototype constraints

The README documents the routes and local run instructions for the current prototype. Its frontend is a standalone preview, backend access may use an optional shared bearer token, and the backend does not yet provide account-level room permissions or device-key authentication. Do not use it with private household data.