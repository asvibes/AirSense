# Local setup and user guide

## Requirements

The repository README specifies Python 3.10 or later. Dependencies are declared in `requirements.txt`; test dependencies are in `requirements-dev.txt`.

## Windows PowerShell setup

Run commands from the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python -m alembic upgrade head
python -m flask --app "app.main:create_app()" run
```

Open `http://127.0.0.1:5000/`. Register or sign in, then use the authenticated dashboard. To run the tests:

```powershell
python -m pytest -q
```

The default database URL points to a local SQLite file under `instance`. Set `DATABASE_URL` before running the migration command if using another database. PostgreSQL URL handling exists, but integration compatibility is not verified by this submission.

## Configuration and secrets

The application loads a local `.env` file when present; `.env.example` is a template and is not itself a source of production credentials. At minimum, configure a private `SECRET_KEY` and `AIRSENSE_DEVICE_KEY_PEPPER` for production use. Production startup rejects missing or default security values. Keep all actual credentials out of Git and do not paste them into reports or screenshots.

Other environment settings include:

- `DATABASE_URL`, `APP_ENV`, and `AUTO_CREATE_SCHEMA`
- `AIRSENSE_HIGH_THRESHOLD`, `AIRSENSE_ELEVATED_THRESHOLD`, `AIRSENSE_ELEVATED_DURATION_SECONDS`, `AIRSENSE_RAPID_RISE_PER_MINUTE`, `AIRSENSE_ALL_CLEAR_DURATION_SECONDS`, and `AIRSENSE_MAX_READING_GAP_SECONDS`
- `AIRSENSE_MAX_FUTURE_SECONDS`, `AIRSENSE_MAX_LIVE_READING_AGE_SECONDS`, and `TRUSTED_PROXY_HOPS`
- `PRIVATE_UPLOAD_FOLDER` (with `AIRSENSE_PRIVATE_UPLOAD_FOLDER` as a fallback)
- `BREVO_API_KEY`, `MAIL_DEFAULT_SENDER`, `MAIL_DEFAULT_SENDER_NAME`, `PUBLIC_BASE_URL`, and `EMAIL_VERIFICATION_REQUIRED`

Threshold defaults are illustrative demonstration settings. They should not be described as authoritative health advice. `AUTO_CREATE_SCHEMA=true` is for disposable test databases only; use Alembic migrations for a maintained database. Back up any database before applying migrations.

## Demonstration workflow

1. Register a local account. With test configuration, email verification is disabled by default; production email behavior requires provider configuration.
2. Create or select a home and create a room.
3. To demonstrate dashboard or alert behavior without hardware, submit a reading using the owner-only demo route. Clearly state that it is simulated.
4. To demonstrate device ingestion, provision a sensor and securely retain the one-time returned device key. The key is not recoverable from the stored hash.
5. To demonstrate historical replay, choose a CSV with a timestamp field and supported measurement columns. The application validates file type/content, size, row limits, timestamps, and units; it records source provenance.
6. Review history, alerts, and analytics pages. Forecasts are conditional and may be reported unavailable when sample or holdout requirements are not met.

The repository includes `tools/seed_demo_home.py`, which creates an idempotent demo home for an **existing account**; it does not create user credentials. The test fixtures create disposable test users. No verified demo logins are supplied by this documentation.

For detailed account-owner and home-member workflows, see the separate [end-user manual](12_user_manual.md).

## Technology and module reference

The dependency list and source tree are summarized in [document 11](11_technology_stack_and_module_map.md).

## Deployment caution

`render.yaml` describes a Render web-service configuration. It is not proof of a running deployment. No verified Azure deployment is claimed. Before using a public deployment, configure HTTPS, secrets, database access restrictions, a supported persistent database, backups, and tested email settings. The Azure SQL proposal is separate from the active Flask migrations.
