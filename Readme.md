# AirSense

AirSense is a ventilation-support application for reviewing indoor air readings, room trends, and advisory threshold alerts. It consumes readings from configured sensors or manually submitted simulator values; it does not measure air quality itself.

## Run Locally

**Requirements:** Python 3.10 or later.

### 1. Create and activate a virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 2. Install dependencies

```powershell
pip install -r requirements.txt
```

### 3. Apply database migrations

```powershell
python -m alembic upgrade head
```

### 4. Start the application

```powershell
python -m flask --app "app.main:create_app()" run
```

Open `http://127.0.0.1:5000/` for the landing page, then use Sign in or Register to access the dashboard.

The default database is SQLite at `instance\airsense.sqlite3`. Set `DATABASE_URL` to use another supported SQLAlchemy database URL.

`AUTO_CREATE_SCHEMA` defaults to `false`; apply Alembic migrations before starting the application. SQLAlchemy's `create_all()` can create missing tables, but it does not migrate existing tables. Set `AUTO_CREATE_SCHEMA=true` only for disposable databases such as isolated tests.

The application does not automatically load `.env.example`. In PowerShell, set required environment variables in the current shell before starting Flask, or configure them in your development environment:

```powershell
$env:DATABASE_URL = "sqlite:///instance/airsense.sqlite3"
$env:SECRET_KEY = "<private random value>"
$env:AIRSENSE_DEVICE_KEY_PEPPER = "<private random value>"
```

Keep real values in an ignored local `.env` or protected environment settings, never in source control. Before running migrations against a database that contains data, stop the application and make a separate verified backup of the database file. Do not use `AUTO_CREATE_SCHEMA` to update an existing schema.

### Production configuration

Set `SECRET_KEY` and `AIRSENSE_DEVICE_KEY_PEPPER` to strong, private values before production use. Production mode refuses to start without them.

Sessions use HttpOnly, SameSite cookies, and mutation requests require a CSRF token. Home-scoped routes enforce owner/member membership. Device ingestion uses per-sensor keys whose peppered hashes are stored in the database.
Authentication and abuse-sensitive routes use database-backed rate-limit buckets shared across workers. Set `TRUSTED_PROXY_HOPS` only when the deployment has a known proxy chain; leave it at `0` to ignore forwarded client headers.

The application emits content-type, clickjacking, referrer, permissions, and CSP headers. HSTS is emitted only for secure production requests. HTTPS, production database network restrictions, and cloud secret configuration must still be configured and verified before public deployment.

## Dashboard

The responsive frontend is served from `/alerts` after sign-in. It loads rooms, readings, alerts, sensor status, thresholds, household members, and activity from the authenticated backend APIs.

Features include:

* **Overview:** Summary cards and a latest-reading bar chart for metrics recorded in the selected home.
* **Room management:** Owners can create rooms and edit room names and multiple ventilation sources per room. Room deletion is not implemented.
* **Sensor management:** Owner-managed sensor provisioning, key rotation, and revocation. A provisioned key is shown once; only its hash is stored.
* **Sensor ingestion:** Submit device readings using per-sensor keys through the same alert evaluation path used by simulator readings.
* **Alert management:** View alert history and acknowledge alerts while authenticated.
* **Threshold configuration:** Persist per-room, per-metric advisory thresholds. CO₂ receives the configured defaults; other parameters have alerts disabled until a threshold is explicitly set.
* **History and export:** Filter stored readings by household, room, sensor, metric, and date range; inspect timestamped samples and gaps; export CSV or a multi-page PDF report.
* **Analytics:** Review observed minimum, average, maximum, and change summaries; compare series by room/sensor; view actual samples or daily, weekly, and monthly averages. Empty periods are not synthesized.
* **Predictions:** A dedicated page reports forecasts only when a per-series linear trend beats a persistence baseline by at least 5% on a later chronological holdout. Unsupported series and horizons remain unavailable; simulated readings are excluded from training.
* **Household management:** Owners can invite members and review activity history.
* **Simulation:** Submit simulated readings to the server-side alert pipeline.
* **Environmental dataset replay:** Import supported timestamped measurements from a CSV, including CO₂, particulate matter, temperature, humidity, CO, NO₂, VOC, and compatible custom measurements with explicit units. Historical dataset readings retain their timestamps and do not create live alerts.
* **Appearance:** Persist the light/dark theme preference.

The browser interface uses plain HTML, CSS, and vanilla JavaScript. No separate frontend build or third-party browser package is required.

Invitation links are single-use and expire after 24 hours. Email delivery is configured through the Brevo adapter when deployment credentials and a verified sender are supplied.

DALTON source data is not bundled. In the Demo Lab, upload a CSV (up to 16 MB) with one timestamp column (`ts`, `timestamp`, `datetime`, or similar) and any supported measurement columns; CO₂ is optional. Common aliases and explicit units are recognized and converted only when the conversion is defined. The documented DALTON headers and units are applied only to files matching the DALTON schema; other unitless or ambiguous columns are reported for review and not imported. The app imports up to 1,000 rows per replay, skips duplicate metric/timestamp pairs, and reports skipped duplicates. Original timestamps are kept by default; optional shifting moves the newest sample to the present while retaining sample spacing. Historical dataset readings are stored for dashboard, History, Analytics, and Predictions, but do not produce active alerts. See [DALTON replay notes](docs/dalton-notes.md).

## API Overview

Account and home API routes use the signed-in session. Authenticated `POST`, `PUT`, `PATCH`, and `DELETE` requests require the `X-CSRF-Token` header. The dashboard obtains the token from the server-rendered page.

Device ingestion uses the `X-Device-Key` header for sensor authentication.

| Endpoint | Purpose |
|---|---|
| `GET /api/health` | Check application/database availability; no account session required. |
| `GET /api/me` | Return the signed-in account, CSRF token, and homes. |
| `POST /api/auth/register`, `POST /api/auth/login`, `POST /api/auth/logout` | Register, sign in, and sign out. |
| `GET /api/homes`, `POST /api/homes` | List or create homes for the signed-in user. |
| `POST /api/active-home` | Select a home in the session. |
| `GET /api/homes/{home_id}/dashboard` | Get current dashboard readings and alerts. |
| `GET /api/homes/{home_id}/rooms`, `POST /api/homes/{home_id}/rooms` | List or create rooms. |
| `PATCH /api/homes/{home_id}/rooms/{room_id}` | Update a room name and/or ventilation sources; owner only. Room deletion is not implemented. |
| `GET /api/homes/{home_id}/sensors`, `POST /api/homes/{home_id}/sensors` | List or provision sensors; provisioning returns a one-time device key. |
| `POST /api/homes/{home_id}/sensors/{sensor_id}/rotate-key`, `POST /api/homes/{home_id}/sensors/{sensor_id}/revoke` | Rotate a sensor key or revoke the sensor. |
| `POST /api/sensors/{sensor_id}/readings` | Submit a validated reading using `X-Device-Key`. |
| `POST /api/homes/{home_id}/demo/readings`, `POST /api/homes/{home_id}/demo/replay` | Submit simulator readings or replay a timestamped environmental CSV. |
| `GET /api/homes/{home_id}/thresholds`, `PUT /api/homes/{home_id}/thresholds` | Read or batch-update per-room, per-metric thresholds. |
| `PUT /api/homes/{home_id}/thresholds/{room_id}/{metric_code}` | Update one room/metric threshold. |
| `GET /api/homes/{home_id}/history`, `GET /api/homes/{home_id}/history.csv` | Get filtered history or export it as CSV. |
| `GET /api/homes/{home_id}/history/options` | List stored metrics for the selected room and sensor filters. |
| `GET /api/homes/{home_id}/history.pdf` | Export a PDF report for the selected history filters. |
| `GET /api/homes/{home_id}/predictions` | List saved model evaluations or request a validated forecast for a stored series. |
| `GET /api/homes/{home_id}/members`, `POST /api/homes/{home_id}/invitations` | List members or create a single-use invitation. |
| `POST /api/invitations/accept`, `DELETE /api/homes/{home_id}/members/{user_id}` | Accept an invitation or remove a non-owner member. |
| `GET /api/homes/{home_id}/activity` | Read the home activity log (owner only). |
| `GET /api/dashboard?home_id=...`, `GET /api/alerts?home_id=...`, `POST /api/policies`, `POST /api/readings`, `POST /api/alerts/{alert_id}/acknowledge` | Legacy authenticated dashboard/alert routes retained for compatibility. |

Authenticated mutating routes use session authentication and CSRF protection. Device ingestion is authenticated separately with the sensor key. `REQUIRE_API_TOKEN` is an optional additional gate in the legacy alerts blueprint; it does not replace session, membership, or device authentication and is not a global API gate.

Forecast training is a separate offline task and is never run during page or API loading. Run `python -m app.ml.train` after adding real device or dataset readings. It evaluates each home/room/sensor/metric series with an 80/20 chronological split, compares the linear time trend with a persistence baseline, and writes model/evaluation results to `instance/forecast_models.json`. Series with fewer than 30 distinct timestamps or without the required holdout improvement are saved as unavailable, not forecast.

## Security

* **Password storage:** Passwords are validated and hashed using scrypt.
* **Session protection:** Sessions use HttpOnly, SameSite cookies, and mutation requests require CSRF protection.
* **Household authorization:** Home-scoped requests check household membership. Owners manage rooms, sensors, thresholds, and invitations; members can view home data and submit simulator readings.
* **Device credentials:** Device keys are randomly generated, peppered, and stored only as hashes. The one-time provisioning or rotation response must be treated as a secret.
* **Invitations:** Invitation tokens are stored by token hash and restricted to the invited email address. Invite delivery is manual, and tokens must be shared securely.
* **Rate limiting:** The current rate limiter is in-memory and does not coordinate across workers.
* **Deployment:** Configure strong secrets and use HTTPS before public deployment.

## Database

The application uses SQLAlchemy models and Alembic migrations. The current local SQLite database is at revision `20261105_0004`, which adds nullable `air_readings.received_at`. The active schema contains 11 application tables plus Alembic's version table. Fresh migration-to-head and ORM metadata comparison, upgrade from the prior revision, and downgrade/re-upgrade are tested with temporary databases; no production database is used for these tests.

Readings and alerts use relational models. Duplicate home/room/metric/timestamp readings are rejected, open-alert uniqueness is enforced in the database, and reading/alert updates are transactional. Foreign keys ensure individual referenced records exist, but the active schema does not enforce same-home consistency between a row's `home_id`, `room_id`, and optional sensor through composite constraints. Current local records passed integrity and foreign-key checks, and read-only same-home relationship checks found no mismatches.

Separate, one-time Azure SQL target-schema scripts and their application order are documented in [`database/README.md`](./database/README.md). They define a different schema—including global roles, composite same-home relationships, temporal threshold provenance, additional reading/alert constraints, activity logs, views, and triggers—and are not wired into the Flask application's Alembic migrations. Do not execute them against the local SQLite database.

## Testing and Verification

Run the integration tests:

```powershell
python -m unittest discover -s tests -v
```

Apply migrations:

```powershell
python -m alembic upgrade head
```

Back up any populated database before applying migrations. The migration command targets the `DATABASE_URL` environment variable when set, otherwise the URL in `alembic.ini`; verify the target first. The latest full local test run passed **77 tests and 64 subtests**. That is backend/unit/API/database test evidence, not browser E2E, PostgreSQL, or cloud deployment evidence.

List registered Flask routes:

```powershell
python -m flask --app "app.main:create_app()" routes
```

## Project status and known gaps

The latest known backend test baseline is **77 tests and 64 subtests passed**. No percentage-complete score is reported because PRD scope and delivery criteria have not been independently weighted or fully verified.

| Area | Local implementation status | Remaining or unverified |
|---|---|---|
| Authentication and authorization | Session auth, scrypt password hashes, CSRF, per-home owner/member checks; selected access-control tests. | PRD facility-manager/admin roles and role-change flow are absent; browser E2E not verified. |
| Rooms and sensors | Room creation/listing/editing; sensor provision/rotate/revoke; freshness and device-key ingestion. | Room deletion and sensor move/edit are absent. |
| Readings, thresholds, alerts | Validated simulator/device/DALTON flows, server-generated UTC `received_at`, threshold evaluation, duplicate suppression, acknowledgement/all-clear, and selected audit events. | Threshold source citations are not stored. Existing readings retain `received_at = NULL` because historical receipt times are unknown. |
| History and dashboard | Same-origin UI API calls, polling, history filters, charts, heatmap, CSV. | UI behavior has no automated browser E2E evidence. |
| Audit/security | Login/logout (known account), threshold, sensor, membership, reading, and alert events; credentials are not intentionally included. | No role changes; unknown-account failed logins have no home-scoped audit record. Full threat-model/security evidence remains incomplete. |
| Analytics and files | Local dashboard reporting and CSV streaming. | Power BI report is a zero-byte placeholder; Blob Storage is not integrated. |
| Cloud/deployment | Render configuration exists as a deployment template. | No verified live deployment, HTTPS/security headers, Azure SQL/Blob configuration, firewall evidence, or cloud test result is claimed. |

The application currently implements home-scoped `owner` and `member` roles—not the full proposed standard-user/facility-manager/administrator model. See [docs/PRD.md](docs/PRD.md) for the local implementation summary and [docs/product-requirements.md](docs/product-requirements.md) for target requirements.

## Project Constraints and Limitations

* AirSense is a ventilation-support demo, not a medical or diagnostic system.
* Readings depend on configured sensors or submitted simulator values; the application does not measure air quality independently.
* Threshold defaults are illustrative, not published health or safety guidelines.
* The dashboard displays only measurements present in stored readings. Verify metric units and sensor ranges before any non-demo use.
* The application does not replace a certified carbon monoxide alarm or other safety equipment.
* Thresholds do not currently have stored authoritative citations.
* Dataset replay requires the user to provide a CSV; imported historical rows do not create live alerts. Email delivery, automatic sensor adapters, and live vendor integrations are not configured.
* Authentication and ingestion abuse limits use persistent database-backed buckets; verify database locking and cleanup behavior on the deployment database.
