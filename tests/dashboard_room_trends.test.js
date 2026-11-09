const test = require("node:test");
const assert = require("node:assert/strict");
const { trendForMetric } = require("../app/static/js/room-trends.js");

const NOW = Date.parse("2026-11-09T10:00:00Z");
const minute = 60 * 1000;
function samples(values, metric = "CO2", offsets = [30, 20, 10, 0]) {
  return values.map((value, index) => ({
    metric,
    value,
    measured_at: new Date(NOW - offsets[index] * minute).toISOString()
  }));
}

test("reports an upward trend for recent sustained increases", () => {
  assert.equal(trendForMetric(samples([600, 640, 700, 760]), "CO2", NOW).direction, "up");
});

test("reports a downward trend for recent sustained decreases", () => {
  assert.equal(trendForMetric(samples([900, 850, 780, 720]), "CO2", NOW).direction, "down");
});

test("reports stable when the change stays within the metric noise threshold", () => {
  assert.equal(trendForMetric(samples([600, 610, 625, 630]), "CO2", NOW).direction, "stable");
});

test("returns no trend when there are no readings", () => {
  assert.equal(trendForMetric([], "CO2", NOW), null);
  assert.equal(trendForMetric(null, "CO2", NOW), null);
});

test("returns no trend when history has too few samples or too short a span", () => {
  assert.equal(trendForMetric(samples([600, 700, 800]).slice(0, 3), "CO2", NOW), null);
  assert.equal(trendForMetric(samples([600, 700, 800, 900], "CO2", [10, 7, 3, 0]), "CO2", NOW), null);
});

test("returns no trend when the newest reading is stale", () => {
  assert.equal(trendForMetric(samples([600, 700, 800, 900], "CO2", [55, 50, 45, 40]), "CO2", NOW), null);
});

test("does not infer a trend across an excessive gap in the comparison window", () => {
  assert.equal(trendForMetric(samples([600, 700, 800, 900], "CO2", [55, 45, 10, 0]), "CO2", NOW), null);
});

test("compares only samples for the requested measurement and ignores invalid values", () => {
  const input = [
    ...samples([600, 620, 630, 650]),
    ...samples([99, 1, 90, 2], "humidity"),
    { metric: "CO2", value: "not-a-number", measured_at: new Date(NOW - 5 * minute).toISOString() }
  ];
  assert.equal(trendForMetric(input, "CO2", NOW).direction, "stable");
  assert.equal(trendForMetric(input, "humidity", NOW).direction, "down");
});

test("includes a screen-reader label and an explicit arrow symbol", () => {
  const trend = trendForMetric(samples([500, 600, 700, 800]), "CO2", NOW);
  assert.equal(trend.symbol, "↑");
  assert.equal(trend.ariaLabel, "Trend: increasing");
});
