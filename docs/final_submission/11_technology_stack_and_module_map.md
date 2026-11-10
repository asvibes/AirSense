# Technology stack and module documentation

## Verified technology stack

| Layer | Technology found in the repository | Use and qualification |
|---|---|---|
| Language/runtime | Python; README says Python 3.10+ and Render configuration specifies Python 3.12.8 | The full test result in document 10 is from the local Python environment; no supported-version matrix was run. |
| Web application | Flask 3.x dependency range | App factory in `app/main.py`; blueprints register application routes. |
| Data access | SQLAlchemy 2.x dependency range | ORM models and sessions are under `app/models/` and `app/db.py`. |
| Schema evolution | Alembic 1.x dependency range | Active application migrations are under `migrations/versions/`. |
| Default database | SQLite | Local default is configured in `app/config.py`; application connections enable SQLite foreign keys. |
| Additional database driver | `psycopg[binary]` 3.x is declared; PostgreSQL URLs are normalized | PostgreSQL migration and test CI jobs passed on commit `0fe75da`; Azure SQL connectivity remains unverified. |
| Browser UI | HTML templates, CSS, vanilla JavaScript | No separate frontend framework or package build is declared in the inspected requirements. |
| Web server | Gunicorn 22.x dependency range | `render.yaml` uses Gunicorn; a live deployment is not verified. |
| Testing | pytest 8.x development dependency | `tests/` contains Python tests; JavaScript test execution and line coverage were not measured. |
| Environment configuration | `python-dotenv` 1.x | `app/config.py` loads a local `.env` file when present. `.env.example` is a template, not a credential store. |
| Email | Python standard-library HTTP client calling Brevo's API | Delivery requires configured credentials/sender; provider operation was not verified. |
| Forecasting | Python standard-library arithmetic/time/JSON plus application code | Custom linear time-trend fit and evaluation; NumPy/scikit-learn are not application dependencies. This is a statistical feature, not evidence of a validated ML product. |
| CSV/PDF handling | Python CSV parsing and application report code; repository dependencies define active runtime packages | CSV replay/export and PDF generation routes/services exist; their output was not visually audited in a browser during this task. |

Dependency ranges are read from `requirements.txt` and `requirements-dev.txt`; they are not exact lock-file versions. This repository does not include a frontend dependency manifest or a Python lock file in the inspected root.

## Backend module map

### Application entry and configuration

| Path | Responsibility |
|---|---|
| `app/main.py` | Flask app factory, error handlers, proxy/security headers, blueprint registration, health and landing routes |
| `app/config.py` | Environment configuration and database URL normalization |
| `app/db.py` | SQLAlchemy engine/session lifecycle, SQLite foreign-key pragma, optional test schema creation |
| `app/error_handlers.py`, `app/json_request.py` | HTTP/API error handling and JSON body helpers |
| `app/parameters.py`, `app/timestamps.py`, `app/csv_safety.py` | Metric/unit registry and conversions, UTC helpers, safe CSV cell output |

### Routers

`app/routers/` separates request handling by domain:

- `auth.py`: registration, login/logout, OTP verification and password reset
- `homes.py`, `rooms.py`: home/membership/invitation and room operations
- `sensors.py`, `sensor_readings.py`: sensor provisioning/key lifecycle and device ingestion
- `thresholds.py`, `alerts.py`, `dashboard.py`, `audit.py`: policies, alerts, dashboard data, activity
- `demo.py`: simulator submission and dataset replay
- `history.py`: history, analytics/predictions, CSV and PDF routes
- `uploads.py`: authorized room photo upload/retrieval/deletion

### Domain services, repositories and security

- `app/services/ingestion/`: reading validation, ingestion orchestration, and rejection auditing
- `app/repositories/alerts.py`: reading persistence, threshold evaluation integration, alert lifecycle and replay scope helpers
- `app/services/alerts/`: alert rule evaluation/wording and all-clear transitions
- Other services provide audit, invitations, provisioning, email, freshness, local private-file storage (`blob_storage.py`), and PDF reports.
- `app/security/`: session/CSRF/membership guards, password hashing, device-key hashing, database-backed rate limits, and shared dependencies.
- `app/schemas/`: typed validation helpers for auth, readings, alerts, and sensors.

`app/services/blob_storage.py` is a local private-file implementation; despite its module name, it is not evidence of an Azure Blob Storage integration.

### Models and database

The active ORM defines 13 application tables: `homes`, `users`, `home_memberships`, `home_invitations`, `email_challenges`, `rate_limit_buckets`, `rooms`, `sensors`, `metrics`, `threshold_policies`, `air_readings`, `air_alerts`, and `audit_logs`. The detailed field/key design is in [document 4](04_er_diagram_and_database_design.md).

### Sources and analytics

- `app/sources/simulator.py`: simulated readings and scenarios
- `app/sources/airgradient.py`: AirGradient-style `rco2` payload normalization
- `app/sources/dalton_replay.py`: timestamped environmental CSV parsing and unit/schema handling
- `app/ml/forecasting.py`: data filtering, linear model, holdout metrics, and horizon predictions
- `app/ml/train.py`: offline series grouping/model evaluation and model JSON persistence

### Frontend, tests and tooling

- `app/templates/` contains landing, auth, dashboard, history, and predictions views.
- `app/static/` contains shared styles, dashboard/history/prediction JavaScript, service-worker and manifest assets. Presence of PWA-related files is not proof of offline support being complete.
- `tests/` contains Python tests plus several `.test.js` files. Document 10 records the Python run; no JavaScript runner result or line-coverage percentage is claimed.
- `tools/seed_demo_home.py` creates an idempotent demo home for an existing account; it does not create credentials.

## Architecture and implementation references

See [document 3](03_architecture_and_data_flow.md) and its rendered architecture diagram. Runtime/API behavior is documented in [document 6](06_api_reference.md); setup is in [document 7](07_setup_and_user_guide.md).
