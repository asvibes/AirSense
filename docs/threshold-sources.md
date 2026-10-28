# Thresholds and source documentation

## Purpose

AirSense threshold values are configurable rule inputs, not universal medical safety boundaries. A dashboard status such as Normal, Elevated, or High describes how a measurement compares with the configured project rule; it is not a diagnosis, a complete indoor-air-quality score, or a guarantee of safety.

## Threshold policy requirements

For each configured threshold, record:

- Metric and unit (for example, CO2 in ppm).
- Numeric value and comparison operator.
- Room/facility scope and effective date.
- Whether a duration or consecutive-sample condition is required.
- Source organization/document, exact title, publication/version date, URL, and date accessed.
- Rationale for applying that guidance to the project and any limitations.
- Person/role that approved or last changed the policy.

Do not present an uncited default as published guidance. If a credible source is not selected and reviewed, label the value illustrative/demo-only and avoid claims that it defines a safe/unsafe boundary.

## Evaluation behavior

- Use documented inclusive/exclusive comparisons consistently at boundary values.
- Apply room-specific policy effective at the measurement time when policy history is available.
- For duration-based rules, require valid consecutive/time-window observations and define how missing readings and long gaps reset evaluation.
- Snapshot the threshold/policy version or value on alert creation to preserve context after subsequent policy edits.
- Prevent repeated qualifying readings from creating uncontrolled duplicate open alerts.
- Show the measured value, unit, threshold, timestamp, source, and current sensor freshness with the status.

## Current implementation

Current demo defaults are illustrative configuration values and are not represented as published health guidance. The existing alert lifecycle supports configurable policy values, duration rules, duplicate prevention, and alert wording; see [implementation status](./PRD.md) and [alert lifecycle](./alert-lifecycle.md). The backend does not yet persist citations for the illustrative defaults. Do not invent citations or imply the values have been validated by a health authority.