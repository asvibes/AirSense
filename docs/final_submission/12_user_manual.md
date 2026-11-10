# AirSense end-user manual

## Purpose and limitations

This manual describes the local application functions found in the current `divija` source. The UI and route behavior can change. AirSense displays readings supplied to it; it does not measure air on its own. Simulator and historical dataset records are not physical sensor measurements. The app is not a medical diagnostic tool or certified CO2 alarm.

## Roles

- **Owner:** A user with the `owner` membership role for a home. Owners can manage rooms, sensors, thresholds, invitations, and simulator/replay actions.
- **Member:** A user with the `member` role for a home. Members can view home data and use routes specifically available to members; owner-only functions remain restricted.

There is no global facility-manager or system-administrator role in the active app.

## Before starting

For local use, follow [the setup guide](07_setup_and_user_guide.md). A developer must apply database migrations and start Flask. The app opens at `/`. The repository does not provide reviewed demo credentials.

## Account access

1. Select Register and submit the requested account details.
2. If email verification is enabled, request and enter the one-time verification code. The configured mail provider must be operational for delivery; a local configuration or test setup may disable verification.
3. If already registered, use Login.
4. For a forgotten password, use the password-recovery page and follow the verification/reset flow.
5. Sign out from the account controls when finished, especially on a shared computer.

Do not share passwords, session cookies, OTPs, reset tokens, or device keys. Exact form feedback depends on application configuration.

## Home and room setup

1. After authentication, select an existing home or create one.
2. Create rooms and enter ventilation-source information where appropriate.
3. Room names are unique within a home (case-insensitive at the database index).
4. Owners can edit a room's name and ventilation sources. Room deletion is not implemented.
5. Invite a household member by email from the home-membership workflow. Invitations are single-use, expire after 24 hours, and are limited to the invited email. Email delivery depends on Brevo configuration.

## Add a sensor

1. As a home owner, open sensor management and provision a sensor for the correct room.
2. Copy the returned device key into the sensor client securely. It is returned only during provisioning or rotation; the application stores a keyed hash rather than a recoverable raw key.
3. Send device readings to `POST /api/sensors/<sensor_id>/readings` with the `X-Device-Key` header.
4. A sensor can be revoked or its key rotated by an owner. Revoke a suspected exposed key promptly.
5. The displayed freshness is calculated from last-seen time and the sensor's configured reporting interval; it does not establish that the sensor itself is calibrated or functioning correctly.

The repository includes an AirGradient payload normalizer for a JSON payload containing `rco2`; no physical AirGradient hardware test is claimed.

## Simulated readings and historical CSV

### Simulated reading

Use the owner-only demo/simulator action to select a room and either a supported scenario or a value, metric and unit. Submitted rows are stored with source `simulated`. State clearly in any demonstration that the values are simulated.

### CSV dataset replay

1. Select the destination room and a CSV/TXT file with a timestamp column.
2. Ensure timestamp values are parseable; timezone-naive dataset timestamps are treated as UTC by the parser.
3. Include recognized metric columns with explicit supported units unless the file matches the documented DALTON schema.
4. Choose a row limit between 1 and 1,000. Files larger than 16 MB are rejected.
5. Review the parser's accepted/rejected/duplicate information before interpreting the data.
6. Timestamp shifting, when selected, moves the latest sample to the current time while preserving relative spacing.

Replay data is stored as `dataset`, remains historical data, and does not create live alerts through the batch replay path. The source CSV is not bundled.

## Dashboard, alert and policy use

- Use the dashboard to review available rooms, readings, alerts and sensor freshness for an authorized home.
- A reading uses a metric and unit; interpret values together with the timestamp and source label.
- Alert levels in code include high, sustained elevated and rapid rise. Acknowledgement changes an alert state; it is not a measurement correction or safety certification.
- Threshold policies can be reviewed and updated by an owner. Existing defaults such as CO2 thresholds are illustrative configuration only and are not represented as health guidance.
- Alert clearing depends on the configured below-threshold duration and maximum gap between readings. Missing data can prevent a clear transition.

## History, analytics, forecasts and exports

1. Open History to filter stored readings by the available room/sensor/metric/time options.
2. Open Analytics to view summary/trend views represented by the application.
3. CSV and PDF exports are available through the history routes.
4. The Predictions page can only show a forecast when an offline model evaluation has been generated and passed its evidence checks. Training requires at least 30 distinct timestamps for a series and the linear trend must improve MAE by at least 5% over a persistence baseline on a chronological holdout.
5. Forecasts are statistical estimates with residual-based intervals, not guaranteed predictions. They are limited to a maximum 24-hour horizon.

The offline training command is `python -m app.ml.train`. It reads device/dataset sources, excludes simulated rows, and writes model/evaluation JSON under the app instance directory. A user should not expect an immediate forecast merely from opening the page.

## Photos, invitations and support

Authorized home members can upload, retrieve and delete room photos using the private upload routes. JPEG, PNG and WebP files are supported with a 5 MB per-file limit. Local filesystem configuration does not imply a hosted private-storage integration.

For report or API integration questions, see [the API reference](06_api_reference.md). For setup errors, check migrations, environment variables, database path, and application logs without exposing credentials. No help desk or live production support contact was found in the repository.
