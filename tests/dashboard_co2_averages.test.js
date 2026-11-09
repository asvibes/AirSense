const test = require("node:test");
const assert = require("node:assert/strict");
const { averageBySource } = require("../app/static/js/co2-averages.js");

const NOW = Date.parse("2026-11-09T10:00:00Z");
function reading(value, source = "device", minutesAgo = 5, room = "room-1", metric = "CO2") {
  return {
    metric,
    value,
    source,
    room_id: room,
    measured_at: new Date(NOW - minutesAgo * 60 * 1000).toISOString()
  };
}

test("computes the correct average from valid readings of the same source", () => {
  const groups = averageBySource([
    reading(600, "device", 10, "room-1"),
    reading(800, "device", 5, "room-2")
  ], { now: NOW });
  assert.deepEqual(groups, [{ source: "device", count: 2, average: 700 }]);
});

test("never mixes readings from different sources", () => {
  const groups = averageBySource([
    reading(600, "device", 10),
    reading(800, "device", 5, "room-2"),
    reading(1500, "dataset", 4, "room-3"),
    reading(1700, "dataset", 3, "room-4"),
    reading(3000, "simulated", 2, "room-5")
  ], { now: NOW });
  assert.deepEqual(groups, [
    { source: "dataset", count: 2, average: 1600 },
    { source: "device", count: 2, average: 700 },
    { source: "simulated", count: 1, average: 3000 }
  ]);
});

test("excludes missing, non-numeric, non-finite, and wrong-measurement values", () => {
  const groups = averageBySource([
    reading(null),
    reading(""),
    reading("not a number"),
    reading(Infinity),
    reading(true),
    reading(-1),
    reading(100001),
    { ...reading(900), source: "" },
    { ...reading(1200), metric: "HUMIDITY" }
  ], { now: NOW });
  assert.deepEqual(groups, []);
});

test("excludes stale readings instead of letting them skew a current average", () => {
  const groups = averageBySource([
    reading(700, "device", 5),
    reading(2500, "device", 90, "room-2")
  ], { now: NOW });
  assert.deepEqual(groups, [{ source: "device", count: 1, average: 700 }]);
});

test("handles absent input and ignores future or malformed timestamps", () => {
  assert.deepEqual(averageBySource(undefined, { now: NOW }), []);
  const groups = averageBySource([
    reading(800, "device", -10),
    { ...reading(900), measured_at: "not a date" }
  ], { now: NOW });
  assert.deepEqual(groups, []);
});

test("supports source-separated historical averages inside the selected date range", () => {
  const inRange = [reading(400, "dataset", 1440), reading(600, "dataset", 1200)];
  const groups = averageBySource(inRange, { now: NOW, maxAgeMs: null });
  assert.deepEqual(groups, [{ source: "dataset", count: 2, average: 500 }]);
});
