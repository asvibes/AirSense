# AirSense data model

## Status

This document describes a proposed target schema for the academic MVP. It is not a schema inventory or evidence that all listed entities are implemented. The current branch uses SQLAlchemy models and migrations for the alert lifecycle; see [implementation status](./PRD.md) and the existing alert lifecycle documentation.

## Proposed entities

| Entity | Key attributes | Relationships / purpose |
| --- | --- | --- |
| `Users` | `user_id` PK, name, unique email, password hash, `role_id` FK, created time, active flag | Account identity; never store the raw password. |
| `Roles` | `role_id` PK, unique role name | Defines standard user, facility manager, and administrator permissions. |
| `Rooms` | `room_id` PK, name, location label, `manager_user_id` FK, created time | A room belongs to a facility/home boundary and has authorized members/managers. |
| `Sensors` | `sensor_id` PK, credential reference/hash, `room_id` FK, sensor type, status, last seen | Registered measurement source assigned to a room. |
| `CO2Readings` | `reading_id` PK, `sensor_id` FK, ppm, measured time, received time, source | Immutable measured and server-received measurement record. |
| `Thresholds` | `threshold_id` PK, `room_id` FK, elevated/high values, effective time, `updated_by` FK | Versioned room policy and attribution for changes. |
| `Alerts` | `alert_id` PK, room/sensor/reading FKs, threshold snapshot, severity, created time, status, nullable acknowledger FK | A rule event, linked to the evidence that generated it. |
| `ActivityLogs` | `log_id` PK, nullable user FK, action, target type/ID, time, outcome | Security-sensitive and administrative event history. |

## Data integrity and normalization

- Separate roles, users, rooms, sensors, readings, threshold policies, alerts, and activity events rather than repeating descriptive data across readings.
- Use foreign keys for relationships and appropriate `NOT NULL`, `UNIQUE`, and `CHECK` constraints.
- Constrain ppm values to the sensor/project-supported range; validate units and metric identity at the API boundary as well.
- Store measurement time separately from server receipt time. Preserve timezone-aware timestamps (normally UTC).
- Retain source provenance (`device`, `simulated`, or an approved dataset source) so demo values cannot be mistaken for physical measurements.
- Version or snapshot thresholds so historical alert interpretation remains explainable after a policy changes.
- Avoid storing unnecessary personal data. Device secrets and passwords must never be stored in raw form.

## Indexes and query patterns

Candidate indexes:

- `CO2Readings(sensor_id, measured_at)` for sensor history.
- `Sensors(room_id, status)` for room inventory.
- `Rooms(manager_user_id)` and membership/assignment join keys for authorization.
- `Alerts(room_id, status, created_at)` for active and recent alerts.
- `Thresholds(room_id, effective_from)` for selecting the policy applicable to a reading.

Use bounded time ranges and pagination for reading history. Query authorization boundaries as part of the server-side data access path rather than relying on client-supplied room IDs alone.

## Required course evidence

The submission should include a reviewed ER diagram and schema/query scripts demonstrating:

- Primary and foreign keys, constraints, and indexes.
- Multi-table joins.
- A view such as latest reading per room.
- A stored procedure or trigger, if supported by the selected database and course requirements.
- A transaction that stores a valid reading and any corresponding alert atomically.
- Transaction rollback tests proving invalid or failed alert creation does not leave partial state.

The proposed Azure SQL scripts are in [`database/migrations/`](../database/migrations/) with their execution notes in [`database/README.md`](../database/README.md). They are a separate target schema and are not applied by the app. The current local prototype uses SQLAlchemy and SQLite by default; do not describe the target schema as deployed until deployment and verification are complete.