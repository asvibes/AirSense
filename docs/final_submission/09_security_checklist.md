# Security checklist

**Scope:** Local source and automated test evidence only. A checked code item does not certify a production deployment. “Not verified” means this repository audit cannot establish completion.

| Control | Status | Evidence / limitation |
|---|---|---|
| Passwords are not stored in plain text | Implemented in code | Password helper uses Werkzeug scrypt hashing. |
| Password policy is validated | Implemented in code | Application requires 12–256 characters with at least one letter and number. |
| Device keys are not stored as raw values | Implemented in code | Keyed hashes and constant-time verification are used; provisioning returns the secret once. |
| Invitation and challenge credentials are protected | Implemented in code | Invitation/OTP/reset values are hashed with expiry/attempt state in the active models and services. |
| Authenticated mutation CSRF checks | Implemented in code | Session-protected mutations validate CSRF tokens; verify coverage for any future routes. |
| Server-side home/role authorization | Implemented in code | Home-scoped membership checks use owner/member roles; automated access-control tests exist. |
| Device and demo request validation | Implemented in code | Reading, timestamp, metric/unit, room binding, rate and replay limits are checked. |
| SQL query safety | ORM is used in active query paths | No independent adversarial SQL-injection assessment is claimed. |
| Duplicate and alert lifecycle constraints | Implemented in schema and service | Reading uniqueness and open-alert uniqueness/check constraints exist; selected database tests cover behavior. |
| Audit events avoid raw device/invitation secrets | Intended in application event details | Event selection and details are partial; inspect new event types before deployment. |
| Error responses avoid stack traces | Implemented and tested for selected paths | Error handlers and error-response tests exist; not a full information-disclosure audit. |
| Security response headers | Implemented and tested | Flask sets CSP and related headers; HSTS is conditional on secure production requests. |
| Secret values in repository | Example file uses placeholders | `.env.example` contains configuration placeholders. Verify actual local/deployment secrets independently; none should be published. |
| Upload validation and private path | Implemented in code and selected tests | Room upload service validates files and authorizes retrieval; hosted filesystem controls are not verified. |
| HTTPS at deployment | Not verified | No reachable deployment was tested. `render.yaml` is configuration only. |
| Production secret management | Not verified | No cloud secret-store evidence or deployment export was inspected. |
| Database firewall/network restrictions | Not verified | No Azure resource evidence. |
| Least-privilege hosted identity | Not verified | No deployed database principal or permissions evidence. |
| Backup, restore, retention and deletion policy | Not verified | No operational procedure or restore evidence found. |
| Azure SQL schema application | Not verified | SQL Server scripts are separate from active Alembic schema. |
| Blob Storage private access | Not implemented/verified | No active Blob adapter was found. |
| Power BI access controls | Not verified | The tracked `.pbix` is empty. |
| Independent penetration test / threat review | Not evidenced | This checklist is not a substitute for one. |

## Remaining release checks

Before any public use, the project team should verify a specific deployed build and URL; HTTPS, cookies, secrets, database network and identity configuration; backup and restore; rate-limit behavior under the chosen deployment; file persistence/access; and email delivery. Capture evidence with secrets and personal information redacted. These are recommendations, not claims that the checks have been performed.
