## Project Overview

AirSense is an indoor air-quality monitoring platform that makes room-level CO₂ readings and ventilation-support alerts easier to understand.

## Technology Stack

* Backend and web UI: Python, Flask, Jinja templates
* Local development database: SQLite
* Production database target: Azure SQL Database

## Alert acknowledgement and all-clear

The runnable alert slice records a CO₂ reading with its threshold. A reading above the threshold opens one alert per room. A household member can acknowledge an active alert; later high readings update the same alert without losing its acknowledgement. A reading at or below the incident's captured threshold automatically marks the alert all clear. A later breach opens a new alert.

Acknowledgement names are display labels in this local prototype, not authenticated identities. Alert transitions are isolated from the SQLite repository so the persistence adapter can be replaced when Azure SQL and application authentication are configured.

### Run locally

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
flask --app "app.main:create_app()" run
```

Open `http://127.0.0.1:5000/alerts`. The local database is created at `instance\airsense.sqlite3`; set `AIRSENSE_DATABASE` to override its location.

### API

* `GET /api/alerts` returns alert history.
* `POST /api/readings` accepts JSON with `room`, `co2_ppm`, and `threshold_ppm`.
* `POST /api/alerts/{id}/acknowledge` accepts JSON with `acknowledged_by`.

The reading endpoint returns an `action` of `open`, `update`, `clear`, or `none` and the affected alert, if any.

### Tests

```powershell
python -m unittest discover -s tests
```

AirSense is a ventilation-support tool, not a medical or safety device. It does not replace a certified carbon monoxide alarm.
