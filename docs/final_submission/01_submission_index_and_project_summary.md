# AirSense academic submission package

**Project:** AirSense
**Programme context:** B.Tech CSE (AI/ML) project
**Evidence snapshot:** 10 November 2026
**Evidence baseline:** Local `divija` at pushed commit `27a83d1` on 10 November 2026. The current review's test result was run against this clean commit; subsequent edits in the review are documentation-only.

## Project summary

AirSense is a locally runnable Flask web application for receiving indoor-air measurements, associating them with homes and rooms, evaluating configured rules, and presenting readings, alerts, history, and forecasts. A reading can originate from a provisioned sensor, the simulator, or an uploaded historical dataset. AirSense is software: it does not itself sense or verify indoor air, and simulator or dataset values are not physical measurements.

The current application uses SQLAlchemy models and Alembic migrations, SQLite as its default local database, server-rendered HTML with vanilla JavaScript, and home-scoped `owner` and `member` access. It includes a time-trend forecasting method, but this is not evidence of a deployed or validated AI/ML model. The project is not a medical, health-diagnostic, or certified safety product.

## Existing ten-document batch

| No. | Document | Main evidence |
|---|---|---|
| 1 | This index and project summary | Project context and submission status |
| 2 | [Requirements and traceability](02_requirements_scope_and_traceability.md) | Proposed scope versus implemented behavior |
| 3 | [Architecture and data flow](03_architecture_and_data_flow.md) | Local application structure and data paths |
| 4 | [ER diagram and database design](04_er_diagram_and_database_design.md) | Active ORM entities and relationships |
| 5 | [SQL artifacts and schema status](05_sql_artifacts_and_schema_status.md) | Existing Azure SQL scripts and their limits |
| 6 | [API reference](06_api_reference.md) | Implemented route families and authentication |
| 7 | [Setup and user guide](07_setup_and_user_guide.md) | Local setup and safe demonstration steps |
| 8 | [Data classification and threat model](08_data_classification_and_threat_model.md) | Data sensitivity and concise threat analysis |
| 9 | [Security checklist](09_security_checklist.md) | Code-level controls and deployment gaps |
| 10 | [Test and submission evidence](10_test_and_submission_evidence.md) | Test results, missing evidence register, commit history |

## Final deliverables audit additions

The audit found that the first batch did not fully satisfy the requested final-submission artifacts. The following additions complete the documentation structure and supply rendered diagrams:

| Document | Purpose |
|---|---|
| [Technology stack and module map](11_technology_stack_and_module_map.md) | Verified dependencies and source-module responsibilities |
| [End-user manual](12_user_manual.md) | Role-aware user workflows and operating instructions |
| [DFD Level 0 and Level 1](13_data_flow_diagrams.md) | Context and decomposed data-flow diagrams |
| [B.Tech final project report](14_btech_final_project_report.md) | Full report draft with explicit institutional placeholders |

Editable SVG sources and PNG exports are in [diagrams/](diagrams/). The ER diagram describes all active ORM tables and declared fields; the architecture and DFDs describe code paths, not a verified live deployment.

This package groups the repository's [submission deliverables](../../docs/product-requirements.md#16-deployment-and-submission-deliverables) into ten original documents plus audit additions. Files and evidence not present in the repository are marked as missing or unverified rather than represented as completed.

## Ten brief deliverables — direct links

| No. | Required deliverable | Documentation |
|---|---|---|
| 1 | ER diagram with entities, attributes, keys and relationships | [ER diagram and database design](04_er_diagram_and_database_design.md) · [PNG](diagrams/er_diagram.png) · [editable SVG](diagrams/er_diagram.svg) |
| 2 | System architecture diagram | [Architecture and data flow](03_architecture_and_data_flow.md) · [PNG](diagrams/system_architecture.png) · [editable SVG](diagrams/system_architecture.svg) |
| 3 | DFD Level 0 and Level 1 | [DFD guide](13_data_flow_diagrams.md) · [Level 0 PNG](diagrams/dfd_level_0.png) · [Level 1 PNG](diagrams/dfd_level_1.png) · [editable SVG sources](13_data_flow_diagrams.md#diagram-files) |
| 4 | Threat model | [Data classification and threat model](08_data_classification_and_threat_model.md) |
| 5 | Actual API reference | [API reference](06_api_reference.md) |
| 6 | Testing report and verified results/coverage | [Test and submission evidence](10_test_and_submission_evidence.md) |
| 7 | Installation and setup guide | [Setup guide](07_setup_and_user_guide.md) |
| 8 | User manual | [End-user manual](12_user_manual.md) |
| 9 | Technology stack and module documentation | [Technology stack and module map](11_technology_stack_and_module_map.md) |
| 10 | B.Tech final project report | [Final project report draft](14_btech_final_project_report.md) |

Use the [final submission checklist](15_final_submission_checklist.md) to track remaining team- and institution-specific work. Diagrams are embedded as PNGs in the report and provided as editable SVG sources. Application screenshots are explicitly marked as empty capture slots until the team supplies genuine screenshots.

## Evidence boundary

The repository contains an Azure SQL proposal under `database/`, a Render service configuration, and a zero-byte Power BI placeholder. A reproducible standalone [HTML analytics report](../../database/powerbi/airsense-analytics-report.html) and its [synthetic CSV dataset](../../database/powerbi/airsense-synthetic-readings.csv) are now included; they are descriptive examples only, not a Power BI report or live integration. The team supplied [https://airsense-85qa.onrender.com/](https://airsense-85qa.onrender.com/), but a check of the page and `/api/health` returned HTTP 503 via the web checker and direct requests timed out; operational availability is not verified. No Azure resource screenshots, physical-sensor validation, or role-specific demo credentials were found during this audit. GitHub Actions push run [42848360170](https://github.com/asvibes/AirSense/actions/runs/42848360170) and pull-request run [42848374302](https://github.com/asvibes/AirSense/actions/runs/42848374302) both passed all three CI jobs on commit `0fe75da`, including PostgreSQL tests and migrations.

The local Python suite result is recorded in [document 10](10_test_and_submission_evidence.md). The successful CI runs validate the test suite and migrations on the CI PostgreSQL service, but do not establish browser end-to-end behavior, Azure/cloud integration, production readiness, or the correctness of readings from physical sensors.

## Academic-use note

Student names, roll numbers, institution, supervisor, semester, and institutional formatting requirements were not present in the inspected repository. Add those details only from verified institutional records. The project report cites the repository and official technology documentation; no project-specific peer-reviewed literature review was present, so the team must add course-required scholarly references if required by the rubric.
