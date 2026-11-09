(function (root, factory) {
  const roomTrends = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = roomTrends;
  } else {
    root.AirSenseRoomTrends = roomTrends;
  }
})(typeof globalThis === "object" ? globalThis : this, function () {
  "use strict";

  const WINDOW_MS = 60 * 60 * 1000;
  const MAX_STALENESS_MS = 30 * 60 * 1000;
  const MIN_SPAN_MS = 15 * 60 * 1000;
  const MAX_GAP_MS = 20 * 60 * 1000;
  const MIN_SAMPLES = 4;
  const ABSOLUTE_CHANGE = {
    CO2: 50,
    TEMPERATURE: 0.3,
    temperature: 0.3,
    HUMIDITY: 2,
    humidity: 2
  };

  function thresholdFor(metric, reference) {
    if (Object.hasOwn(ABSOLUTE_CHANGE, metric)) return ABSOLUTE_CHANGE[metric];
    return Math.max(Math.abs(reference) * 0.02, 0.01);
  }

  function trendForMetric(samples, metric, now = Date.now()) {
    if (!Array.isArray(samples) || typeof metric !== "string") return null;
    const nowMs = now instanceof Date ? now.getTime() : Number(now);
    if (!Number.isFinite(nowMs)) return null;

    const valid = samples
      .filter(sample => sample && sample.metric === metric && sample.value !== null && sample.value !== "")
      .map(sample => ({
        value: Number(sample.value),
        time: Date.parse(sample.measured_at)
      }))
      .filter(sample => Number.isFinite(sample.value)
        && Number.isFinite(sample.time)
        && sample.time <= nowMs
        && sample.time >= nowMs - WINDOW_MS)
      .sort((left, right) => left.time - right.time);

    const unique = valid.filter((sample, index) => index === 0 || sample.time !== valid[index - 1].time);
    if (unique.length < MIN_SAMPLES) return null;

    const firstTime = unique[0].time;
    const lastTime = unique[unique.length - 1].time;
    if (nowMs - lastTime > MAX_STALENESS_MS || lastTime - firstTime < MIN_SPAN_MS) return null;
    for (let index = 1; index < unique.length; index += 1) {
      if (unique[index].time - unique[index - 1].time > MAX_GAP_MS) return null;
    }

    const earlierAverage = (unique[0].value + unique[1].value) / 2;
    const recentAverage = (unique[unique.length - 2].value + unique[unique.length - 1].value) / 2;
    const difference = recentAverage - earlierAverage;
    const threshold = thresholdFor(metric, earlierAverage);
    if (Math.abs(difference) <= threshold) {
      return { direction: "stable", label: "Stable", symbol: "↔", ariaLabel: "Trend: stable" };
    }
    if (difference > 0) {
      return { direction: "up", label: "Increasing", symbol: "↑", ariaLabel: "Trend: increasing" };
    }
    return { direction: "down", label: "Decreasing", symbol: "↓", ariaLabel: "Trend: decreasing" };
  }

  return { trendForMetric };
});
