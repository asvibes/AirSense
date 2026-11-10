# ER diagram and active database design

## Schema status

This diagram summarizes the active SQLAlchemy model classes in `app/models/`, not the separate Azure SQL proposal under `database/migrations/`. The current metadata contains 13 application tables. Alembic adds its own `alembic_version` bookkeeping table when migrations are applied.

### Rendered diagram

The high-resolution diagram includes every active model table, field, key/FK marker, and relationship/cardinality summary:

- [ER diagram PNG](diagrams/er_diagram.png)
- [Editable ER diagram SVG source](diagrams/er_diagram.svg)

```mermaid
erDiagram
    HOMES ||--o{ HOME_MEMBERSHIPS : has
    USERS ||--o{ HOME_MEMBERSHIPS : joins
    HOMES ||--o{ HOME_INVITATIONS : issues
    USERS ||--o{ HOME_INVITATIONS : creates
    USERS o|--o{ EMAIL_CHALLENGES : may_own
    HOMES ||--o{ ROOMS : contains
    HOMES ||--o{ SENSORS : registers
    ROOMS ||--o{ SENSORS : assigned
    HOMES ||--o{ THRESHOLD_POLICIES : scopes
    ROOMS ||--o{ THRESHOLD_POLICIES : configures
    METRICS ||--o{ THRESHOLD_POLICIES : applies_to
    HOMES ||--o{ AIR_READINGS : stores
    ROOMS ||--o{ AIR_READINGS : locates
    SENSORS o|--o{ AIR_READINGS : may_source
    METRICS ||--o{ AIR_READINGS : measures
    HOMES ||--o{ AIR_ALERTS : scopes
    ROOMS ||--o{ AIR_ALERTS : concerns
    METRICS ||--o{ AIR_ALERTS : classifies
    HOMES ||--o{ AUDIT_LOGS : records
    USERS o|--o{ AUDIT_LOGS : may_act

    HOMES {
        string id PK
        string name
    }
    USERS {
        string id PK
        string email UK
        string display_name
        string password_hash
        int session_version
        boolean is_active
        datetime email_verified_at
        datetime created_at
    }
    HOME_MEMBERSHIPS {
        string home_id PK, FK
        string user_id PK, FK
        string role
        datetime joined_at
    }
    HOME_INVITATIONS {
        string id PK
        string home_id FK
        string email
        string token_hash UK
        string created_by FK
        datetime created_at
        datetime expires_at
        datetime accepted_at
    }
    EMAIL_CHALLENGES {
        string id PK
        string user_id FK
        string email
        string purpose
        string otp_hash
        datetime created_at
        datetime expires_at
        datetime last_sent_at
        int attempts
        datetime consumed_at
        string reset_token_hash UK
        datetime reset_token_expires_at
        datetime reset_token_used_at
    }
    RATE_LIMIT_BUCKETS {
        string key PK
        datetime window_started_at
        int count
    }
    ROOMS {
        string id PK
        string home_id FK
        string name
        string ventilation
        json ventilation_sources
    }
    SENSORS {
        string id PK
        string home_id FK
        string room_id FK
        string name
        string key_hash UK
        string status
        int reporting_interval_seconds
        datetime last_seen_at
        datetime created_at
    }
    METRICS {
        string code PK
        string name
        string unit
    }
    THRESHOLD_POLICIES {
        int id PK
        string home_id FK
        string room_id FK
        string metric_code FK
        float high_threshold
        float elevated_threshold
        int elevated_duration_seconds
        float rapid_rise_per_minute
        int all_clear_duration_seconds
        int max_reading_gap_seconds
        datetime elevated_since
    }
    AIR_READINGS {
        int id PK
        string home_id FK
        string room_id FK
        string sensor_id FK
        string metric_code FK
        float value
        string source
        datetime measured_at
        datetime received_at
    }
    AIR_ALERTS {
        int id PK
        string home_id FK
        string room_id FK
        string metric_code FK
        string level
        string status
        float trigger_value
        float threshold_value
        float latest_value
        string threshold_unit
        int clear_duration_seconds
        datetime below_threshold_since
        datetime created_at
        datetime acknowledged_at
        string acknowledged_by
        datetime all_clear_at
        text detail
    }
    AUDIT_LOGS {
        int id PK
        string home_id FK
        string actor_user_id FK
        string event_type
        string entity_type
        string entity_id
        text details_json
        datetime created_at
    }
```

## Relationships and constraints

- A membership is identified by the composite `(home_id, user_id)` key; application roles currently use `owner` and `member`.
- Room names are unique within a home, including a case-insensitive unique functional index.
- Sensor status is constrained to active/revoked; reporting intervals are constrained to 30–86,400 seconds. Device-key hashes are unique.
- Threshold policies are unique for a home, room, and metric. Policies are current values and are not effective-dated in the active ORM schema.
- Readings have uniqueness across home, room, metric, and measured time. `received_at` is nullable for historic rows.
- Active/acknowledged alerts use a filtered unique index by home, room, metric, and level. Alert status/level and transition metadata have checks.
- Email OTP/reset challenge records store hashes and expiry/attempt state. Rate-limit counters are persisted in the database.
- `email_challenges` contains nullable `user_id`, `consumed_at`, and reset-token state; `rate_limit_buckets` is independent and has no declared foreign key.

## Data dictionary

The following describes the purpose of each active ORM attribute. `PK` and `FK` are shown in the ER diagram above. Nullable timestamps/IDs can be empty until the associated event occurs.

| Entity | Attribute | Meaning |
|---|---|---|
| `homes` | `id`, `name` | Home identifier and display name. |
| `users` | `id`, `email`, `display_name` | Account identifier, unique login email, and displayed name. |
|  | `password_hash`, `session_version` | Scrypt password hash and session invalidation counter; never store the raw password. |
|  | `is_active`, `email_verified_at`, `created_at` | Account enabled state, email verification time, and creation time. |
| `home_memberships` | `home_id`, `user_id`, `role`, `joined_at` | Home/user association, `owner` or `member` role, and membership time. The two IDs form the composite primary key. |
| `home_invitations` | `id`, `home_id`, `email`, `role` | Invitation identifier, target home/address, and role granted on acceptance. |
|  | `token_hash`, `created_by`, `created_at`, `expires_at`, `accepted_at` | Stored token digest, inviting user, issue/expiry times, and one-time acceptance time. |
| `email_challenges` | `id`, `user_id`, `email`, `purpose` | Challenge identifier, optional linked account, target address, and verification/reset purpose. |
|  | `otp_hash`, `created_at`, `expires_at`, `last_sent_at`, `attempts`, `consumed_at` | OTP digest, issue/expiry/resend times, attempt counter, and consumption time. |
|  | `reset_token_hash`, `reset_token_expires_at`, `reset_token_used_at` | Optional reset-token digest, expiry, and one-time use time. |
| `rate_limit_buckets` | `key`, `window_started_at`, `count` | Rate-limit scope key, current window start, and requests counted in that window. |
| `rooms` | `id`, `home_id`, `name` | Room identifier, containing home, and room name. |
|  | `ventilation`, `ventilation_sources` | Legacy joined display string and JSON list of ventilation source labels. |
| `sensors` | `id`, `home_id`, `room_id`, `name` | Sensor identifier, associated home/room, and display name. |
|  | `key_hash`, `status`, `reporting_interval_seconds` | Keyed device-credential digest, active/revoked state, and expected reporting interval. |
|  | `last_seen_at`, `created_at` | Time of most recent accepted device reading and provision time. |
| `metrics` | `code`, `name`, `unit` | Metric code (primary key), display name, and canonical unit. |
| `threshold_policies` | `id`, `home_id`, `room_id`, `metric_code` | Policy identifier and home/room/metric scope. |
|  | `high_threshold`, `elevated_threshold`, `elevated_duration_seconds` | High value, sustained-elevated value, and required elevated duration. |
|  | `rapid_rise_per_minute`, `all_clear_duration_seconds`, `max_reading_gap_seconds` | Rapid-rise rate, clear duration, and largest allowed gap between readings for evaluation. |
|  | `elevated_since` | Start time tracked for a currently sustained elevated condition. |
| `air_readings` | `id`, `home_id`, `room_id`, `sensor_id`, `metric_code` | Reading identifier, home/room, optional originating sensor, and measured metric. |
|  | `value`, `source`, `measured_at`, `received_at` | Numeric value, provenance label, event/measurement time, and server receipt time (nullable for some historical records). |
| `air_alerts` | `id`, `home_id`, `room_id`, `metric_code` | Alert identifier and home/room/metric scope. |
|  | `level`, `status`, `trigger_value`, `threshold_value`, `latest_value`, `threshold_unit` | Alert classification/state and values/units used to describe its condition. |
|  | `clear_duration_seconds`, `below_threshold_since`, `created_at` | Clear timing policy, time below threshold, and alert creation time. |
|  | `acknowledged_at`, `acknowledged_by`, `all_clear_at`, `detail` | Acknowledgement metadata, all-clear time, and explanatory text. |
| `audit_logs` | `id`, `home_id`, `actor_user_id` | Event identifier, home scope, and optional acting user. |
|  | `event_type`, `entity_type`, `entity_id`, `details_json`, `created_at` | Event classification, affected entity reference, JSON details, and event time. |

These descriptions explain application semantics; they do not add database constraints beyond those listed above and shown in the ORM/migrations.

## Important integrity limitation

Several rows hold both `home_id` and `room_id`, while independent foreign keys ensure each referenced row exists. The active schema does not use composite foreign keys to ensure those two references always belong to the same home. Application routes enforce home/room membership in normal flows, but direct SQL or future code can still create an inconsistent association. A reading's optional sensor reference likewise is not constrained by a composite home/room relationship.

## Migration chain

The active Alembic chain is `20261027_0001` → `20261028_0002` → `20261028_0003` → `20261105_0004` → `20261107_0005` → `20261108_0006` → `20261108_0007` → `20261108_0008`. It adds core schema, room ventilation sources, nullable reading receipt time, email challenge/reset state, rate limits, and email-verification state. Local tests exercise migration paths on disposable SQLite databases. This does not verify a production migration or Azure SQL compatibility.

## Design references

The canonical model definitions are in `app/models/`; migration files are in `migrations/versions/`. See [document 5](05_sql_artifacts_and_schema_status.md) before considering the SQL Server target scripts. The existing [data-model document](../../docs/data-model.md) is useful background but predates some active authentication tables; this diagram includes those current models.
