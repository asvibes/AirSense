# AirSense

AirSense is a responsive indoor-air-quality project that turns sensor readings into room-wise statuses, alerts, history, and ventilation guidance. It consumes readings; it does not measure air quality itself.

The current runnable slice implements the alert lifecycle from the PRD:

* **High:** opens immediately when a reading reaches the configured high threshold.
* **Elevated:** opens only after consecutive readings stay at or above the configured elevated threshold for the configured duration.
* **Rapid rise:** opens when the rate of increase between consecutive readings reaches the configured rate.
* **Acknowledgement:** records a display name and timestamp. Repeating acknowledgement does not overwrite the original acknowledgement.
* **All clear:** an open alert clears only after readings remain below its applicable threshold for the alert's configured duration. Missing samples or gaps beyond the configured maximum restart the timer.
* **Duplicate prevention:** a PostgreSQL/SQLite partial unique index allows at most one open alert for a home, room, metric, and level. A new breach after all-clear creates a new alert.

## Status and scope

The alert vertical slice and a basic Flask UI/API are implemented. The original repository has no recoverable feature implementation in its history: commit `bbf7ad6` (`Added files empty`) added the empty placeholders. The attached product requirements are broader than this slice. Registration, household membership and role checks, sensor provisioning/authentication, the general dashboard, history/CSV, audit log, simulator/replay ingestion, and Power BI integration remain future work; the current alert UI/API is not a complete household application.

The demo threshold defaults are **illustrative configuration values, not sourced health or safety guidelines**. Set metric-specific values and durations for the intended sensor and cite their source before household use. Alert acknowledgements use caller-supplied display labels; they are not authenticated identities. A bearer API token can restrict write endpoints, but it does not replace user accounts, roles, or per-device credentials. Do not put personal or household sensor data on a public deployment until authentication and home-level authorization are implemented.

AirSense is a ventilation-support tool, not a medical or safety device. It does not replace a certified carbon monoxide alarm.

## Run locally

Requires Python 3.10 or later.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m alembic upgrade head
python -m flask --app "app.main:create_app()" run
```

Open `http://127.0.0.1:5000/alerts`. For local development, the default database is SQLite at `instance\airsense.sqlite3`. Alembic applies the versioned schema. Set `DATABASE_URL` to use another SQLAlchemy URL.

Run tests with:

```powershell
python -m unittest discover -s tests -v
```

## Configuration

Copy `.env.example` to `.env` and export its values in your shell or hosting environment. The app does not load `.env` files automatically.

| Variable | Purpose | Demo default |
| --- | --- | --- |
| `DATABASE_URL` | SQLAlchemy database URL; PostgreSQL URLs are adapted to psycopg 3 | local SQLite |
| `SECRET_KEY` | Flask secret key | development-only fallback |
| `AIRSENSE_HIGH_THRESHOLD` | Immediate High threshold, in the configured metric's unit | `1500` |
| `AIRSENSE_ELEVATED_THRESHOLD` | Sustained Elevated threshold | `1000` |
| `AIRSENSE_ELEVATED_DURATION_SECONDS` | Required sustained Elevated duration | `300` |
| `AIRSENSE_RAPID_RISE_PER_MINUTE` | Rapid-rise threshold in metric units per minute | `200` |
| `AIRSENSE_ALL_CLEAR_DURATION_SECONDS` | Required below-threshold duration before clearing | `300` |
| `AIRSENSE_MAX_READING_GAP_SECONDS` | Larger sample gaps reset sustained timers | `120` |
| `AIRSENSE_API_TOKEN` | Shared bearer token for hosted application routes | unset |
| `REQUIRE_API_TOKEN` | Require the token on application routes | `false` |

Set `REQUIRE_API_TOKEN=true` and a random `AIRSENSE_API_TOKEN` of at least 32 characters before exposing application routes. API clients then send `Authorization: Bearer <token>`. This shared token is a deployment guard, not household-member authentication. The hosted browser UI also requires this header; interactive account login is not implemented yet.

## API

* `GET /api/health` checks application/database availability.
* `GET /api/alerts?home_id=demo-home` lists alert history (all homes if no filter is supplied).
* `POST /api/policies` configures the alert thresholds and durations for one home/room/metric. Its JSON body includes `room`, `metric`, `unit`, `high_threshold`, `elevated_threshold`, `elevated_duration_seconds`, `rapid_rise_per_minute`, `all_clear_duration_seconds`, and `max_reading_gap_seconds`.
* `POST /api/readings` records and evaluates a reading. Example:

```json
{
  "home_id": "demo-home",
  "home_name": "Demo Home",
  "room": "Bedroom",
  "metric": "CO2",
  "unit": "ppm",
  "value": 1650,
  "source": "simulated",
  "measured_at": "2026-10-27T06:35:00Z"
}
```

`source` is `dataset`, `simulated`, or `device`. `measured_at` is an optional ISO-8601 timestamp with timezone. The response includes newly created alerts, all-clear transitions, and active alerts. Replayed timestamps must be newer than the latest sample for that home/room/metric.

* `POST /api/alerts/{id}/acknowledge` accepts `{"acknowledged_by":"Member name"}`.

Invalid input returns a 400 response; missing alerts return 404; attempting to acknowledge an all-clear alert returns 409. The API does not yet verify that the supplied acknowledgement name belongs to the home.

## Database and deployment

Alembic migrations live in `migrations/versions/`; the schema uses SQLAlchemy types and a filtered unique index that is supported by both PostgreSQL and SQLite. Apply changes with `python -m alembic upgrade head`. The deployment command runs migrations before starting the application.

For Render:

1. Create a PostgreSQL database and a web service from this repository's `render.yaml`.
2. Set `DATABASE_URL` to the database's **internal** connection URL.
3. Set `SECRET_KEY` and `AIRSENSE_API_TOKEN` to unique generated secrets in the Render dashboard.
4. The blueprint requires the bearer token for all write requests. Keep household data out of this deployment until account authentication, household authorization, and per-sensor credentials are added.

Render deployment configuration is provided; this repository has not been deployed or verified against a live Render service. 
