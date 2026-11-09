const test = require("node:test");
const assert = require("node:assert/strict");
const createLiveUpdateScheduler = require("../app/static/js/live-update-scheduler.js");

function fakeClock() {
  let callback = null;
  let interval = null;
  let cleared = null;
  return {
    setInterval(fn, delay) {
      callback = fn;
      interval = delay;
      return "timer-1";
    },
    clearInterval(id) {
      cleared = id;
    },
    tick() {
      return callback();
    },
    get interval() {
      return interval;
    },
    get cleared() {
      return cleared;
    }
  };
}

test("starts only one timer at the configured 20-second dashboard interval", () => {
  const clock = fakeClock();
  const scheduler = createLiveUpdateScheduler({
    refresh: async () => {},
    intervalMs: 20000,
    setInterval: clock.setInterval,
    clearInterval: clock.clearInterval
  });

  scheduler.start();
  scheduler.start();

  assert.equal(clock.interval, 20000);
  assert.equal(scheduler.isRunning, true);
  scheduler.stop();
  assert.equal(clock.cleared, "timer-1");
  assert.equal(scheduler.isRunning, false);
});

test("does not start overlapping refresh requests", async () => {
  const clock = fakeClock();
  let calls = 0;
  let finish;
  const scheduler = createLiveUpdateScheduler({
    refresh: () => {
      calls += 1;
      return new Promise(resolve => { finish = resolve; });
    },
    setInterval: clock.setInterval,
    clearInterval: clock.clearInterval
  });
  scheduler.start();

  const first = clock.tick();
  const second = await clock.tick();
  assert.equal(calls, 1);
  assert.equal(second, false);
  assert.equal(scheduler.isRefreshing, true);
  finish();
  assert.equal(await first, true);
  assert.equal(scheduler.isRefreshing, false);
});

test("handles failed requests and recovers on the next polling cycle", async () => {
  const clock = fakeClock();
  let calls = 0;
  const errors = [];
  const scheduler = createLiveUpdateScheduler({
    refresh: async () => {
      calls += 1;
      if (calls === 1) throw new Error("offline");
    },
    onError: error => errors.push(error.message),
    setInterval: clock.setInterval,
    clearInterval: clock.clearInterval
  });
  scheduler.start();

  assert.equal(await clock.tick(), false);
  assert.deepEqual(errors, ["offline"]);
  assert.equal(await clock.tick(), true);
  assert.equal(calls, 2);
});

test("does not poll while the page is hidden and can restart after visibility returns", async () => {
  const clock = fakeClock();
  let visible = false;
  let calls = 0;
  const scheduler = createLiveUpdateScheduler({
    refresh: async () => { calls += 1; },
    shouldRun: () => visible,
    setInterval: clock.setInterval,
    clearInterval: clock.clearInterval
  });
  scheduler.start();

  assert.equal(await clock.tick(), false);
  visible = true;
  assert.equal(await scheduler.refreshNow(), true);
  scheduler.stop();
  assert.equal(calls, 1);
});
