# Reading validation

AirSense applies broad engineering sanity bounds to supported metrics before
they reach persistence or alert evaluation. These are data-quality bounds, not
health, regulatory, or safety thresholds:

| Metric | Normalized range |
|---|---:|
| CO2 | 0-100,000 ppm |
| PM1, PM2.5, PM10 | 0-1,000,000 ug/m3 |
| Temperature | -100 to 100 C |
| Humidity | 0-100 % |
| CO, NO2 | 0-100,000 ppm |
| VOC, ethanol | 0-1,000,000 ppb |

Device readings older than `AIRSENSE_MAX_LIVE_READING_AGE_SECONDS` are
rejected; the default is 24 hours. Historical dataset replay is not subject to
that live-device age limit, so authorized replay can preserve original
timestamps. Future timestamps remain subject to the existing future-skew
limit.
