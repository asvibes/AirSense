# DALTON dataset and replay notes

## Status and workflow

The Demo Lab supports both synthetic scenarios and replay of user-provided processed DALTON CSV files. DALTON samples are validated and sent through the same server-side ingestion and alert pipeline as simulator readings. Imported readings use the `dataset` source and are labeled as recorded DALTON data in the dashboard.

The repository does not bundle DALTON data. Obtain a permitted processed CSV from the [DALTON dataset repository](https://github.com/prasenjit52282/dalton-dataset), then upload it from the Demo Lab. CSV-delimited `.txt` files are supported too. The current request upload limit is 16 MB, and a replay imports up to 1,000 valid CO₂ samples.

Expected columns:

- `ts`: source timestamp; values without a timezone are interpreted as UTC.
- `CO2`: CO₂ concentration in ppm.
- `Valid_CO2`: validity flag; only valid rows are imported.
- `Loc` and other DALTON columns may be present but are not required for the reading mapping.

Rows with missing or malformed timestamps, nonpositive CO₂ values (including zero sentinels), or invalid `Valid_CO2` flags are skipped. Rows are replayed chronologically. By default, timestamps are shifted together so the newest sample is current while sample spacing is preserved. Uncheck timestamp shifting to preserve source times.

## Data handling

- Confirm the dataset's provenance, licence/terms, and permitted use before importing.
- Do not commit restricted or personal dataset files. Use the small synthetic CSV fixtures in automated tests.
- Imported values are recorded data, not live physical measurements; the dashboard labels them accordingly.
- `tools/dalton_prep.py` previews payloads locally and does not ingest them into the app.
