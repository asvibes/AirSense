# AirSense final college submission checklist

This checklist is a handoff for the project team. Boxes are intentionally unchecked; this document does not assert that the remaining evidence or approvals have been obtained. Follow the college rubric and template where they differ.

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

- [ ] Confirm whether the college requires another fresh test run on the final submitted checkout; the 10 November 2026 run is recorded with its command, result, duration, and warnings, and includes pre-existing staged changes.
- [ ] Run the JavaScript trend/source-average tests in an environment with Node.js; they were not executable in the current environment.
- [ ] Add a coverage percentage only after running coverage instrumentation; no percentage has been measured.
- [x] Clearly state that the Python test result was collected from a working tree with pre-existing staged changes and does not represent only committed HEAD `4b79836`.
- [ ] Add deployment, Azure, Power BI, PostgreSQL, email-provider, or hardware evidence only if the team has actually produced and verified it.
- [ ] Confirm the Power BI artifact and any resource screenshots are genuine, readable, and appropriately redacted before claiming them complete.
- [ ] Remove or retain every placeholder intentionally; do not submit accidental `[Insert ...]` fields or empty screenshot slots as completed content.

## Final package review

- [ ] Open the final Markdown/PDF export and check page breaks, table wrapping, figure sizing, captions, and link behavior.
- [x] Verify all local links and referenced files resolve in the current package; recheck after any later edits or file moves.
- [x] Confirm the current branch is `divija`; recheck the final package state before submission.
- [x] Preserve the team's existing staged and unstaged changes; no pre-existing changes were staged, unstaged, or overwritten during this documentation pass.
- [ ] Obtain any required guide/department approval before final submission.
