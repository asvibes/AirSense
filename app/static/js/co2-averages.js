(function (root, factory) {
  const co2Averages = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = co2Averages;
  } else {
    root.AirSenseCO2Averages = co2Averages;
  }
})(typeof globalThis === "object" ? globalThis : this, function () {
  "use strict";

  const DEFAULT_MAX_AGE_MS = 30 * 60 * 1000;

  function averageBySource(readings, {
    metric = "CO2",
    now = Date.now(),
    maxAgeMs = DEFAULT_MAX_AGE_MS
  } = {}) {
    if (!Array.isArray(readings)) return [];
    const nowMs = now instanceof Date ? now.getTime() : Number(now);
    if (!Number.isFinite(nowMs)) return [];

    const groups = new Map();
    readings.forEach(reading => {
      if (!reading || reading.metric !== metric || reading.value === null || reading.value === "") return;
      if (typeof reading.source !== "string" || !reading.source.trim()) return;
      if (typeof reading.value !== "number" && typeof reading.value !== "string") return;
      const value = Number(reading.value);
      const measuredAt = Date.parse(reading.measured_at);
      if (!Number.isFinite(value) || !Number.isFinite(measuredAt) || measuredAt > nowMs) return;
      if (metric === "CO2" && (value < 0 || value > 100000)) return;
      if (maxAgeMs !== null && nowMs - measuredAt > maxAgeMs) return;

      const group = groups.get(reading.source) || { source: reading.source, total: 0, count: 0 };
      group.total += value;
      group.count += 1;
      groups.set(reading.source, group);
    });

    return Array.from(groups.values())
      .map(group => ({
        source: group.source,
        count: group.count,
        average: group.total / group.count
      }))
      .sort((left, right) => left.source.localeCompare(right.source));
  }

  return { averageBySource, DEFAULT_MAX_AGE_MS };
});
