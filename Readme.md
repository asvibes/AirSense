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

## Project status

**Overall completion: about 57% of the PRD** (reviewed 28 October 2026).

| Area | Weight | Completion | Contribution |
|---|---|---|---|
| Must-have features F1-F7 | 70% | ~75% | ~52.5% |
| Should-have features F8-F9 | 10% | ~22% | ~2% |
| Could and Stretch features F10-F14 | 10% | 0% | 0% |
| Delivery items (live HTTPS URL, security headers, Power BI report) | 10% | ~25% | ~2.5% |
| **Total** | 100% | | **~57%** |

These percentages are estimates from reading the code and running the test suite (28 tests, all passing).

### Status table

| # | Feature | Priority | Done | Status | What works | What is missing |
|---|---|---|---|---|---|---|
| F1 | Auth and roles | Must | ~85% | Mostly done | Register, login, logout, create home, single-use invite codes, Owner and Member roles, CSRF protection, rate-limited login, access-control tests | Passwords use scrypt, the PRD asks for bcrypt or Argon2id; access tests do not yet cover every route |
| F2 | Sensor provisioning | Must | ~70% | Mostly done | Owner provisions a sensor for a room, one-time device key, only a peppered hash stored, rotate key, revoke sensor | QR pairing, whole-house (unassigned) sensors, moving a sensor between rooms |
| F3 | Ingestion and monitoring | Must | ~75% | Mostly done | Device-key authenticated endpoint, validation, duplicate rejection through a unique constraint, rejections logged, last-seen tracking for freshness | "Reading too old" check, separate rejection counter, test that a forced failure saves nothing |
| F4 | Dashboard | Must | ~60% | Partly done | Room cards with latest values and open alerts, tabs, source labels, pause control, heatmap view, dark theme | Verified 15-30 second polling, trend arrows, freshness on every card, 360 px phone-width check |
| F5 | Status and alerts | Must | ~90% | Nearly done | High, sustained Elevated and Rapid rise alerts, one open alert per room, metric and level, acknowledge with who and when, all-clear after a quiet period, about 18 lifecycle tests | Projected trend on all-clear, wording audit for "safe" and "dangerous", certified-alarm notice on CO and NO2 screens |
| F6 | History | Must | ~70% | Mostly done | Date, room and metric filters, indexed time queries, 90-day coverage heatmap, CSV export | CSV is streamed directly, not saved to private Blob Storage with a signed link |
| F7 | Audit logging | Must | ~75% | Mostly done | Owner-only activity log for logins, invitations, rooms, sensors, thresholds and ingestion; Members get 403 | Database trigger for threshold changes (only in the Azure SQL scripts, not the running app) |
| F8 | Demo panel | Should | ~25% | Started | Simulated-reading endpoint that drives alert scenarios | Simulator scenarios, DALTON replay, demo panel page |
| F9 | Room photos | Should | ~20% | Started | Ventilation sources can be ticked per room | Photo upload |
| F10 | Email alerts | Could | 0% | Not started | | |
| F11 | Critical Alarm Mode | Could | 0% | Not started | | |
| F12 | Safety plan | Could | 0% | Not started | | |
| F13 | Automatic photo suggestions | Could | 0% | Not started | | |
| F14 | Live AirGradient source | Stretch | 0% | Not started | | |

**Must-have summary:** all 7 are started. F5 is nearly done, F1, F2, F3, F6 and F7 are mostly done, and F4 is partly done. A pair needs 5 working end to end; F5, F1, F3, F7 and F2 are the closest.

### Delivery checklist (security check, 3 November)

| Item | Status |
|---|---|
| Repository with CI | Done (unit tests, Alembic migration and route listing) |
| Deployment config | `render.yaml` written; live HTTPS URL not confirmed |
| Security checklist document | Written; needs final review against the deployed app |
| Security headers (CSP, HSTS, X-Frame-Options) | Not done |
| DALTON data import | Not done |
| Power BI analytics report | Not done |
| PWA manifest and service worker | Not done |

## Project Constraints and Limitations

* AirSense is a ventilation-support demo, not a medical or diagnostic system.
* Readings depend on configured sensors or submitted simulator values; the application does not measure air quality independently.
* Threshold defaults are illustrative, not published health or safety guidelines.
* The current dashboard supports CO₂ in ppm. Verify metric units and sensor ranges before any non-demo use.
* The application does not replace a certified carbon monoxide alarm or other safety equipment.
* Thresholds do not currently have stored authoritative citations.
* DALTON replay, email delivery, automatic sensor adapters, and live vendor integrations are not configured.
* The rate limiter is process-local and is not suitable for coordinating multiple workers.

