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

## Important integrity limitation

Several rows hold both `home_id` and `room_id`, while independent foreign keys ensure each referenced row exists. The active schema does not use composite foreign keys to ensure those two references always belong to the same home. Application routes enforce home/room membership in normal flows, but direct SQL or future code can still create an inconsistent association. A reading's optional sensor reference likewise is not constrained by a composite home/room relationship.

## Migration chain

The active Alembic chain is `20261027_0001` → `20261028_0002` → `20261028_0003` → `20261105_0004` → `20261107_0005` → `20261108_0006` → `20261108_0007` → `20261108_0008`. It adds core schema, room ventilation sources, nullable reading receipt time, email challenge/reset state, rate limits, and email-verification state. Local tests exercise migration paths on disposable SQLite databases. This does not verify a production migration or Azure SQL compatibility.

## Design references

The canonical model definitions are in `app/models/`; migration files are in `migrations/versions/`. See [document 5](05_sql_artifacts_and_schema_status.md) before considering the SQL Server target scripts. The existing [data-model document](../../docs/data-model.md) is useful background but predates some active authentication tables; this diagram includes those current models.
