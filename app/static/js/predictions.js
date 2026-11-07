(() => {
  "use strict";
  const config = JSON.parse(document.getElementById("predictions-config").textContent);
  const $ = selector => document.querySelector(selector);
  const esc = value => String(value ?? "").replace(/[&<>"']/g, char => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  })[char]);
  const colors = { actual: "#83cdb8", forecast: "#83c8d0" };
  let rooms = [];
  let sensors = [];
  let modelResults = [];
  let activeUnit = "";
  let choiceRequestId = 0;
  let forecastRequestId = 0;

  async function api(path) {
    const response = await fetch(path, { credentials: "same-origin" });
    const payload = (response.headers.get("content-type") || "").includes("application/json")
      ? await response.json() : null;
    if (response.status === 401) {
      window.location.assign(`/login?next=${encodeURIComponent(window.location.pathname)}`);
      throw new Error("Your session expired. Sign in again.");
    }
    if (!response.ok) throw new Error(payload?.error || `Request failed (${response.status}).`);
    return payload;
  }

  function homePath() {
    return `/api/homes/${encodeURIComponent($("#household").value)}`;
  }

  function setStatus(title, message, state = "unavailable") {
    const status = $("#forecast-status");
    status.dataset.state = state;
    status.innerHTML = `<strong>${esc(title)}</strong>${esc(message)}`;
  }

  function updateOptions(select, options, emptyLabel) {
    const current = select.value;
    select.innerHTML = `<option value="">${esc(emptyLabel)}</option>` + options.map(option =>
      `<option value="${esc(option.value)}">${esc(option.label)}</option>`
    ).join("");
    if (options.some(option => option.value === current)) select.value = current;
  }

  function updateHorizonOptions(metricCode) {
    const select = $("#horizon");
    const matching = modelResults.filter(model =>
      model.available && (!metricCode || model.metric === metricCode)
    );
    if (
      matching.length > 1
      && (!$("#room").value || !$("#sensor").value)
    ) {
      select.innerHTML = '<option value="">Select a room and sensor first</option>';
      select.disabled = true;
      return;
    }
    const horizons = [
      { minutes: 60, label: "Next 1 hour" },
      { minutes: 360, label: "Next 6 hours" },
      { minutes: 1440, label: "Next 24 hours" }
    ].filter(option =>
      matching.some(model => Number(model.tested_horizon_seconds) >= option.minutes * 60)
    );
    select.innerHTML = horizons.length
      ? horizons.map(option => `<option value="${option.minutes / 60}">${option.label}</option>`).join("")
      : '<option value="">No validated horizon</option>';
    select.disabled = !horizons.length;
  }

  async function loadChoices(requestId) {
    const home = homePath();
    const [roomData, sensorData] = await Promise.all([
      api(`${home}/rooms`),
      api(`${home}/sensors`)
    ]);
    if (requestId !== choiceRequestId) return false;
    rooms = roomData.rooms || [];
    sensors = sensorData.sensors || [];
    updateOptions($("#room"), rooms.map(room => ({ value: room.id, label: room.name })), "All rooms");
    updateOptions($("#sensor"), sensors
      .filter(sensor => !$("#room").value || sensor.room_id === $("#room").value)
      .map(sensor => ({ value: sensor.id, label: `${sensor.name} · ${sensor.room}` })), "All sensors");
    const roomId = encodeURIComponent($("#room").value);
    const sensorId = encodeURIComponent($("#sensor").value);
    const [optionsData, modelData] = await Promise.all([
      api(`${home}/history/options?room_id=${roomId}&sensor_id=${sensorId}`),
      api(`${home}/predictions?room_id=${roomId}&sensor_id=${sensorId}`)
    ]);
    if (requestId !== choiceRequestId) return false;
    modelResults = modelData.models || [];
    updateOptions($("#metric"), optionsData.metrics.map(metric => ({
      value: metric.code,
      label: `${metric.name} (${metric.code})`
    })), optionsData.metrics.length ? "Choose available parameter" : "No stored parameters");

    if (!$("#metric").value && optionsData.metrics.length) {
      const forecastMetric = modelResults.find(model =>
        model.available && optionsData.metrics.some(metric => metric.code === model.metric)
      )?.metric;
      $("#metric").value = forecastMetric || optionsData.metrics[0].code;
    }
    updateHorizonOptions($("#metric").value);
    if (!optionsData.metrics.length) {
      setStatus("No stored parameters", "No actual sensor readings are available in this household, so there is nothing to evaluate or forecast.");
      updatePerformance(null);
      renderChart([], []);
      renderRows([], []);
      return true;
    }
    if (!modelResults.length) {
      setStatus("Coming Soon · no validated model", "There are no saved evaluation results for this selection. Forecasts are not generated while the only available data is insufficient or fails to beat the persistence baseline.");
    } else {
      const availableCount = modelResults.filter(model => model.available).length;
      setStatus(
        availableCount ? "Validated model results available" : "No supported forecasts yet",
        availableCount
          ? `${availableCount} parameter series passed chronological holdout evaluation. Select a specific room, sensor, and parameter.`
          : modelResults[0].reason || "Stored data has not produced a model that beats the persistence baseline."
      );
    }
    return true;
  }

  function updatePerformance(metrics) {
    const trend = metrics?.trend;
    const baseline = metrics?.persistence;
    const format = value => Number.isFinite(Number(value)) ? Number(value).toPrecision(4) : "Not available";
    $("#metric-mae").textContent = trend ? format(trend.mae) : "—";
    $("#metric-rmse").textContent = trend ? format(trend.rmse) : "—";
    $("#metric-r2").textContent = trend && trend.r2 !== null ? format(trend.r2) : "Not available";
    if (!trend || !baseline) {
      $("#performance-chart").innerHTML = "";
      return;
    }
    const maximum = Math.max(Number(trend.mae), Number(baseline.mae), Number.EPSILON);
    $("#performance-chart").innerHTML = [
      ["Trend model MAE", Number(trend.mae)],
      ["Persistence MAE", Number(baseline.mae)]
    ].map(([label, value]) => `<div class="performance-row"><span>${label}</span><div class="performance-track"><i style="width:${Math.max(1, value / maximum * 100)}%"></i></div><b>${format(value)}</b></div>`).join("");
  }

  function renderChart(actual, forecast) {
    const points = [
      ...actual.map(item => ({ ...item, time: Date.parse(item.measured_at), kind: "actual" })),
      ...forecast.map(item => ({ ...item, time: Date.parse(item.measured_at), kind: "forecast" }))
    ].filter(item => Number.isFinite(item.time) && Number.isFinite(Number(item.value)));
    if (!points.length) {
      $("#chart-wrap").innerHTML = '<div class="status">No actual readings or validated forecast values are available for this selection.</div>';
      return;
    }
    const width = 900, height = 300, left = 64, right = 22, top = 18, bottom = 40;
    const minTime = Math.min(...points.map(item => item.time));
    const maxTime = Math.max(...points.map(item => item.time));
    const span = Math.max(1, maxTime - minTime);
    const values = points.flatMap(item => [Number(item.lower ?? item.value), Number(item.upper ?? item.value)]);
    let minValue = Math.min(...values), maxValue = Math.max(...values);
    if (minValue === maxValue) { minValue -= 1; maxValue += 1; }
    const x = time => left + (time - minTime) / span * (width - left - right);
    const y = value => top + (1 - (value - minValue) / (maxValue - minValue)) * (height - top - bottom);
    const grid = [0, .5, 1].map(fraction => {
      const value = minValue + fraction * (maxValue - minValue);
      const coordinate = y(value);
      return `<line class="chart-grid" x1="${left}" y1="${coordinate}" x2="${width - right}" y2="${coordinate}"/><text class="chart-label" x="${left - 8}" y="${coordinate + 3}" text-anchor="end">${esc(value.toPrecision(4))}</text>`;
    }).join("");
    const actualDots = actual.map(item => {
      const time = Date.parse(item.measured_at);
      const value = Number(item.value);
      if (!Number.isFinite(time) || !Number.isFinite(value)) return "";
      return `<circle class="actual-dot" cx="${x(time)}" cy="${y(value)}" r="3.5"><title>Actual ${esc(item.value)} ${esc(item.unit)} at ${esc(item.measured_at)} · ${esc(item.source)}</title></circle>`;
    }).join("");
    const forecastLine = forecast.map((item, index) =>
      `${index ? "L" : "M"}${x(Date.parse(item.measured_at)).toFixed(2)},${y(Number(item.value)).toFixed(2)}`
    ).join(" ");
    const upper = forecast.map(item => `${x(Date.parse(item.measured_at)).toFixed(2)},${y(Number(item.upper)).toFixed(2)}`);
    const lower = [...forecast].reverse().map(item => `${x(Date.parse(item.measured_at)).toFixed(2)},${y(Number(item.lower)).toFixed(2)}`);
    const band = forecast.length ? `<polygon class="interval-band" points="${[...upper, ...lower].join(" ")}"/>` : "";
    $("#chart-wrap").innerHTML = `<svg class="prediction-chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="Actual readings and validated sensor forecast">${grid}${band}${actualDots}${forecast.length ? `<path class="forecast-line" d="${forecastLine}"/>` : ""}<text class="chart-label" x="${left}" y="${height - 10}">${esc(new Date(minTime).toLocaleString())}</text><text class="chart-label" x="${width - right}" y="${height - 10}" text-anchor="end">${esc(new Date(maxTime).toLocaleString())}</text></svg>`;
  }

  function renderRows(actual, forecast) {
    const rows = [
      ...actual.map(item => ({ ...item, kind: "Actual", interval: "—" })),
      ...forecast.map(item => ({ ...item, kind: "Forecast", interval: `${Number(item.lower).toPrecision(4)} – ${Number(item.upper).toPrecision(4)}`, source: "Model estimate" }))
    ].sort((a, b) => Date.parse(a.measured_at) - Date.parse(b.measured_at));
    $("#forecast-rows").innerHTML = rows.map(item =>
      `<tr><td>${esc(item.kind)}</td><td><time datetime="${esc(item.measured_at)}">${esc(new Date(item.measured_at).toLocaleString())}</time></td><td class="numeric">${esc(item.value)}</td><td>${esc(item.unit || activeUnit)}${item.kind === "Forecast" ? ` · 90% interval ${esc(item.interval)}` : ""}</td><td>${esc(item.source)}</td></tr>`
    ).join("") || '<tr><td class="table-empty" colspan="5">No actual values or validated forecast results.</td></tr>';
  }

  async function loadForecast() {
    const requestId = ++forecastRequestId;
    if (!$("#metric").value) {
      setStatus("Choose a parameter", "The selector lists only parameters with stored readings for the chosen household, room, and sensor.");
      return;
    }
    try {
      const params = new URLSearchParams({
        room_id: $("#room").value,
        sensor_id: $("#sensor").value,
        metric: $("#metric").value,
        horizon_minutes: String((Number($("#horizon").value) || 1) * 60)
      });
      const result = await api(`${homePath()}/predictions?${params}`);
      if (requestId !== forecastRequestId) return;
      updatePerformance(result.metrics);
      if (!result.available) {
        activeUnit = result.actual?.[0]?.unit || "";
        setStatus("Forecast unavailable", result.reason || "No validated forecast is available for this selection.");
        renderChart(result.actual || [], []);
        renderRows(result.actual || [], []);
        return;
      }
      const label = $("#metric").selectedOptions[0]?.textContent || result.metric;
      activeUnit = result.actual[0]?.unit || "";
      const horizonHours = result.horizon_seconds / 3600;
      setStatus(
        "Validated forecast",
        `${label} · next ${horizonHours} hour${horizonHours === 1 ? "" : "s"} · ${result.sample_count} real training readings. Test metrics use a later chronological holdout. Forecasts are estimates, not measurements.`,
        "available"
      );
      $("#chart-hint").textContent = `${result.actual.length} actual stored values and ${result.forecast.length} forecast points. Shaded area is a holdout-residual interval; no interpolated actual readings are added.`;
      renderChart(result.actual, result.forecast);
      renderRows(result.actual, result.forecast);
    } catch (error) {
      setStatus("Unable to load forecast", error.message, "error");
    }
  }

  async function reloadChoices(loadModel = true) {
    const requestId = ++choiceRequestId;
    forecastRequestId += 1;
    try {
      const loaded = await loadChoices(requestId);
      if (loaded && requestId === choiceRequestId && loadModel && $("#metric").value) {
        await loadForecast();
      }
    } catch (error) {
      if (requestId === choiceRequestId) setStatus("Unable to load available data", error.message, "error");
    }
  }

  $("#household").addEventListener("change", async () => {
    const url = new URL(window.location.href);
    url.searchParams.set("home_id", $("#household").value);
    window.history.replaceState(null, "", url);
    await reloadChoices();
  });
  $("#room").addEventListener("change", async () => {
    await reloadChoices();
  });
  $("#sensor").addEventListener("change", async () => {
    await reloadChoices();
  });
  $("#metric").addEventListener("change", async () => {
    updateHorizonOptions($("#metric").value);
    await loadForecast();
  });
  $("#horizon").addEventListener("change", loadForecast);
  $("#theme-toggle").addEventListener("click", () => {
    const next = document.documentElement.dataset.theme === "night" ? "day" : "night";
    document.documentElement.dataset.theme = next;
    $("#theme-toggle").setAttribute("aria-label", `Switch to ${next === "night" ? "day" : "night"} mode`);
    try { localStorage.setItem("airsense-theme", next); } catch { /* The theme remains available for this page. */ }
  });
  try {
    const savedTheme = localStorage.getItem("airsense-theme");
    if (savedTheme === "day" || savedTheme === "night") document.documentElement.dataset.theme = savedTheme;
  } catch { /* The default theme remains available for this page. */ }
  reloadChoices();
})();
