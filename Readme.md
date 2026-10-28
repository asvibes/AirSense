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

Open `http://127.0.0.1:5000/register` to create the first account and home. The root route (`/`) redirects to the dashboard, which requires sign-in.

The default database is SQLite at `instance\airsense.sqlite3`. Set `DATABASE_URL` to use another supported SQLAlchemy database URL.

`AUTO_CREATE_SCHEMA` defaults to `true` for local development. Production deployments should apply Alembic migrations.

### Production configuration

Set `SECRET_KEY` and `AIRSENSE_DEVICE_KEY_PEPPER` to strong, private values before production use. Production mode refuses to start without them.

Sessions use HttpOnly, SameSite cookies, and mutation requests require a CSRF token. The included rate limiter is process-local; use a shared limiter before running multiple workers.

Use HTTPS before deploying the application publicly.

## Dashboard

The responsive frontend is served from `/alerts` after sign-in. It loads rooms, readings, alerts, sensor status, thresholds, household members, and activity from the authenticated backend APIs.

Features include:

* **Overview:** Summary cards and a latest-reading bar chart for metrics recorded in the selected home.
* **Room management:** Manage rooms and multiple ventilation sources per room.
* **Sensor management:** Owner-managed sensor provisioning, key rotation, and revocation. A provisioned key is shown once; only its hash is stored.
* **Sensor ingestion:** Submit device readings using per-sensor keys through the same alert evaluation path used by simulator readings.
* **Alert management:** View alert history and acknowledge alerts while authenticated.
* **Threshold configuration:** Persist per-room CO₂ threshold settings.
* **History and export:** View history charts, a 90-day coverage heatmap, and export readings as CSV.
* **Household management:** Owners can invite members and review activity history.
* **Simulation:** Submit simulated readings to the server-side alert pipeline.
* **Appearance:** Persist the light/dark theme preference.

The browser interface uses plain HTML, CSS, and vanilla JavaScript. No separate frontend build or third-party browser package is required.

Invitation links are single-use and expire after seven days. Email delivery is not configured, so invitation links must be shared manually.

DALTON files are not included or replayed.

## API Overview

Account and home API routes use the signed-in session. Authenticated `POST`, `PUT`, `PATCH`, and `DELETE` requests require the `X-CSRF-Token` header. The dashboard obtains the token from the server-rendered page.

Device ingestion uses the `X-Device-Key` header for sensor authentication.

| Endpoint                                                   | Purpose                                                           |
| ---------------------------------------------------------- | ----------------------------------------------------------------- |
| `GET /api/health`                                          | Check application and database availability.                      |
| `GET /api/me`                                              | Return the signed-in account and its homes.                       |
| `POST /api/auth/register`                                  | Register an account.                                              |
| `POST /api/auth/login`                                     | Sign in.                                                          |
| `POST /api/auth/logout`                                    | Sign out.                                                         |
| `GET /api/homes`                                           | List homes available to the signed-in account.                    |
| `POST /api/homes`                                          | Create a home.                                                    |
| `POST /api/active-home`                                    | Select the active home.                                           |
| `GET /api/homes/{home_id}/rooms`                           | List rooms in a home.                                             |
| `POST /api/homes/{home_id}/rooms`                          | Create a room.                                                    |
| `GET /api/homes/{home_id}/sensors`                         | List sensors in a home.                                           |
| `POST /api/homes/{home_id}/sensors`                        | Provision a sensor and return its one-time device key.            |
| `POST /api/homes/{home_id}/sensors/{sensor_id}/rotate-key` | Rotate a sensor's device key.                                     |
| `POST /api/homes/{home_id}/sensors/{sensor_id}/revoke`     | Revoke a sensor.                                                  |
| `POST /api/sensors/{sensor_id}/readings`                   | Submit validated sensor readings using `X-Device-Key`.            |
| `POST /api/homes/{home_id}/demo/readings`                  | Submit simulated readings through the server-side alert pipeline. |
| `GET /api/homes/{home_id}/dashboard`                       | Retrieve dashboard data for a home.                               |
| `GET /api/homes/{home_id}/rooms`                           | Retrieve room data.                                               |
| `GET /api/homes/{home_id}/sensors`                         | Retrieve sensor data.                                             |
| `GET /api/homes/{home_id}/thresholds`                      | Retrieve threshold settings.                                      |
| `PUT /api/homes/{home_id}/thresholds`                      | Save validated room threshold settings as a batch.                |
| `GET /api/homes/{home_id}/history`                         | Retrieve stored readings, with optional filters.                  |
| `GET /api/homes/{home_id}/history.csv`                     | Export reading history as CSV.                                    |
| `POST /api/alerts/{alert_id}/acknowledge`                  | Acknowledge an alert as the signed-in user.                       |
| `GET /api/homes/{home_id}/members`                         | List household members.                                           |
| `POST /api/invitations/accept`                             | Accept an invitation using its single-use token.                  |
| `GET /api/homes/{home_id}/activity`                        | Retrieve activity history for home owners.                        |

Owners create invitations through `/invitations`. The invited account accepts the invitation using `POST /api/invitations/accept`.

The legacy `POST /api/readings` and `POST /api/policies` endpoints remain available for authenticated browser/API compatibility. The optional `REQUIRE_API_TOKEN` setting adds a bearer-token gate to legacy alert routes; it does not replace account authentication or household authorization.

## Security

* **Password storage:** Passwords are validated and hashed using scrypt.
* **Session protection:** Sessions use HttpOnly, SameSite cookies, and mutation requests require CSRF protection.
* **Household authorization:** Home-scoped requests check household membership. Owners manage rooms, sensors, thresholds, and invitations; members can view home data and submit simulator readings.
* **Device credentials:** Device keys are randomly generated, peppered, and stored only as hashes. The one-time provisioning or rotation response must be treated as a secret.
* **Invitations:** Invitation tokens are stored by token hash and restricted to the invited email address. Invite delivery is manual, and tokens must be shared securely.
* **Rate limiting:** The current rate limiter is in-memory and does not coordinate across workers.
* **Deployment:** Configure strong secrets and use HTTPS before public deployment.

## Database

The application uses SQLAlchemy models and Alembic migrations.

Readings and alerts use relational models. Duplicate room/metric/timestamp readings are rejected, open-alert uniqueness is enforced in the database, and reading/alert updates are transactional.

Separate Azure SQL target-schema scripts and their application order are documented in [`database/README.md`](./database/README.md). These scripts are not currently wired into the Flask application's Alembic migrations.

## Testing and Verification

Run the integration tests:

```powershell
python -m unittest discover -s tests -v
```

Apply migrations:

```powershell
python -m alembic upgrade head
```

List registered Flask routes:

```powershell
python -m flask --app "app.main:create_app()" routes
```

## Project Constraints and Limitations

* AirSense is a ventilation-support demo, not a medical or diagnostic system.
* Readings depend on configured sensors or submitted simulator values; the application does not measure air quality independently.
* Threshold defaults are illustrative, not published health or safety guidelines.
* The current dashboard supports CO₂ in ppm. Verify metric units and sensor ranges before any non-demo use.
* The application does not replace a certified carbon monoxide alarm or other safety equipment.
* Thresholds do not currently have stored authoritative citations.
* DALTON replay, email delivery, automatic sensor adapters, and live vendor integrations are not configured.
* The rate limiter is process-local and is not suitable for coordinating multiple workers.

