# Test results and submission evidence register

**Evidence snapshot:** 10 November 2026
**Branch inspected:** local `divija`
**Commit at HEAD when audited:** `4b79836`

## Automated test evidence

The full Python suite was run from the repository root with:

```powershell
python -m pytest -q
```

**Observed result:** 202 passed, 14 warnings, in 79.58 seconds. The warnings include Alembic's `path_separator` deprecation notice and SQLAlchemy's inability to reflect a SQLite expression-based index. No test failures were reported. The run included the pre-existing staged application/test changes in the local working tree; it did not test only the committed `4b79836` snapshot.

The suite includes coverage for reading validation/ingestion, alert scenarios and wording, access control, device provisioning, authentication rate limits and email flows, database/migration behavior, audit records, exports, CSV replay, forecasts, timestamps, dashboard routes, room uploads, AirGradient payloads, and demo-home seeding.

### Verified coverage areas

| Area exercised | Representative test files |
|---|---|
| Authentication, registration, recovery and rate limiting | `test_landing_auth.py`, `test_email_flows.py`, `test_auth_rate_limits.py` |
| Home authorization and membership | `test_access_control.py`, `test_invitation_acceptance_flow.py` |
| Sensor provisioning and ingestion | `test_provisioning.py`, `test_ingestion.py`, `test_airgradient.py` |
| Threshold/alert rules, acknowledgement and lifecycle | `test_thresholds.py`, `test_alert_scenarios.py`, `test_alert_wording.py` |
| Database constraints, migrations, workflow and rollback | `test_database.py`, `test_database_workflow.py` |
| History and exports | `test_history_page.py`, `test_csv_exports.py` |
| Dataset/CSV parsing and replay | `test_dalton_replay.py`, `test_json_request_validation.py` |
| Forecast evaluation | `test_forecasting.py` |
| Audit, timestamps, errors and response headers | `test_audit.py`, `test_timestamps.py`, `test_error_handlers.py`, `test_security_headers.py` |
| Dashboard, uploads, simulator and demo seeding | `test_dashboard_live_updates.py`, `test_room_uploads.py`, `test_simulator.py`, `test_seed_demo_home.py` |

This is feature-level test coverage, not a statement that every branch or requirement has a passing test. A line/branch coverage percentage was **not measured** because the run used `pytest -q` without coverage instrumentation. No JavaScript test runner result was collected.

This evidence is limited to the Python test suite. It is not a browser end-to-end run, PostgreSQL or Azure SQL integration test, load test, physical-sensor calibration, or penetration test. PostgreSQL migration/test jobs are configured in CI, but a successful CI run was not verified. The repository contains JavaScript test files, but no result for a JavaScript test runner was collected for this evidence snapshot.

### Representative test cases

The expected behavior below is taken from the named tests. “Observed” refers to the full Python suite result above, not a separately captured per-test report.

| Test area and evidence | Expected result | Observed result |
|---|---|---|
| Authentication (`test_landing_auth.py`, `test_email_flows.py`) | Registration, login, verification/recovery paths follow validation and session rules | Suite passed; 202 tests total |
| Authorization (`test_access_control.py`, `test_invitation_acceptance_flow.py`) | Cross-home access is denied; invitations are limited to the intended account and single use | Suite passed; 202 tests total |
| Ingestion (`test_ingestion.py`, `test_airgradient.py`) | Valid supported payload is normalized and stored; invalid room/source data is rejected | Suite passed; 202 tests total |
| Alerts (`test_alert_scenarios.py`, `test_thresholds.py`) | Configured crossings create appropriate alert states; duplicate active alerts are suppressed | Suite passed; 202 tests total |
| History and exports (`test_history_page.py`, `test_csv_exports.py`) | Authorized history queries and export routes return supported results | Suite passed; 202 tests total |
| Dashboard (`test_dashboard_live_updates.py`, `test_room_dashboard_integration.py`) | Dashboard data is returned for authorized home context | Suite passed; 202 tests total |
| JavaScript trend/source averages (`dashboard_room_trends.test.js`, `dashboard_co2_averages.test.js`) | Rising/falling/stable trends and source-separated averages are calculated correctly | Not executed: Node.js test runner unavailable; assertions exist in repository |

This table summarizes selected test intent, not individual test counts or a line-coverage report. See the unverified scenarios above before treating the project as deployment-tested.

## Submission deliverable register

| Brief item | Repository evidence | Status |
|---|---|---|
| Deployed frontend and backend | Flask application and a `render.yaml` service description | Application code/configuration present; live deployment and URL not verified. No Azure deployment is established. |
| SQL schema and query | `database/migrations/001...008`, seed SQL, and `database/queries/reading_transaction_example.sql` | Present as a proposed SQL Server track; distinct from the active ORM/Alembic schema and not applied to a verified Azure database. |
| ER diagram and design document | Mermaid ER diagram in [document 4](04_er_diagram_and_database_design.md); existing `docs/architecture.md` | Included in this package for current ORM; diagram/design must not be mistaken for deployed cloud architecture. |
| API list and setup/README | [documents 6 and 7](06_api_reference.md) and repository `Readme.md` | Present, based on local route code and setup. |
| Data classification | [document 8](08_data_classification_and_threat_model.md) | Included as a code-based student-project note; not a legal/privacy assessment. |
| Azure resource screenshots | No screenshot files or Azure resource evidence found | Missing; obtain only from actual resources and redact credentials, identifiers, and personal data. |
| Power BI report | `database/powerbi/airsense-report.pbix` has length 0 bytes | Missing/placeholder; no finished report or connection verified. |
| Threat model and security checklist | [documents 8 and 9](08_data_classification_and_threat_model.md) | Included; controls dependent on a live environment are explicitly not verified. |
| Test evidence | This document and the Python suite result above | Python tests passed as reported; other integration/e2e test classes not evidenced. |
| Demo accounts per role | Test fixtures create disposable accounts; `tools/seed_demo_home.py` requires an existing account | No reviewed demo credentials are provided. The implemented roles are owner/member, not the three global roles in the proposed PRD. Do not publish test secrets. |
| Full commit history | Git history reachable from local `divija` | Snapshot appended below (100 commits at audit time). It records subjects only; use the repository for full commit objects, authorship, timestamps, and diffs. |
| Level 0 and Level 1 DFD | [Document 13](13_data_flow_diagrams.md), with SVG and PNG exports | Added; logical current-code flows, not a production network trace. |
| User manual | [Document 12](12_user_manual.md) | Added for implemented user workflows; no usability study is claimed. |
| Technology stack and module documentation | [Document 11](11_technology_stack_and_module_map.md) | Added from repository dependencies and source tree. |
| Complete B.Tech report | [Document 14](14_btech_final_project_report.md) | Drafted with institution/student/supervisor placeholders; team must supply verified academic details and any required scholarly references. |

## Items requiring project-team action

1. Supply student/institution details and required college formatting from verified records.
2. If the rubric requires live-cloud evidence, deploy and test the selected build, then collect genuine, redacted resource screenshots and connectivity evidence.
3. Build and verify the Power BI report against a deliberately selected data source; do not present the empty placeholder as a report.
4. Decide whether to retain the proposed Azure SQL target or document the active local/SQLAlchemy database as the final implementation. Reconcile the schema before claiming the SQL target is active.
5. Create demo accounts only in a controlled environment and distribute credentials securely. The repository does not contain production/demo passwords.
6. Preserve simulated and dataset source labels in any presentation; do not imply those records came from physical hardware.

## Full local `divija` commit history

The following is a point-in-time subject list from `git log --format="%h %s" HEAD`. It is not a substitute for the Git repository, which retains the full commit objects. Local staged/unstaged changes are not commits and are intentionally absent.

4b79836 fix: integrate trends and source averages into live dashboard
a0c8418 fix: separate CO2 averages by source
1df51af feat: add room card trend indicators
28d7018 fix: hide invitation controls from non-owners
a1bd064 fix: correct landing page navigation
607d9c0 feat: add single-page OTP registration
5b99dbd feat: add live dashboard updates
7574e77 fix: enforce HSTS for production HTTPS
8a60439 fix: harden Render proxy and security headers
d81a900 feat: complete invitation acceptance flow
b29b40a fix: prevent duplicate home invitations
83bbabf fix: centralize authenticated session setup
51fa762 perf: batch DALTON replay ingestion
9460ca2 fix: prevent duplicate demo submissions
ee39053 fix: simplify registration and password recovery flow
4c70cb4 fix: add email verification resend to login
1dd3290 fix: resolve registration flow and improve email diagnostics
ca4e0cd feat: add secure password reset resend flow
b0543c3 fix: make rate limiting and database tests PostgreSQL-compatible
53ec5b4 fix: complete reading validation and CI compatibility
856e25d fix: validate sensor readings and DALTON gaps
8fdf4ff fix: harden email delivery configuration
788af41 fix: require explicit transactional email configuration
eb3ef20 fix: make login failure rate limits atomic
37e183e fix: restrict legacy reading submission to owners
0c0823f fix: make email verification migration PostgreSQL compatible
7c6eebb security: complete application hardening
f5f0bd2 fix: harden authentication and email security
ad86bec feat: add transactional email flows and improve charts
6c99b04 fix: improve application-wide text contrast
050e517 feat: improve dashboard predictions and alerts
6159e18 Fix predictions and member invitations
56b1fd8 Fix DALTON CSV parsing and parameter mapping
a3cca86 Add multi-parameter dataset support
1f71293 Fix landing and home navigation flow
dc9bdca Remove unused empty project files
e126d8f Unify Insights theme and refine scrollbar styling
4ecdcc4 Complete AirSense frontend and analytics features
d0367a6 feat: improve dashboard sidebar and account menu
cde1a1c feat: connect dashboard and auth navigation
5dbec34 feat: integrate custom error pages
22ba0ba fix connect landing page and login routing
82de75e Merge pull request #14 from asvibes/agents/generic-fix-request
b9d8f42 Agent Host changes for agents/generic-fix-request
727b3ea feat: add landing page and improve login navigation
b002d06 feat: restore upload support and add landing page
2de0f22 fix: improve CSV safety and DALTON replay handling
908c75a Merge pull request #13 from asvibes/divija
74476dc Merge pull request #12 from asvibes/revert-11-shreya
e4f4388 Revert "feat: implement uploads and AirGradient support"
4e3aac3 Merge pull request #11 from asvibes/shreya
8223802 Merge branch 'divija' into shreya
96085bc chore(git): ignore local secrets and database artifacts
114ef9e docs: update database and implementation status
a3232c2 feat(rooms): add owner room editing to the dashboard
bc6e058 fix(api): validate JSON objects and sanitize CSV exports
82730cb fix(ingestion): make replay atomic and audit rejection events
72de21c feat(db): align schema and persist server receipt timestamps
07203e4 feat: implement uploads and AirGradient support
01e34ec docs: update empty files audit findings
af85f6c chore: stop tracking Python cache files
d1cb37a fix: wire DALTON replay button click handler
73f5fc0 feat: complete DALTON replay demo flow
b189687 feat: add DALTON replay ingestion
c9f9fa6 Merge pull request #9 from asvibes/divija
f880410 docs: remove trailing README blank line
51b23f3 Merge remote-tracking branch 'origin/shreya' into divija
2567f33 Update AirSense dashboard UI and navigation
84034f3 Update AirSense dashboard UI and navigation
c2ead0c docs: fix README conflict and update documentation
646df7c Merge remote-tracking branch 'origin/divija' into shreya
cff1a47 docs: update README
500e035 feat: integrate simulated readings with ingestion pipeline
fda59ad Merge pull request #8 from asvibes/divija
47a8fef feat: add human-readable alert messages
f353c93 added seed files
f1a0b24 Restore SQL database migrations
9618fbc docs: refresh empty files audit
ac1ddd0 Merge latest Shreya branch into divija
9850a65 docs: document AirSense architecture and requirements
b893c50 backend: Connect AirSense dashboard and services
9d3ef5d database: add Azure SQL schema and seed scripts
916c1f5 Merge pull request #7 from asvibes/divija
f83c868 Agent Host changes for divija
b002115 Merge pull request #6 from asvibes/feat/airsense-dashboard
cbca63b frontend: Improve history chart and add dark theme
16e4cf5 Merge pull request #5 from asvibes/feat/airsense-dashboard
f5b1727 frontend: Add connected AirSense dashboard
5d4dbb5 Merge pull request #4 from asvibes/shreya-2
385a528 updated readme
1899e57 Update Readme.md
330fcc8 Merge pull request #3 from asvibes/divija
8b70168 Agent Host changes for divija
bd485bd Implement configurable alert lifecycle and persistence
abb8bd5 Merge pull request #2 from asvibes/agents/airsense-indoor-air-quality-dashboard
569ccaf Agent Host changes for agents/airsense-indoor-air-quality-dashboard
e488c53 Merge pull request #1 from asvibes/divija
bbf7ad6 Added files empty
d86c41e Add AirSense project documentation
128fc1a Add READMm.md
