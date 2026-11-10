# AirSense API reference

This is a route-family reference based on the Flask blueprints in `app/routers/`. It describes the local application, not an externally reachable deployed service. Request and response details can evolve with the source.

## Authentication conventions

- Protected user APIs use a signed Flask session and apply home membership/role checks. Registration, login, and recovery routes are public account workflows; signed-in mutations require CSRF validation. `GET /api/health` is public and checks database query availability.
- Cookie/session-based mutating requests require `X-CSRF-Token` (or an accepted form token where applicable). Device-key sensor ingestion uses its device credential instead.
- Sensor ingestion uses `X-Device-Key`, not the browser session.
- Most successful create operations return `201`; validation failures generally return `400`; missing authentication returns `401`; missing access to a home can be hidden as `404`, and insufficient role can return `403`. Exact behavior is route-specific.
- JSON request bodies are parsed and validated; clients should not assume an invalid payload succeeds.

## Account and session routes

| Method and path | Purpose |
|---|---|
| `GET /api/me` | Current authenticated account and home membership information |
| `POST /api/auth/register/send-otp` | Request a registration verification code |
| `POST /api/auth/register` | Register, optionally verifying an OTP depending on configuration |
| `POST /api/auth/verify-email` | Verify an email challenge |
| `POST /api/auth/verify-email/resend` | Resend an email verification challenge |
| `POST /api/auth/login` | Start an authenticated session |
| `POST /api/auth/logout` | End the authenticated session |
| `POST /api/auth/forgot-password` | Request a password-reset challenge |
| `POST /api/auth/forgot-password/resend` | Resend a password-reset challenge |
| `POST /api/auth/verify-reset` | Verify reset challenge and issue reset state |
| `POST /api/auth/reset-password` | Complete password reset |

HTML routes also exist for login, registration, verification, forgot-password, and reset pages. Legacy form aliases are registered alongside several `/api` endpoints.

## Homes, rooms, sensors, and measurements

| Method and path | Purpose / access |
|---|---|
| `GET /api/homes` | List the signed-in user's homes |
| `POST /api/homes` | Create a home |
| `POST /api/active-home` | Select a home for the browser session |
| `GET /api/homes/<home_id>/members` | List members; owner/member access |
| `POST /api/homes/<home_id>/invitations` | Create and email invitation; owner only |
| `POST /api/invitations/accept` | Accept an invitation for the invited account |
| `DELETE /api/homes/<home_id>/members/<user_id>` | Remove eligible member; owner access |
| `GET /api/homes/<home_id>/rooms` | List rooms; home access |
| `POST /api/homes/<home_id>/rooms` | Create room; owner only |
| `PATCH /api/homes/<home_id>/rooms/<room_id>` | Edit room name/ventilation; owner only |
| `GET /api/homes/<home_id>/sensors` | List sensors; owner/member access |
| `POST /api/homes/<home_id>/sensors` | Provision sensor; owner only, returns a one-time device key |
| `POST /api/homes/<home_id>/sensors/<sensor_id>/rotate-key` | Rotate key; owner only |
| `POST /api/homes/<home_id>/sensors/<sensor_id>/revoke` | Revoke sensor; owner only |
| `POST /api/sensors/<sensor_id>/readings` | Device-key-authenticated measurement ingestion |
| `GET /api/homes/<home_id>/dashboard` | Home dashboard data; home membership required |

The sensor endpoint accepts the application's reading payload and recognizes an AirGradient-style JSON payload with `rco2`. The route binds that payload to the provisioned sensor's room, then uses shared validation/ingestion. Device requests are limited and rejected for invalid, inactive, or unauthenticated sensors.

## Thresholds, demo, history, analytics, and exports

| Method and path | Purpose |
|---|---|
| `GET /api/homes/<home_id>/thresholds` | Read home threshold policies |
| `PUT /api/homes/<home_id>/thresholds` | Batch update thresholds |
| `PUT /api/homes/<home_id>/thresholds/<room_id>/<metric_code>` | Update one room/metric policy |
| `POST /api/homes/<home_id>/demo/readings` | Submit owner-authorized simulated reading |
| `POST /api/homes/<home_id>/demo/replay` | Upload and replay a validated dataset CSV |
| `GET /api/homes/<home_id>/history` | Filter and read home history |
| `GET /api/homes/<home_id>/history/options` | List available metric filters |
| `GET /api/homes/<home_id>/history.csv` | Download filtered history as CSV |
| `GET /api/homes/<home_id>/history.pdf` | Generate a history PDF |
| `GET /api/homes/<home_id>/predictions` | List saved model evaluations or request forecast data |
| `GET /api/homes/<home_id>/activity` | Read home activity log; owner-only route |
| `POST /api/homes/<home_id>/rooms/<room_id>/photos` | Upload an authorized room photo |
| `GET /api/homes/<home_id>/rooms/<room_id>/photos/<filename>` | Retrieve an authorized room photo |
| `DELETE /api/homes/<home_id>/rooms/<room_id>/photos/<filename>` | Delete an authorized room photo |

Related HTML pages include `/alerts`, `/history`, `/analytics`, and `/predictions`. The database health endpoint is `GET /api/health`.

## Compatibility routes

The `alerts` blueprint also retains legacy authenticated routes including `/api/dashboard`, `/api/alerts`, `/api/policies`, `/api/readings`, and `/api/alerts/<alert_id>/acknowledge`. `REQUIRE_API_TOKEN` applies only as an additional gate in that legacy blueprint; it is not a global replacement for session, membership, or device authentication.

The exact legacy aliases present in the route decorators are:

| Method and path | Purpose |
|---|---|
| `GET /api/dashboard` | Legacy dashboard response |
| `GET /api/alerts` | Legacy alert listing |
| `POST /api/policies` | Legacy policy creation/update path |
| `POST /api/readings`, `POST /readings` | Legacy reading submission aliases |
| `POST /api/alerts/<alert_id>/acknowledge`, `POST /alerts/<alert_id>/acknowledge` | Acknowledge a legacy alert |

## HTML page routes

These are browser pages, not JSON API endpoints:

| Method and path | Page |
|---|---|
| `GET /` | Landing page |
| `GET /login`, `GET /register` | Authentication pages |
| `GET /verify-email`, `GET /forgot-password`, `GET /reset-password`, `GET /join` | Verification, recovery, and invitation pages |
| `GET /alerts`, `GET /history`, `GET /analytics`, `GET /predictions` | Authenticated application pages |

Authentication form aliases `POST /register/send-otp`, `/register`, `/verify-email`, `/verify-email/resend`, `/forgot-password`, `/forgot-password/resend`, `/reset-password`, `/login`, and `/logout` are registered alongside corresponding `/api` operations. Exact handling depends on whether the request is a browser form or JSON.

This route inventory is derived from the route decorators in `app/routers/`; it is not a guarantee of backward compatibility. Query parameters, request schemas, and response schemas are route-specific and should be checked in the implementation.

## Payload and operational details

Reading validation accepts a room, metric, numeric value, unit, and optional timezone-aware ISO-8601 `measured_at`; the default metric is CO2. Metric-specific aliases and supported units are normalized by application code. Device reading timestamp age/future checks are configurable. Dataset replay requires a timestamp column, is limited by configuration to 16 MB and at most 1,000 imported rows, and uses `source=dataset`.

Provisioning and key rotation responses contain a one-time secret and should be handled as credentials. The public route list does not include every form alias or every JSON field; use the corresponding router implementation and tests when integrating a client.

Invitation creation also returns the invitation token in its JSON response while sending the invitation email. Treat that token as a secret.

## Response shapes and endpoint-specific behavior

The routes return JSON for `/api/` paths unless noted. Exact status and response details are implemented per route; common examples include:

| Endpoint | Successful response shape / status |
|---|---|
| `GET /api/me` | `200`: `user`, `csrf_token`, and `homes` |
| `POST /api/auth/register/send-otp` | `202`: generic `message`; avoids disclosing whether an address is registered |
| `POST /api/auth/register` | `201`: `user` and `home` when registration completes; `202`: `verification_required`, `email`, and `message` when verification is configured |
| `POST /api/auth/verify-email` | `200`: `{"verified":true}` for JSON requests |
| `POST /api/auth/verify-email/resend` | `200`: generic `message` |
| `POST /api/auth/forgot-password` and `/api/auth/forgot-password/resend` | `200`: generic `message` for JSON/API requests |
| `POST /api/auth/verify-reset` | `200`: one-time `reset_token` |
| `POST /api/auth/reset-password` | `200`: `{"status":"password_reset"}` for JSON requests |
| `GET /api/homes` | `200`: `homes` array |
| `POST /api/homes` | `201`: `home` object with `id`, `name`, and `role` |
| `POST /api/active-home` | `200`: selected `home_id` |
| `GET /api/homes/<home_id>/members` | `200`: `members` array |
| `POST /api/homes/<home_id>/invitations` | `201`: `invitation` object, including a one-time token and delivery status |
| `POST /api/invitations/accept` | `200`: `home_id` and `role`; selects the home in the session |
| `DELETE /api/homes/<home_id>/members/<user_id>` | `200`: `{"status":"removed"}` |
| `GET /api/homes/<home_id>/rooms` | `200`: `rooms` array; each room includes readings, trend readings, sensors, and thresholds |
| `POST /api/homes/<home_id>/rooms` | `201`: `room` object |
| `PATCH /api/homes/<home_id>/rooms/<room_id>` | `200`: updated `room` object |
| `GET /api/homes/<home_id>/sensors` | `200`: `sensors` array |
| `POST /api/homes/<home_id>/sensors` | `201`: `sensor` object and one-time `device_key` |
| `POST /api/homes/<home_id>/sensors/<sensor_id>/rotate-key` | `200`: one-time `device_key` |
| `POST /api/homes/<home_id>/sensors/<sensor_id>/revoke` | `200`: `sensor` object with status |
| `POST /api/sensors/<sensor_id>/readings` | `201`: shared ingestion result, including reading and alert lifecycle changes |
| `GET /api/homes/<home_id>/dashboard` | `200`: `home_id`, `readings`, and `alerts` |
| `GET /api/homes/<home_id>/thresholds` | `200`: `thresholds` array |
| `PUT /api/homes/<home_id>/thresholds` | `200`: updated `thresholds` array |
| `PUT /api/homes/<home_id>/thresholds/<room_id>/<metric_code>` | `200`: updated `threshold` object |
| `GET /api/homes/<home_id>/history` | `200`: `readings` array and `range` object |
| `GET /api/homes/<home_id>/history/options` | `200`: `metrics` array |
| `POST /api/homes/<home_id>/demo/readings` | `201`: shared ingestion result, including reading and alert lifecycle changes |
| `POST /api/homes/<home_id>/demo/replay` | `201`: import source, counts, parameters, skipped/duplicate details, and created readings |
| `GET /api/homes/<home_id>/history.csv` | `200`: CSV attachment |
| `GET /api/homes/<home_id>/history.pdf` | `200`: PDF attachment |
| `GET /api/homes/<home_id>/activity` | `200`: `events` array |
| `GET /api/homes/<home_id>/predictions` | Without `metric`, `200`: `models` array; with `metric`, returns availability/reason and forecast data when available |
| `GET /api/health` | `200`: `{"status":"ok"}` if the database query succeeds |
| `POST /api/auth/login` | `200`: `user` object on success; also starts the signed-in session |
| `POST /api/auth/logout` | `200`: `{"status":"signed_out"}` |
| `POST /api/homes/<home_id>/rooms/<room_id>/photos` | `201`: `photo` metadata and retrieval `url` |
| `GET /api/homes/<home_id>/rooms/<room_id>/photos/<filename>` | `200`: private image response |
| `DELETE /api/homes/<home_id>/rooms/<room_id>/photos/<filename>` | `200`: `{"status":"removed"}` |
| `GET /api/dashboard` and `GET /api/homes/<home_id>/dashboard` | `200`: `home_id`, `readings`, and `alerts` |
| `GET /api/alerts` | `200`: `alerts` array; owner access required |
| `POST /api/policies` | `200`: `policy` object |
| `POST /api/readings` and `POST /readings` | `201`: shared ingestion result |
| `POST /api/alerts/<alert_id>/acknowledge` | `200`: `alert` object for JSON requests |

Validation and authorization failures generally return an `error` field. The device endpoint returns `401` for an invalid or inactive device key, `400` for invalid readings, and `429` when rate limited. Authentication, invitation, forecast, upload, and legacy routes have additional route-specific response bodies and status codes; consult their router implementations for exhaustive contracts. The invitation creation response contains a bearer-like token in addition to email delivery, so clients must protect it as a secret.
