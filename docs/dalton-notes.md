# DALTON dataset and replay notes

## Status and workflow

The Demo Lab supports both synthetic scenarios and replay of user-provided environmental CSV files, including processed DALTON exports. Simulator readings use the live alert pipeline. Dataset readings are stored with their original timestamps (unless shifting is requested), labeled as recorded data, and are not evaluated as live alerts.

The repository does not bundle DALTON data. Obtain a permitted processed CSV from the [DALTON dataset repository](https://github.com/prasenjit52282/dalton-dataset), then upload it from the Demo Lab. CSV-delimited `.txt` files are supported too. The current request upload limit is 16 MB, and a replay examines up to 1,000 rows.

The CSV needs a timestamp column (`ts`, `timestamp`, `datetime`, or a recognized alias) and one or more measurements. CO₂ is optional. Recognized measurements include CO₂, PM1, PM2.5, PM10, temperature, humidity, CO, NO₂, VOC, and ethanol. Common aliases and supported units are normalized; ambiguous/unsupported columns are reported for review. Unitless measurements are imported only for the documented DALTON schema; other unitless recognized columns are flagged for review rather than assigned a presumed unit. Other measurements can be imported with a supported explicit unit.

DALTON validity fields such as `Valid_CO2` are honored when present. Its documented `ts` format `YYYY/MM/DD HH:MM:SS` is supported; timestamps without a timezone are interpreted as UTC. Duplicate measurements for a metric at the same timestamp are skipped and reported.

The DALTON header mapping and units follow the [dataset's published column definitions](https://github.com/prasenjit52282/dalton-dataset#data-description): `T` is temperature in °C, `H` humidity in %, `PMS1`/`PMS2_5`/`PMS10` are particulate matter in µg/m³, `CO2` and `CO` are ppm, `NO2`/`VoC`/`C2H5OH` are ppb. `C2H5OH` is stored as the `ETHANOL` metric. These unit defaults are applied only when the CSV matches the DALTON schema; other unitless files are reported for review instead of being assigned guessed units.

Rows with missing or malformed timestamps, invalid/non-finite measurement values, or false validity flags are skipped. By default, timestamps are preserved; optionally shift all timestamps together so the newest sample is current while sample spacing is preserved.

## Data handling

- Confirm the dataset's provenance, licence/terms, and permitted use before importing.
- Do not commit restricted or personal dataset files. Use the small synthetic CSV fixtures in automated tests.
- Imported values are historical dataset data, not live physical measurements; the dashboard labels them accordingly.
- Only simulator and device readings use configured alert policies. Dataset imports do not create or clear alerts.
- `tools/dalton_prep.py` previews payloads locally and does not ingest them into the app.
