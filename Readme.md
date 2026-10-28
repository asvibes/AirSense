# AirSense

AirSense is a ventilation-support application for reviewing indoor air readings, room trends, and advisory threshold alerts. It consumes readings from configured sensors or manually submitted simulator values; it does not measure air quality itself.

## Run locally

Requires Python 3.10 or later.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m alembic upgrade head
python -m flask --app "app.main:create_app()" run
```

Open `http://127.0.0.1:5000/register` to create the first account and home. `/` redirects to the dashboard, which requires sign-in. The default database is SQLite at `instance\airsense.sqlite3`; set `DATABASE_URL` to use another supported SQLAlchemy database URL. `AUTO_CREATE_SCHEMA` defaults to `true` for local development; production deployments should apply Alembic migrations.

Set `SECRET_KEY` and `AIRSENSE_DEVICE_KEY_PEPPER` to strong, private values before production use. Production mode refuses to start without them. Sessions use HttpOnly, SameSite cookies and mutation requests require a CSRF token. The included rate limiter is process-local; use a shared limiter before running multiple workers.

Run the integration tests, migration, and route-list checks with:

```powershell
python -m unittest discover -s tests -v
python -m alembic upgrade head
python -m flask --app "app.main:create_app()" routes
```

## Dashboard

The responsive frontend is served from `/alerts` after sign-in. Its rooms, readings, alerts, sensor status, thresholds, household members, and activity are loaded from the authenticated backend APIs. User mutations include CSRF protection. The interface includes:

* Overview cards and a latest-reading bar chart for metrics recorded in the selected home.
* Room management with persisted multiple ventilation sources per room.
* Owner-managed sensor provisioning, key rotation, and revocation. A provisioned key is shown once; only its hash is stored.
* Device reading ingestion using per-sensor keys and the same alert evaluation path as simulator readings.
* Alert history and authenticated acknowledgement.
* Persisted per-room CO₂ threshold settings, history charts, a 90-day coverage heatmap, and CSV export.
* Owner-only invitations and activity history; invite links are single-use, expire after seven days, and must be shared manually because email delivery is not configured.
* A simulator that submits readings to the server-side alert pipeline, plus a persisted light/dark theme preference.

The browser uses plain HTML, CSS, and vanilla JavaScript; no separate frontend build or third-party browser package is required. DALTON files are not included or replayed. Do not treat demo values or illustrative default thresholds as health or safety guidance.

## API overview

All account/home API routes use the signed-in session. Authenticated `POST`, `PUT`, `PATCH`, and `DELETE` requests require the `X-CSRF-Token` header. The dashboard obtains the token from the server-rendered page. Device ingestion instead authenticates with `X-Device-Key`.

* `GET /api/health` checks application/database availability.
* `GET /api/me` returns the signed-in account and its homes.
* `POST /api/auth/register`, `POST /api/auth/login`, and `POST /api/auth/logout` manage account sessions.
* `GET/POST /api/homes` lists or creates homes; `POST /api/active-home` selects one.
* `GET/POST /api/homes/{home_id}/rooms` lists or creates rooms.
* `GET/POST /api/homes/{home_id}/sensors` lists or provisions sensors. Provisioning returns a one-time device key.
* `POST /api/homes/{home_id}/sensors/{sensor_id}/rotate-key` rotates a device key; `/revoke` disables the sensor.
* `POST /api/sensors/{sensor_id}/readings` accepts validated readings with `X-Device-Key`.
* `POST /api/homes/{home_id}/demo/readings` submits a simulated reading through the normal server-side alert pipeline.
* `GET /api/homes/{home_id}/dashboard`, `/rooms`, `/sensors`, and `/thresholds` return home-bound data.
* `PUT /api/homes/{home_id}/thresholds` saves the room threshold settings as one validated batch. Owners can edit settings; members can view them.
* `GET /api/homes/{home_id}/history` returns stored readings. Add `room_id`, `metric`, `from`, `to`, and `limit` query parameters to filter. `GET /api/homes/{home_id}/history.csv` exports the same data.
* `POST /api/alerts/{alert_id}/acknowledge` records the signed-in user's display name and timestamp.
* `GET /api/homes/{home_id}/members` lists household members. Owners create invitations at `/invitations`; the invited account accepts the single-use token at `POST /api/invitations/accept`.
* `GET /api/homes/{home_id}/activity` returns audit history to home owners.

The legacy `POST /api/readings` and `POST /api/policies` endpoints remain available for authenticated browser/API compatibility. Optional `REQUIRE_API_TOKEN` adds a bearer-token gate to legacy alert routes; it does not replace account authentication or household authorization.

## Security and product limits


* `POST /api/alerts/{id}/acknowledge` accepts `{"acknowledged_by":"Member name"}`.

When `REQUIRE_API_TOKEN=true`, API requests require `Authorization: Bearer <AIRSENSE_API_TOKEN>`. The dashboard itself remains available as a shell so a user can enter the deployment token; the browser holds it in tab-scoped session storage. This token is a shared deployment guard, not an account or household permission.

## Subject constraints and implementation status

* **System Design:** One Flask application, REST endpoints, and 20-second polling; no websockets or microservices. Replay and simulated readings use the same alert evaluation path.
* **RDBMS:** Readings and alerts use relational SQLAlchemy models. Duplicate room/metric/timestamp readings are rejected, open-alert uniqueness is enforced in the database, and reading/alert updates are transactional.
* **DP-900:** Readings retain metric, unit, source, and timestamp. The current dashboard supports CO₂/ppm only. The backend does not yet persist citations for the illustrative default thresholds.
* **Cloud Security:** A shared bearer token can guard API routes, but user accounts, home-membership authorization, and per-device keys are not implemented. Do not enter private household data. Use HTTPS before any hosted use.

AirSense makes no medical or diagnostic claims and does not replace a certified carbon monoxide alarm. CO and NO₂ are advisory metrics; their entry screens are not enabled in this demo.

The separate Azure SQL target-schema scripts and their apply order are documented in [database/README.md](./database/README.md). They are not wired into the current Flask app's Alembic migrations.

## Current scope and limitations

The current frontend is a standalone prototype and is not connected to the backend. Its sample interactions are not persisted. DALTON data import/replay, account and household authorization, real sensor provisioning/ingestion, authoritative threshold references, and persisted audit history remain future work. The backend alert API remains available but is not consumed by this frontend. Do not use this preview with personal household data.

Alert thresholds shown by default are illustrative configuration values, not published health or safety guidelines. Record a guideline source for each threshold and verify the metric units and sensor range before any non-demo use.
=======
* Passwords are validated and hashed with scrypt. Invitations are stored by token hash and limited to the invited email.
* Household membership is checked on every home-scoped request. Owners manage rooms, sensors, thresholds, and invitations; members can view home data and submit simulator readings.
* Device keys are randomly generated, peppered, and stored only as hashes. Treat the one-time provisioning/rotation response as a secret.
* Invite delivery is manual. The token must be shared securely with the account using the invited email address.
* The rate limiter is in-memory and does not coordinate across workers.
* Threshold defaults are illustrative and have no stored authoritative citations. CO/NO₂ advisory displays do not replace certified carbon-monoxide alarms or other safety equipment.
* DALTON replay, email delivery, automatic sensor adapters, and live vendor integrations are not configured.

