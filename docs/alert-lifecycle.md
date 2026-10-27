# Alert lifecycle

## Rules and state

Each threshold policy is scoped to a home, room, and metric:

* **High:** a reading at or above `high_threshold` opens a High alert immediately.
* **Elevated:** a reading at or above `elevated_threshold` starts a timer. The alert opens only after samples remain elevated for `elevated_duration_seconds`. A sample gap greater than `max_reading_gap_seconds` restarts the timer. A High reading takes precedence over Elevated.
* **Rapid rise:** a reading creates a Rapid Rise alert when its increase over the preceding sample, expressed per minute, reaches `rapid_rise_per_minute`.
* **All clear:** for each open alert, samples must remain strictly below its captured trigger threshold for `all_clear_duration_seconds`. Samples separated by a gap greater than `max_reading_gap_seconds` restart the timer. The threshold is captured when the alert opens, so later policy changes do not silently change its clear condition.

Acknowledgement is independent from resolution: an acknowledged alert remains open, continues to receive readings, and can transition to All clear. Repeated acknowledgement is idempotent and preserves the original member label and timestamp. A later breach after All clear creates a new alert.

The filtered unique index on `(home_id, room_id, metric_code, level)` for `active` and `acknowledged` alerts is the final duplicate guard; the same transition logic runs within one database transaction.

## API

* `POST /api/policies` stores a room/metric rule set.
* `POST /api/readings` stores a timestamped reading and evaluates the rule set in the same transaction.
* `POST /api/alerts/{id}/acknowledge` records an acknowledgement.
* `GET /api/alerts` lists alert history.

When `REQUIRE_API_TOKEN=true`, each application endpoint requires `Authorization: Bearer <AIRSENSE_API_TOKEN>`. `/api/health` remains available for the hosting health check.

## Data and deployment caveats

The models and Alembic migration target SQLite for local development and PostgreSQL for Render. The demo reads are not yet authenticated sensor ingestion; it has no user accounts, home membership enforcement, or device-key hashes. Default alert thresholds are examples only and must be replaced with cited, metric-appropriate guidance before household use.
