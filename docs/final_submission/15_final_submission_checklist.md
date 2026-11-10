# AirSense final college submission checklist

This checklist maps the student guide supplied by the team to repository evidence. It does not assert that reviews, registration, deployment, or faculty approvals occurred. The guide's submission deadline of 6 November 2026 has passed; ask the project lead/mentor whether late submission is authorized before representing this package as submitted.

## Registration and team requirements

- [ ] Confirm the project appeared as **Taken** on the public list before work began; the registration/public-list links are not included in the supplied guide text.
- [ ] Confirm one registration form was filed for the team and every member accepted the undertaking.
- [ ] Confirm the team has one or two members, belongs to one project, and meets the solo (at least three) or pair (at least five) core-feature minimum.
- [ ] Use verified student records to check names, roll numbers, team size, project title and registration description; the repository cannot establish the registered team or idea status.
- [ ] If a pair, ensure individual contribution can be explained in the viva and supported by genuine commit history. Do not manufacture commits or divide one change artificially.

## Review milestones

| Guide milestone | Required hand-in | Evidence in this repository | Status |
|---|---|---|---|
| Design review — 19 October 2026 | Design document, ER diagram, threat model | [Architecture and data flow](03_architecture_and_data_flow.md), [ER diagram and database design](04_er_diagram_and_database_design.md), and [threat model](08_data_classification_and_threat_model.md) are present. Review submission and approval are not evidenced. | Documents present; review outcome unverified |
| Mid review — 28 October 2026 | Repository link and one core feature working end to end | The [AirSense GitHub repository](https://github.com/asvibes/AirSense) and automated application tests are available. No mentor review record or browser/live demonstration evidence is included. | Repository present; end-to-end demonstration and review unverified |
| Security check — guide says “Last Tuesday” | Live cloud URL, security checklist, analytics report | [Security checklist](09_security_checklist.md) is present as a code-based review with deployment gaps. The team supplied [https://airsense-85qa.onrender.com/](https://airsense-85qa.onrender.com/); at this check the page and `/api/health` returned HTTP 503 via the web checker, while direct requests timed out. A standalone [HTML analytics report](../../database/powerbi/airsense-analytics-report.html) is present, generated from explicitly synthetic data; the `.pbix` remains empty. | URL supplied but service availability not verified; analytics file present but not a Power BI report or live analytics connection; checklist does not establish deployed security |

Repository files cannot prove registration, milestone hand-in, faculty review, or approval. Keep the team's actual submission receipts and review records separately.

## Four-subject rubric crosswalk

| Subject | Guide requirement | Current evidence | Remaining gap / status |
|---|---|---|---|
| System Design | Functional and non-functional requirements; architecture/data flow; API list; one written trade-off | Requirements/traceability, architecture and DFDs, API reference, plus a retrospective modular-monolith trade-off are documented. | Documents are present; verify they match the faculty template and explain them in the viva. |
| RDBMS | 3NF relational schema with at least five related tables; keys/constraints; joins; view; stored procedure or trigger; transaction; indexes; ER/schema/query hand-in | Active ORM ER/schema documents 13 tables and relationships. The separate proposed SQL scripts contain 11 related tables, keys/constraints, explicit indexes, joins, two views, one trigger, and transaction examples; see the detailed [SQL rubric review](05_sql_artifacts_and_schema_status.md#rdbms-rubric-coverage-review). | Azure SQL scripts are not wired to the application or applied to a verified database. 3NF is not formally assessed. Do not present proposed scripts as the active schema. Confirm the final schema/query files satisfy faculty expectations. |
| DP-900 | Structured/semi-structured/unstructured classification; relational database hosted on Azure; non-relational file/semi-structured store; analytics view | Data classification note distinguishes all three formats; a standalone descriptive HTML report and synthetic CSV are provided as an analytics file. | Azure relational hosting is unverified; Blob/Cosmos integration is absent; HTML output is not a Power BI report and has no live connection; tracked `.pbix` remains zero bytes. Major unmet evidence/implementation requirements. |
| Cloud Security | Role-based login; password hashing; HTTPS; repository secret hygiene; SQL injection/XSS input protections; DB firewall/network rule; activity log; one-page threat model and completed checklist | Local code documents home-scoped owner/member checks, scrypt hashes, request validation, ORM use, security headers, audit events, a threat model, and a security checklist. | Live HTTPS, database firewall/network rule, deployed secrets, and cloud checklist evidence are unverified. No independent SQL injection/XSS assessment is claimed; checklist has unresolved deployment controls. |

## Required final hand-in (five items)

| Required item | Current repository evidence | Status |
|---|---|---|
| Live URL of cloud application | Team supplied [https://airsense-85qa.onrender.com/](https://airsense-85qa.onrender.com/). The page and `/api/health` check returned 503; direct requests timed out. | URL known; deployment currently unavailable/unverified. Recheck with the project owner/Render dashboard before claiming operational. |
| Repository link, full commit history, README setup and test login for every role | [Repository](https://github.com/asvibes/AirSense), Git history, and README setup/test commands exist. No reviewed test login credentials per role are documented; never publish passwords in the repository. | Partial; arrange demo access securely and verify the link/history |
| Project report with required topics, screenshots and credits | [Report](14_btech_final_project_report.md) covers the project topics and now discloses Copilot assistance in its documentation drafting. | Draft; genuine application screenshots, verified academic citations, team/college details, final formatting and any other actual third-party/AI credits remain |
| Schema script and query file | SQL Server schema scripts and `database/queries/reading_transaction_example.sql` exist. | Present as proposed coursework artifacts; not proof of active Azure SQL deployment |
| Analytics report as a file or link | [Standalone HTML report](../../database/powerbi/airsense-analytics-report.html) and [synthetic dataset](../../database/powerbi/airsense-synthetic-readings.csv). | File deliverable present and reproducible; it is not a Power BI report or live-data analysis. The `.pbix` remains an empty placeholder. Confirm with faculty whether standalone HTML satisfies their expected format. |

## Academic identity and report

- [ ] Replace the report's institution and department placeholders using official names.
- [ ] Add academic year/semester and submission date.
- [ ] Add every student name and roll number exactly as recorded by the institution.
- [ ] Add the project guide's name and designation.
- [ ] Complete the certificate, declarations, signature/date lines, and institution seal only through the institution's required process.
- [ ] Add acknowledgements only for people/support confirmed by the team; remove the instruction if acknowledgements are not required.
- [ ] Apply the required title page, margins, fonts, pagination, heading hierarchy, citation style, and final table of contents.
- [ ] Review all report claims against the implementation and ensure unverified deployments, hardware, mail, or cloud integrations are not described as operational.

## Academic references

- [ ] Check the project rubric for the number, type, and citation style of required references.
- [ ] Add complete, genuine sources that the team has read and verified, especially for indoor-air quality/ventilation, CO2 interpretation and limitations, and time-series methods/evaluation.
- [ ] Add sensor calibration references only if the report includes actual hardware measurements.
- [ ] Add in-text citations for claims based on external sources and ensure every citation has a matching bibliography entry.
- [ ] Confirm source metadata (authors, title, venue/publisher, year, page range, DOI/stable URL, and access date when required); do not retain the topic prompts as citations.

## Figures and screenshots

- [ ] Review the embedded system architecture, DFD Level 0, DFD Level 1, and ER figures at full size and at the intended print/page scale.
- [ ] Keep the editable SVG sources with the submission package if the rubric requires editable diagrams.
- [ ] Replace Appendix D screenshot slots only with genuine screenshots captured from the actual application, or remove slots that are not applicable.
- [ ] For each screenshot, record the true capture date, application build/environment, page/workflow, and relevant user role.
- [ ] Redact names, email addresses, personal/home data, session material, passwords, OTP/reset tokens, device keys, and other secrets before inserting screenshots.
- [ ] Label simulated or dataset readings accurately; do not imply that they are physical sensor measurements.
- [ ] Do not use mock-ups as evidence or imply a screenshot proves deployment, hardware operation, or external-service delivery.

## Ten required documentation deliverables

- [x] ER diagram and data dictionary describe the active entities, attributes, keys, relationships, and field meanings.
- [x] System architecture diagram is present.
- [x] DFD Level 0 and Level 1 are present.
- [x] Threat model is present and states its limitations.
- [x] API reference documents inspected routes, auth conventions, representative response shapes, and a clearly illustrative device request example.
- [x] Testing report includes representative expected/observed cases, exact suite result, and distinguishes feature coverage from unmeasured line/branch coverage.
- [x] Installation/setup guide is present for the local demonstration environment.
- [x] User manual describes supported user workflows and limitations.
- [x] Technology stack and module documentation matches declared dependencies and source modules.
- [ ] B.Tech final project report has been reviewed and formatted to the department's requirements.

The [documentation index](01_submission_index_and_project_summary.md#ten-brief-deliverables--direct-links) links to each deliverable.

## Results and evidence

- [x] Run the Python suite on clean pushed commit `27a83d1`; result and warnings are recorded in [document 10](10_test_and_submission_evidence.md). Rerun if application code changes before final submission.
- [ ] Run the three JavaScript tests in an environment with Node.js; Node.js is unavailable in the current environment, so no pass result is claimed.
- [ ] Add a coverage percentage only after running coverage instrumentation; no percentage has been measured.
- [x] Record the clean-commit Python test result and successful push/pull-request CI results for `0fe75da` without claiming unverified browser, cloud, or hardware testing.
- [ ] Add deployment, Azure, Power BI, PostgreSQL, email-provider, or hardware evidence only if the team has actually produced and verified it.
- [ ] Confirm the Power BI artifact and any resource screenshots are genuine, readable, and appropriately redacted before claiming them complete.
- [ ] Remove or retain every placeholder intentionally; do not submit accidental `[Insert ...]` fields or empty screenshot slots as completed content.

## Final package review

- [ ] Open the final Markdown/PDF export and check page breaks, table wrapping, figure sizing, captions, and link behavior.
- [x] Verify the final-submission Markdown's 109 relative file links and 17 internal heading anchors; all resolved, including links to the standalone analytics HTML and CSV. Recheck after later edits or file moves.
- [x] Confirm the current branch is `divija`; recheck the final package state before submission.
- [x] Preserve the team's existing staged and unstaged changes; no pre-existing changes were staged, unstaged, or overwritten during this documentation pass.
- [ ] Obtain any required guide/department approval before final submission.
