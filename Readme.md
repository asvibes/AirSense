# AirSense

AirSense is a ventilation-support demo that shows indoor air readings, room trends, and threshold alerts. It consumes readings from external sensors or replay data; it does not measure air quality itself.

## Run locally

Requires Python 3.10 or later.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m alembic upgrade head
python -m flask --app "app.main:create_app()" run
```

Open `http://127.0.0.1:5000/`. The default database is SQLite at `instance\airsense.sqlite3`; set `DATABASE_URL` to use another supported SQLAlchemy database URL. `AUTO_CREATE_SCHEMA` defaults to `true` for local development.

Run the backend and dashboard tests with:

```powershell
python -m unittest discover -s tests -v
```

## Dashboard

The Flask-rendered interface is responsive and served from `/alerts` (the root route redirects there). It polls the dashboard API every 20 seconds and provides:

* Latest reading by room and metric, including source, sample age, and direction of change when a previous sample exists.
* Room status and alert history, with alert acknowledgement.
* CO₂ reading entry for simulated and recorded replay data.
* Per-room CO₂ threshold configuration for High, sustained Elevated, rapid rise, and all-clear behavior.

The dashboard uses HTML, CSS, and vanilla JavaScript served by Flask; no separate frontend build or third-party browser package is required.

## API

* `GET /api/health` checks application/database availability.
* `GET /api/dashboard?home_id=demo-home` returns the latest two readings per room/metric (for trend calculation) and alert history for the selected home ID.
* `GET /api/alerts?home_id=demo-home` returns alert history.
* `POST /api/policies` configures one room/metric policy. Its JSON body includes `room`, `metric`, `unit`, `high_threshold`, `elevated_threshold`, `elevated_duration_seconds`, `rapid_rise_per_minute`, `all_clear_duration_seconds`, and `max_reading_gap_seconds`.
* `POST /api/readings` stores and evaluates a reading. Example:

```json
{
  "home_id": "demo-home",
  "home_name": "Demo Home",
  "room": "Bedroom",
  "metric": "CO2",
  "unit": "ppm",
  "value": 1650,
  "source": "simulated"
}
```

`source` is `dataset`, `simulated`, or `device`. Timestamps are ISO-8601 with a timezone; omitted timestamps use the current time. A sample must be newer than the most recent reading for its home/room/metric.

* `POST /api/alerts/{id}/acknowledge` accepts `{"acknowledged_by":"Member name"}`.

When `REQUIRE_API_TOKEN=true`, API requests require `Authorization: Bearer <AIRSENSE_API_TOKEN>`. The dashboard itself remains available as a shell so a user can enter the deployment token; the browser holds it in tab-scoped session storage. This token is a shared deployment guard, not an account or household permission.

## Subject constraints and implementation status

* **System Design:** One Flask application, REST endpoints, and 20-second polling; no websockets or microservices. Replay and simulated readings use the same alert evaluation path.
* **RDBMS:** Readings and alerts use relational SQLAlchemy models. Duplicate room/metric/timestamp readings are rejected, open-alert uniqueness is enforced in the database, and reading/alert updates are transactional.
* **DP-900:** Readings retain metric, unit, source, and timestamp. The current dashboard supports CO₂/ppm only. The backend does not yet persist citations for the illustrative default thresholds.
* **Cloud Security:** A shared bearer token can guard API routes, but user accounts, home-membership authorization, and per-device keys are not implemented. Do not enter private household data. Use HTTPS before any hosted use.

AirSense makes no medical or diagnostic claims and does not replace a certified carbon monoxide alarm. CO and NO₂ are advisory metrics; their entry screens are not enabled in this demo.

## Current scope and limitations

This checkout implements the alert lifecycle and its connected demo dashboard. Registration, household membership and role checks, sensor provisioning, per-sensor freshness intervals, CO/NO₂ screens, DALTON upload/replay tools, history charts and CSV export, audit logging, private blob storage, Power BI integration, and live sensor ingestion are not implemented. The dashboard does not label a sensor stale because no expected reporting interval is stored. Do not use this demo with personal household data.

Alert thresholds shown by default are illustrative configuration values, not published health or safety guidelines. Record a guideline source for each threshold and verify the metric units and sensor range before any non-demo use.
