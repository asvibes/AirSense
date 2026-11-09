(function (root, factory) {
  const createLiveUpdateScheduler = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = createLiveUpdateScheduler;
  } else {
    root.createLiveUpdateScheduler = createLiveUpdateScheduler;
  }
})(typeof globalThis === "undefined" ? window : globalThis, function () {
  "use strict";

  return function createLiveUpdateScheduler(options = {}) {
    const refresh = options.refresh;
    const intervalMs = options.intervalMs || 20000;
    const shouldRun = options.shouldRun || (() => true);
    const onError = options.onError || (() => {});
    const schedule = options.setInterval || globalThis.setInterval.bind(globalThis);
    const cancel = options.clearInterval || globalThis.clearInterval.bind(globalThis);
    if (typeof refresh !== "function") {
      throw new TypeError("A dashboard refresh function is required.");
    }
    let timer = null;
    let inFlight = false;

    async function refreshOnce() {
      if (timer === null || inFlight || !shouldRun()) return false;
      inFlight = true;
      try {
        await refresh();
        return true;
      } catch (error) {
        onError(error);
        return false;
      } finally {
        inFlight = false;
      }
    }

    return {
      start() {
        if (timer !== null) return;
        timer = schedule(refreshOnce, intervalMs);
      },
      stop() {
        if (timer === null) return;
        cancel(timer);
        timer = null;
      },
      refreshNow: refreshOnce,
      get isRunning() {
        return timer !== null;
      },
      get isRefreshing() {
        return inFlight;
      }
    };
  };
});
