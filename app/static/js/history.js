(() => {
  "use strict";

  const config = JSON.parse(document.getElementById("history-config").textContent);
  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));
  const esc = value => String(value ?? "").replace(/[&<>"']/g, char => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  })[char]);
  const state = {
    rooms: [],
    sensors: [],
    metrics: [],
    readings: [],
    page: 0,
    pageSize: 100,
    zoom: 1,
    pan: 0,
    requestId: 0,
    optionsRequestId: 0
  };
  const colors = ["#83cdb8", "#83c8d0", "#d3ad75", "#df8f83", "#a9a2e8", "#8db8e6", "#d19bb8"];

  function setStatus(message, error = false) {
    const status = $("#page-status");
    status.textContent = message;
    status.classList.toggle("error", error);
  }

  async function api(path) {
    const response = await fetch(path, { credentials: "same-origin" });
    const type = response.headers.get("content-type") || "";
    const payload = type.includes("application/json") ? await response.json() : null;
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

  function checkedMetrics() {
    return $$("#parameters input:checked").map(input => input.value);
  }

  function setDateDefaults(days = 7) {
    const end = new Date();
    const start = new Date(end.getTime() - days * 86400000);
    const localInputValue = value => {
      const local = new Date(value.getTime() - value.getTimezoneOffset() * 60000);
      return local.toISOString().slice(0, 16);
    };
    $("#date-from").value = localInputValue(start);
    $("#date-to").value = localInputValue(end);
  }

  function toISOString(value) {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) throw new Error("Enter a valid start and end date.");
    return date.toISOString();
  }

  async function loadChoices({ preserve = true } = {}) {
    const home = $("#household").value;
    const priorMetrics = preserve ? new Set(checkedMetrics()) : new Set();
    const [roomData, sensorData] = await Promise.all([
      api(`${homePath()}/rooms`),
      api(`${homePath()}/sensors`)
    ]);
    if ($("#household").value !== home) return;
    state.rooms = roomData.rooms;
    state.sensors = sensorData.sensors;
    const roomSelect = $("#room");
    const roomValue = roomSelect.value;
    roomSelect.innerHTML = '<option value="">All rooms</option>' + state.rooms.map(room =>
      `<option value="${esc(room.id)}">${esc(room.name)}</option>`
    ).join("");
    if (state.rooms.some(room => room.id === roomValue)) roomSelect.value = roomValue;
    updateSensorOptions();
    await loadMetricOptions(priorMetrics);
  }

  function updateSensorOptions() {
    const roomId = $("#room").value;
    const sensorSelect = $("#sensor");
    const current = sensorSelect.value;
    const sensors = state.sensors.filter(sensor => !roomId || sensor.room_id === roomId);
    sensorSelect.innerHTML = '<option value="">All sensors</option>' + sensors.map(sensor =>
      `<option value="${esc(sensor.id)}">${esc(sensor.name)}${sensor.status === "revoked" ? " · Revoked" : ""}</option>`
    ).join("");
    if (sensors.some(sensor => sensor.id === current)) sensorSelect.value = current;
  }

  async function loadMetricOptions(priorMetrics = new Set()) {
    const requestId = ++state.optionsRequestId;
    const selection = `${$("#household").value}:${$("#room").value}:${$("#sensor").value}`;
    const params = new URLSearchParams();
    if ($("#room").value) params.set("room_id", $("#room").value);
    if ($("#sensor").value) params.set("sensor_id", $("#sensor").value);
    const result = await api(`${homePath()}/history/options?${params}`);
    const currentSelection = `${$("#household").value}:${$("#room").value}:${$("#sensor").value}`;
    if (requestId !== state.optionsRequestId || selection !== currentSelection) return;
    state.metrics = result.metrics;
    const wrapper = $("#parameters");
    if (!state.metrics.length) {
      wrapper.innerHTML = '<span class="empty-option">No stored parameters are available for this selection.</span>';
      return;
    }
    wrapper.innerHTML = state.metrics.map((metric, index) => {
      const checked = priorMetrics.size ? priorMetrics.has(metric.code) : true;
      return `<label class="parameter-option"><input type="checkbox" value="${esc(metric.code)}" ${checked ? "checked" : ""}><span>${esc(metric.name)} <small>(${esc(metric.code)} · ${esc(metric.unit)})</small></span></label>`;
    }).join("");
  }

  function filterParams() {
    const from = toISOString($("#date-from").value);
    const to = toISOString($("#date-to").value);
    if (new Date(from) >= new Date(to)) throw new Error("The start date must be earlier than the end date.");
    const metrics = checkedMetrics();
    if (!metrics.length) throw new Error("Select at least one available parameter.");
    const params = new URLSearchParams({ from, to, limit: "10000" });
    if ($("#room").value) params.set("room_id", $("#room").value);
    if ($("#sensor").value) params.set("sensor_id", $("#sensor").value);
    metrics.forEach(metric => params.append("metric", metric));
    return params;
  }

  async function loadReadings() {
    const requestId = ++state.requestId;
    if (!state.metrics.length) {
      state.readings = [];
      render();
      setStatus("No stored readings are available for this household, room, and sensor selection.");
      return;
    }
    let params;
    try {
      params = filterParams();
    } catch (error) {
      setStatus(error.message, true);
      return;
    }
    setStatus("Loading stored readings…");
    try {
      const result = await api(`${homePath()}/history?${params}`);
      if (requestId !== state.requestId) return;
      state.readings = result.readings;
      state.page = 0;
      state.zoom = 1;
      state.pan = 0;
      setStatus(`Loaded ${result.readings.length.toLocaleString()} stored readings${result.readings.length === 10000 ? " (maximum result limit reached)" : ""}.`);
      render();
    } catch (error) {
      if (requestId === state.requestId) setStatus(error.message, true);
    }
  }

  function numeric(value) {
    return Number(value).toLocaleString(undefined, { maximumFractionDigits: 3 });
  }

  function formatTimestamp(value, options = {}) {
    return new Intl.DateTimeFormat(undefined, {
      year: "numeric", month: "short", day: "2-digit",
      hour: "2-digit", minute: "2-digit", second: "2-digit",
      hour12: false, ...options
    }).format(new Date(value));
  }

  function groupsByMetric() {
    const groups = new Map(state.metrics.map(metric => [metric.code, []]));
    state.readings.forEach(reading => {
      if (groups.has(reading.metric)) groups.get(reading.metric).push(reading);
    });
    return groups;
  }

  function seriesGroups(readings) {
    const groups = new Map();
    readings.forEach(reading => {
      const key = `${reading.metric}:${reading.sensor_id || "unassigned"}:${reading.room_id}`;
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(reading);
    });
    for (const values of groups.values()) values.sort((a, b) => Date.parse(a.measured_at) - Date.parse(b.measured_at));
    return groups;
  }

  function median(values) {
    if (!values.length) return null;
    const sorted = [...values].sort((a, b) => a - b);
    const middle = Math.floor(sorted.length / 2);
    return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
  }

  function duration(seconds) {
    if (!Number.isFinite(seconds)) return "—";
    if (seconds < 60) return `${Math.round(seconds)} sec`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)} min ${Math.round(seconds % 60)} sec`;
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    return `${hours} hr ${minutes} min`;
  }

  function intervalData(readings) {
    const bySeries = seriesGroups(readings);
    const intervals = [];
    const perReading = new Map();
    let longestConfiguredGap = null;
    let configuredSeriesCount = 0;
    for (const series of bySeries.values()) {
      const sensor = state.sensors.find(item => item.id === series[0]?.sensor_id);
      const expectedInterval = Number(sensor?.reporting_interval_seconds);
      if (Number.isFinite(expectedInterval) && expectedInterval > 0) configuredSeriesCount += 1;
      series.forEach((reading, index) => {
        const previous = series[index - 1];
        if (!previous) return;
        const seconds = (Date.parse(reading.measured_at) - Date.parse(previous.measured_at)) / 1000;
        intervals.push(seconds);
        perReading.set(reading.id, seconds);
        if (expectedInterval > 0 && seconds > expectedInterval * 2) {
          longestConfiguredGap = Math.max(longestConfiguredGap || 0, seconds);
        }
      });
    }
    const cadence = median(intervals);
    const maximum = intervals.length ? Math.max(...intervals) : null;
    return {
      intervals,
      perReading,
      cadence,
      maximum,
      gap: longestConfiguredGap,
      configuredSeriesCount
    };
  }

  function renderSummary() {
    const interval = intervalData(state.readings);
    $("#summary-count").textContent = state.readings.length.toLocaleString();
    $("#summary-interval").textContent = interval.cadence === null ? "Not available" : duration(interval.cadence);
    $("#summary-gap").textContent = interval.gap === null
      ? (interval.configuredSeriesCount ? "None detected" : "No configured cadence")
      : duration(interval.gap);
    const summary = $("#analytics-summary");
    if (!summary) return;
    const selected = new Set(checkedMetrics());
    const groups = new Map();
    for (const reading of state.readings.filter(item => selected.has(item.metric))) {
      const key = `${reading.metric}|${reading.room_id || ""}|${reading.sensor_id || ""}`;
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(reading);
    }
    summary.innerHTML = [...groups.values()].map(readings => {
      readings.sort((a, b) => Date.parse(a.measured_at) - Date.parse(b.measured_at));
      const metric = state.metrics.find(item => item.code === readings[0].metric);
      const values = readings.map(item => Number(item.value)).filter(Number.isFinite);
      const room = state.rooms.find(item => item.id === readings[0].room_id)?.name || readings[0].room;
      const sensor = state.sensors.find(item => item.id === readings[0].sensor_id)?.name || "Unassigned sensor";
      const change = values.length > 1 ? values[values.length - 1] - values[0] : null;
      return `<tr><td>${esc(metric?.name || readings[0].metric)}</td><td>${esc(room)} / ${esc(sensor)}</td><td>${esc(numeric(Math.min(...values)))} ${esc(readings[0].unit)}</td><td>${esc(numeric(values.reduce((sum, value) => sum + value, 0) / values.length))} ${esc(readings[0].unit)}</td><td>${esc(numeric(Math.max(...values)))} ${esc(readings[0].unit)}</td><td>${change === null ? "—" : `${change > 0 ? "+" : ""}${esc(numeric(change))} ${esc(readings[0].unit)}`}</td><td>${readings.length.toLocaleString()}</td></tr>`;
    }).join("") || '<tr><td class="table-empty" colspan="7">No stored readings match these filters.</td></tr>';
  }

  function aggregatedReadings(period) {
    const buckets = new Map();
    for (const reading of state.readings) {
      const date = new Date(reading.measured_at);
      if (!Number.isFinite(date.getTime())) continue;
      const bucketDate = new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate()));
      if (period === "week") {
        bucketDate.setUTCDate(bucketDate.getUTCDate() - ((bucketDate.getUTCDay() + 6) % 7));
      } else if (period === "month") {
        bucketDate.setUTCDate(1);
      }
      const key = `${reading.metric}|${reading.room_id || ""}|${reading.sensor_id || ""}|${bucketDate.toISOString()}`;
      if (!buckets.has(key)) buckets.set(key, { ...reading, measured_at: bucketDate.toISOString(), values: [], sample_count: 0 });
      const bucket = buckets.get(key);
      bucket.values.push(Number(reading.value));
      bucket.sample_count += 1;
    }
    return [...buckets.values()].map(bucket => ({
      ...bucket,
      value: bucket.values.reduce((sum, value) => sum + value, 0) / bucket.values.length,
      aggregated: true
    }));
  }

  function renderCharts() {
    const chartRoot = $("#charts");
    const period = $("#aggregation")?.value || "sample";
    const compareBy = $("#compare-by")?.value || "parameter";
    const chartReadings = period === "sample" ? state.readings : aggregatedReadings(period);
    const selected = state.metrics.filter(metric => checkedMetrics().includes(metric.code));
    if (!selected.length) {
      chartRoot.innerHTML = '<div class="chart-empty">Select one or more available parameters.</div>';
      return;
    }
    const allTimes = chartReadings.map(reading => Date.parse(reading.measured_at)).filter(Number.isFinite);
    if (!allTimes.length) {
      chartRoot.innerHTML = selected.map(metric => `<div class="chart-empty">${esc(metric.name)} · No samples in the selected range.</div>`).join("");
      return;
    }
    const fullStart = Math.min(...allTimes), fullEnd = Math.max(...allTimes);
    const fullSpan = Math.max(fullEnd - fullStart, 60_000);
    const visibleSpan = fullSpan / state.zoom;
    const maxPan = Math.max(0, fullSpan - visibleSpan);
    state.pan = Math.min(Math.max(0, state.pan), maxPan);
    const rangeStart = fullStart + state.pan;
    const rangeEnd = rangeStart + visibleSpan;
    const width = Math.max(760, Math.min(1400, 760 + Math.log10(chartReadings.length + 1) * 100));
    const height = 190, left = 58, right = 18, top = 14, bottom = 36;
    const plotWidth = width - left - right, plotHeight = height - top - bottom;
    const chartSeries = [];
    for (const metric of selected) {
      const matching = chartReadings.filter(reading => reading.metric === metric.code);
      if (compareBy === "room-sensor") {
        const groups = new Map();
        for (const reading of matching) {
          const key = `${reading.room_id || ""}|${reading.sensor_id || ""}`;
          if (!groups.has(key)) groups.set(key, []);
          groups.get(key).push(reading);
        }
        for (const readings of groups.values()) {
          const room = state.rooms.find(item => item.id === readings[0].room_id)?.name || readings[0].room;
          const sensor = state.sensors.find(item => item.id === readings[0].sensor_id)?.name || "Unassigned sensor";
          chartSeries.push({ metric, readings, label: `${room} · ${sensor}` });
        }
      } else {
        chartSeries.push({ metric, readings: matching, label: metric.name });
      }
    }
    chartRoot.innerHTML = chartSeries.map(({ metric, readings: allReadings, label }, index) => {
      const readings = allReadings.filter(reading => {
        const time = Date.parse(reading.measured_at);
        return time >= rangeStart && time <= rangeEnd;
      });
      if (!readings.length) {
        return `<div class="chart-panel"><h3 class="chart-title">${esc(metric.name)} <small>${esc(metric.unit)}</small></h3><div class="chart-empty">No samples for this parameter in the visible chart range.</div></div>`;
      }
      const series = seriesGroups(readings);
      const intervals = [];
      const gaps = [];
      const configured = [];
      for (const points of series.values()) {
        const sensor = state.sensors.find(item => item.id === points[0]?.sensor_id);
        const expectedInterval = Number(sensor?.reporting_interval_seconds);
        if (period === "sample" && Number.isFinite(expectedInterval) && expectedInterval > 0) {
          configured.push(duration(expectedInterval));
        }
        const seriesIntervals = [];
        for (let point = 1; point < points.length; point += 1) {
          const interval = (Date.parse(points[point].measured_at) - Date.parse(points[point - 1].measured_at)) / 1000;
          intervals.push(interval);
          seriesIntervals.push(interval);
        }
        const seriesCadence = median(seriesIntervals);
        const gapThreshold = expectedInterval > 0 ? expectedInterval * 2 : seriesCadence * 2;
        if (period === "sample" && Number.isFinite(gapThreshold) && gapThreshold > 0) {
          for (let point = 1; point < points.length; point += 1) {
            const start = Date.parse(points[point - 1].measured_at);
            const end = Date.parse(points[point].measured_at);
            const delta = (end - start) / 1000;
            if (delta <= gapThreshold) continue;
            const x1 = left + (start - rangeStart) / visibleSpan * plotWidth;
            const x2 = left + (end - rangeStart) / visibleSpan * plotWidth;
            const cadenceLabel = expectedInterval > 0
              ? `configured cadence ${duration(expectedInterval)}`
              : `observed median interval ${duration(seriesCadence)}`;
            gaps.push(`<rect class="gap-band" x="${x1.toFixed(2)}" y="${top}" width="${Math.max(1, x2 - x1).toFixed(2)}" height="${plotHeight}"><title>Observed gap: ${esc(duration(delta))}; ${esc(cadenceLabel)}</title></rect>`);
          }
        }
      }
      const cadence = median(intervals);
      const values = readings.map(reading => Number(reading.value)).filter(Number.isFinite);
      let minimum = Math.min(...values), maximum = Math.max(...values);
      if (minimum === maximum) {
        const margin = Math.max(Math.abs(minimum) * 0.05, 1);
        minimum -= margin; maximum += margin;
      }
      const grid = [0, 0.5, 1].map(fraction => {
        const y = top + (1 - fraction) * plotHeight;
        return `<line class="chart-grid" x1="${left}" y1="${y}" x2="${width - right}" y2="${y}"/><text class="chart-axis" x="${left - 7}" y="${y + 3}" text-anchor="end">${esc(numeric(minimum + fraction * (maximum - minimum)))}</text>`;
      }).join("");
      const dots = readings.map(reading => {
        const x = left + (Date.parse(reading.measured_at) - rangeStart) / visibleSpan * plotWidth;
        const y = top + (1 - (Number(reading.value) - minimum) / (maximum - minimum)) * plotHeight;
        const sensor = state.sensors.find(item => item.id === reading.sensor_id)?.name || "Unassigned sensor";
        const title = `${formatTimestamp(reading.measured_at)} · ${numeric(Number(reading.value))} ${reading.unit} · ${sensor}${reading.aggregated ? ` · average of ${reading.sample_count} actual samples` : ""}`;
        return `<circle class="chart-dot" cx="${x.toFixed(2)}" cy="${y.toFixed(2)}" r="4" style="fill:${colors[index % colors.length]}"><title>${esc(title)}</title></circle>`;
      }).join("");
      const startLabel = formatTimestamp(new Date(rangeStart).toISOString(), { hour: "2-digit", minute: "2-digit" });
      const endLabel = formatTimestamp(new Date(rangeEnd).toISOString(), { hour: "2-digit", minute: "2-digit" });
      const expectedLabel = [...new Set(configured)].join(", ");
      const sampleLabel = period === "sample"
        ? `${readings.length} actual samples · median interval ${cadence === null ? "not available" : esc(duration(cadence))}${expectedLabel ? ` · configured ${esc(expectedLabel)}` : ""}`
        : `${readings.reduce((count, item) => count + item.sample_count, 0)} actual samples summarized in ${readings.length} non-empty ${period} periods`;
      return `<div class="chart-panel"><h3 class="chart-title"><span><i class="legend-dot" style="background:${colors[index % colors.length]}"></i>${esc(metric.name)} <small>${esc(metric.code)} · ${esc(metric.unit)}${compareBy === "room-sensor" ? ` · ${esc(label)}` : ""}</small></span><small>${sampleLabel}</small></h3><svg class="history-svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="${esc(metric.name)} stored samples plotted at their actual timestamps">${grid}${gaps.join("")}${dots}<text class="chart-axis" x="${left}" y="${height - 6}">${esc(startLabel)}</text><text class="chart-axis" x="${width - right}" y="${height - 6}" text-anchor="end">${esc(endLabel)}</text></svg></div>`;
    }).join("");
  }

  function visibleTableRows() {
    const search = $("#table-search").value.trim().toLocaleLowerCase();
    const selected = new Set(checkedMetrics());
    const intervals = intervalData(state.readings).perReading;
    return [...state.readings]
      .filter(reading => selected.has(reading.metric))
      .filter(reading => {
        if (!search) return true;
        const room = state.rooms.find(item => item.id === reading.room_id)?.name || reading.room;
        const sensor = state.sensors.find(item => item.id === reading.sensor_id)?.name || "Unassigned sensor";
        return [reading.measured_at, room, sensor, reading.metric_name, reading.metric, reading.value, reading.unit, reading.source]
          .join(" ").toLocaleLowerCase().includes(search);
      })
      .sort((a, b) => Date.parse(b.measured_at) - Date.parse(a.measured_at))
      .map(reading => ({ reading, interval: intervals.get(reading.id) }));
  }

  function renderTable() {
    const entries = visibleTableRows();
    const totalPages = Math.max(1, Math.ceil(entries.length / state.pageSize));
    state.page = Math.min(state.page, totalPages - 1);
    const pageRows = entries.slice(state.page * state.pageSize, (state.page + 1) * state.pageSize);
    const body = $("#reading-rows");
    body.innerHTML = pageRows.map(({ reading, interval }) => {
      const room = state.rooms.find(item => item.id === reading.room_id)?.name || reading.room;
      const sensor = state.sensors.find(item => item.id === reading.sensor_id)?.name || "Unassigned sensor";
      return `<tr><td>${esc(formatTimestamp(reading.measured_at))}</td><td><time datetime="${esc(reading.measured_at)}">${esc(reading.measured_at)}</time></td><td>${esc($("#household").selectedOptions[0]?.textContent || "")}</td><td>${esc(room)}</td><td>${esc(sensor)}</td><td>${esc(reading.metric_name)} <small>(${esc(reading.metric)})</small></td><td class="numeric">${esc(reading.value)}</td><td>${esc(reading.unit)}</td><td>${interval === undefined ? "—" : esc(duration(interval))}</td><td>${esc(reading.source)}</td></tr>`;
    }).join("") || '<tr><td class="table-empty" colspan="10">No stored readings match these filters.</td></tr>';
    $("#table-count").textContent = `${entries.length.toLocaleString()} matching readings`;
    $("#page-indicator").textContent = `Page ${state.page + 1} of ${totalPages}`;
    $("#previous-page").disabled = state.page === 0;
    $("#next-page").disabled = state.page + 1 >= totalPages;
  }

  function render() {
    renderSummary();
    renderCharts();
    renderTable();
  }

  function exportUrl(extension) {
    const params = filterParams();
    return `${homePath()}/history.${extension}?${params}`;
  }

  async function initialize() {
    setDateDefaults();
    try {
      await loadChoices({ preserve: false });
      await loadReadings();
    } catch (error) {
      setStatus(error.message || "Unable to load History.", true);
    }
  }

  $("#household").addEventListener("change", async () => {
    const homeId = $("#household").value;
    const homeName = $("#household").selectedOptions[0]?.textContent || "";
    state.readings = [];
    render();
    setStatus("Loading the selected household…");
    $("#active-household-name").textContent = homeName;
    $$(".dashboard-return").forEach(link => {
      link.href = `/alerts?home_id=${encodeURIComponent(homeId)}`;
    });
    const url = new URL(window.location.href);
    url.searchParams.set("home_id", homeId);
    window.history.replaceState(null, "", url);
    try {
      await loadChoices({ preserve: false });
      await loadReadings();
    } catch (error) {
      setStatus(error.message, true);
    }
  });
  $("#room").addEventListener("change", async () => {
    updateSensorOptions();
    try {
      await loadMetricOptions(new Set());
      await loadReadings();
    } catch (error) {
      setStatus(error.message, true);
    }
  });
  $("#sensor").addEventListener("change", async () => {
    try {
      await loadMetricOptions(new Set());
      await loadReadings();
    } catch (error) {
      setStatus(error.message, true);
    }
  });
  $("#apply-filters").addEventListener("click", loadReadings);
  $("#reset-range").addEventListener("click", () => { setDateDefaults(); loadReadings(); });
  $("#parameters").addEventListener("change", () => {
    state.page = 0;
    render();
  });
  $("#table-search").addEventListener("input", () => { state.page = 0; renderTable(); });
  $("#previous-page").addEventListener("click", () => { state.page -= 1; renderTable(); });
  $("#next-page").addEventListener("click", () => { state.page += 1; renderTable(); });
  $("#zoom-in").addEventListener("click", () => { state.zoom = Math.min(16, state.zoom * 2); renderCharts(); });
  $("#zoom-out").addEventListener("click", () => { state.zoom = Math.max(1, state.zoom / 2); renderCharts(); });
  $("#zoom-reset").addEventListener("click", () => { state.zoom = 1; state.pan = 0; renderCharts(); });
  $("#pan-back").addEventListener("click", () => { state.pan = Math.max(0, state.pan - (state.readings.length ? (Math.max(...state.readings.map(item => Date.parse(item.measured_at))) - Math.min(...state.readings.map(item => Date.parse(item.measured_at)))) / state.zoom * 0.6 : 0)); renderCharts(); });
  $("#pan-forward").addEventListener("click", () => {
    const times = state.readings.map(item => Date.parse(item.measured_at));
    if (times.length) {
      const span = Math.max(...times) - Math.min(...times);
      state.pan = Math.min(span - span / state.zoom, state.pan + span / state.zoom * 0.6);
      renderCharts();
    }
  });
  $("#export-csv").addEventListener("click", () => {
    try { window.location.assign(exportUrl("csv")); } catch (error) { setStatus(error.message, true); }
  });
  $("#export-pdf").addEventListener("click", () => {
    try { window.location.assign(exportUrl("pdf")); } catch (error) { setStatus(error.message, true); }
  });
  $("#theme-toggle").addEventListener("click", () => {
    const next = document.documentElement.dataset.theme === "night" ? "day" : "night";
    document.documentElement.dataset.theme = next;
    $("#theme-toggle").setAttribute("aria-label", `Switch to ${next === "night" ? "day" : "night"} mode`);
    try { localStorage.setItem("airsense-theme", next); } catch { /* Theme remains available for this page. */ }
  });
  try {
    const savedTheme = localStorage.getItem("airsense-theme");
    if (savedTheme === "day" || savedTheme === "night") document.documentElement.dataset.theme = savedTheme;
  } catch { /* Theme preference is optional. */ }
  initialize();
})();
