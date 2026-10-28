# DALTON dataset and replay notes

## Status

DALTON import/replay is not connected in the current prototype. The frontend preview uses browser-local illustrative sample data and does not consume DALTON records. The backend accepts its documented reading sources, but the dataset adapter and import workflow are not implemented. See the [README](../Readme.md) and [implementation status](./PRD.md).

## Planned integration boundary

If DALTON data is used for development or evaluation:

- Confirm the dataset's provenance, licence/terms, schema, units, timestamp conventions, and permitted use before importing.
- Keep the source dataset unchanged; perform mapping/cleaning in a reproducible preparation step.
- Map fields to the canonical reading shape: source identifier, room/sensor mapping, metric, value, unit, measurement timestamp, receipt/import timestamp, and source label.
- Validate ranges, missing values, timezone interpretation, duplicates, and ordering before ingestion.
- Preserve provenance so imported/replayed records are distinguishable from live device readings and synthetic demo values.
- Do not imply a replayed value is a real-time physical measurement.

## Replay behavior to define before implementation

- Input file format and schema version.
- Mapping from dataset subjects/locations to demo rooms/sensors without exposing personal data.
- Whether source timestamps are preserved or shifted during replay.
- Handling for malformed rows, duplicates, and unsupported metrics.
- Replay speed, pause/reset behavior, and deterministic test fixtures.
- Clear UI/report label for replayed data, including an obvious demo indication.

## Privacy and reproducibility

Do not commit restricted or personal datasets. Keep credentials and private source data outside the repository. Document any transformation scripts, mapping configuration, and test fixtures; use small synthetic fixtures for automated tests. The placeholder `tools/dalton_prep.py` and mapping file are not evidence that a functioning import pipeline exists.