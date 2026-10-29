(() => {
  "use strict";

  const config = JSON.parse(document.getElementById("airsense-config").textContent);
  const metrics = {
    CO2: { label: "CO₂", unit: "ppm", max: 2000 },
    temperature: { label: "Temperature", unit: "°C", max: 40 },
    humidity: { label: "Humidity", unit: "%", max: 100 }
  };
  let rooms = [];
  let sensors = [];
  let alerts = [];
  let thresholds = [];
  let members = [];
  let activity = [];
  let historyReadings = [];
  let selectedMetric = "CO2";
  let roomFilter = "all";
  let alertFilter = "all";
  let metricTimer = null;

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));
  const escapeHtml = value => String(value ?? "").replace(/[&<>"']/g, char => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  })[char]);
  const format = (value, digits = 0) => Number(value).toLocaleString(undefined, { maximumFractionDigits: digits });
  const dateTime = value => value ? new Date(value).toLocaleString() : "Never";
  const dateOnly = value => value ? new Date(value).toLocaleDateString() : "—";
  const activeAlerts = () => alerts.filter(alert => alert.status === "active" || alert.status === "acknowledged");
  const statusText = status => ({
    active: "Open",
    acknowledged: "Acknowledged",
    all_clear: "All clear",
    high: "High",
    elevated: "Elevated",
    rapid_rise: "Rapid rise",
    none: "No active alert"
  })[status] || status.replaceAll("_", " ");
  const statusClass = status => status.replaceAll("_", "-");
  const roomStatus = room => {
    const alert = activeAlerts().find(item => item.room_id === room.id);
    return alert ? alert.level : "none";
  };
  const latestReading = (room, metric = "CO2") =>
    room.readings.find(reading => reading.metric === metric) || null;

  async function api(path, options = {}) {
    const headers = new Headers(options.headers || {});
    if (options.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
    if (options.method && !["GET", "HEAD"].includes(options.method.toUpperCase())) {
      headers.set("X-CSRF-Token", config.csrfToken);
    }
    const response = await fetch(path, {
      ...options,
      headers,
      credentials: "same-origin"
    });
    const contentType = response.headers.get("content-type") || "";
    const payload = contentType.includes("application/json") ? await response.json() : null;
    if (response.status === 401) {
      window.location.assign(`/login?next=${encodeURIComponent(window.location.pathname + window.location.search)}`);
      throw new Error("Your session has expired. Sign in again.");
    }
    if (!response.ok) throw new Error(payload?.error || `Request failed (${response.status}).`);
    return payload;
  }

  function showMessage(message, type = "info") {
    let node = $("#app-status");
    if (!node) {
      node = document.createElement("div");
      node.id = "app-status";
      node.className = "info-banner";
      node.setAttribute("role", "status");
      $(".page-content").prepend(node);
    }
    node.classList.toggle("error-banner", type === "error");
    node.textContent = message;
    node.hidden = false;
    window.clearTimeout(showMessage.timer);
    showMessage.timer = window.setTimeout(() => { node.hidden = true; }, 6000);
  }

  async function runAction(action) {
    try {
      return await action();
    } catch (error) {
      showMessage(error.message || "Something went wrong. Please try again.", "error");
      return null;
    }
  }

  function showView(name) {
    $$("[data-view]").forEach(view => view.classList.toggle("active", view.dataset.view === name));
    $$("[data-nav]").forEach(button => button.classList.toggle("active", button.dataset.nav === name));
    const heading = $(`[data-view="${name}"] h1`);
    $("#breadcrumb-current").textContent = heading ? heading.textContent.trim() : "Overview";
    $(".sidebar").classList.remove("mobile-open");
    $("#mobile-menu").setAttribute("aria-expanded", "false");
    window.scrollTo({ top: 0, behavior: "smooth" });
    if (name === "history") loadHistory();
    if (name === "activity") loadActivity();
  }

  function valueLabel(reading) {
    if (!reading) return "No reading";
    const digits = reading.metric === "temperature" ? 1 : 0;
    return `${format(reading.value, digits)} ${reading.unit}`;
  }

  function roomCard(room) {
    const state = roomStatus(room);
    const ventilation = (room.ventilation_sources || [room.ventilation || "Not specified"]).join(" · ");
    const readingRows = room.readings.length
      ? room.readings.map(reading => {
        const metric = metrics[reading.metric] || { label: reading.metric_name || reading.metric, unit: reading.unit };
        return `<div class="reading-line"><span class="reading-name">${escapeHtml(metric.label)}</span><strong class="reading-value">${escapeHtml(format(reading.value, reading.metric === "temperature" ? 1 : 0))}<span class="reading-unit">${escapeHtml(reading.unit)}</span></strong></div>`;
      }).join("")
      : '<p class="empty-state">No readings received yet.</p>';
    const lastReading = room.readings.slice().sort((a, b) => new Date(b.measured_at) - new Date(a.measured_at))[0];
    return `<article class="room-card"><div class="room-card-header"><div><h3 class="room-name">${escapeHtml(room.name)}</h3><p class="room-meta">${escapeHtml(ventilation)}</p></div><span class="status-pill status-${statusClass(state)}">${escapeHtml(statusText(state))}</span></div><div class="reading-list">${readingRows}</div><div class="reading-details"><span class="source-pill">${room.sensors.length} sensor${room.sensors.length === 1 ? "" : "s"}</span><span class="reading-age">${lastReading ? `Updated ${escapeHtml(dateTime(lastReading.measured_at))}` : "Awaiting first reading"}</span></div></article>`;
  }

  function renderRooms() {
    const attention = rooms.filter(room => roomStatus(room) !== "none");
    $("#room-grid").innerHTML = rooms.slice(0, 3).map(roomCard).join("") || '<p class="empty-state">No rooms yet. Add a room to get started.</p>';
    const filtered = rooms.filter(room => roomFilter === "all" || roomStatus(room) !== "none");
    $("#all-room-grid").innerHTML = filtered.length ? filtered.map(roomCard).join("") : '<p class="empty-state">No rooms match this filter.</p>';
    $("#room-count").textContent = rooms.length;
    $("#snapshot-room-count").textContent = `${rooms.length} room${rooms.length === 1 ? "" : "s"}`;
    $("#mini-room-status").innerHTML = rooms.length
      ? `<span class="mini-status-dot good"></span>${rooms.length - attention.length} clear <span class="mini-status-dot attention"></span>${attention.length} need attention`
      : "No rooms configured";
    $$("#room-filters [data-filter]").forEach(button => {
      const count = button.dataset.filter === "all" ? rooms.length : attention.length;
      button.innerHTML = `${button.dataset.filter === "all" ? "All rooms" : "Needs a look"} <span>${count}</span>`;
      button.classList.toggle("selected", button.dataset.filter === roomFilter);
    });
    const roomOptions = rooms.map(room => `<option value="${escapeHtml(room.id)}">${escapeHtml(room.name)}</option>`).join("");
    const historyRoom = $("#history-room");
    const previousRoom = historyRoom.value;
    historyRoom.innerHTML = roomOptions || '<option value="">No rooms</option>';
    if (rooms.some(room => room.id === previousRoom)) historyRoom.value = previousRoom;
    $("#sensor-room-select").innerHTML = roomOptions || '<option value="">Add a room first</option>';
    $("#sensor-form button[type=submit]").disabled = rooms.length === 0;
    renderSnapshot();
  }

  function renderSnapshot() {
    const readings = rooms.map(room => ({ room, reading: latestReading(room) })).filter(item => item.reading);
    const mostRecent = readings.slice().sort((a, b) => new Date(b.reading.measured_at) - new Date(a.reading.measured_at))[0];
    $("#snapshot-updated").textContent = mostRecent ? dateTime(mostRecent.reading.measured_at) : "—";
    const body = $("#snapshot-main");
    const center = readings.length
      ? Math.round(readings.reduce((sum, item) => sum + Number(item.reading.value), 0) / readings.length)
      : null;
    const high = Math.max(...thresholds.map(item => Number(item.high_threshold)), Number(config.defaults.high_threshold));
    const elevated = Math.max(...thresholds.map(item => Number(item.elevated_threshold)), Number(config.defaults.elevated_threshold));
    const score = center === null ? null : Math.max(0, Math.min(100, Math.round(100 - (center / high) * 55)));
    const level = center === null ? "none" : center >= high ? "high" : center >= elevated ? "elevated" : "none";
    const summary = center === null ? "Waiting for readings" : level === "none" ? `${format(center)} ppm average CO₂` : `${statusText(level)} · ${format(center)} ppm average CO₂`;
    body.innerHTML = `<div class="air-score"><div class="score-number">${score === null ? "—" : score}</div><div class="score-caption">Home<br>snapshot</div></div><div class="snapshot-copy"><span class="status-pill status-${statusClass(level)}">${escapeHtml(summary)}</span><p>${center === null ? "Connect a sensor or enter a simulator reading to see home conditions." : `${readings.length} room${readings.length === 1 ? "" : "s"} with recent CO₂ data.`}</p><button class="text-button" type="button" data-nav="demo">Enter a reading <span>→</span></button></div>`;
  }

  function renderChart() {
    const metric = metrics[selectedMetric];
    $("#metric-tabs").innerHTML = Object.entries(metrics).map(([key, item]) => `<button class="metric-tab" type="button" role="tab" aria-selected="${key === selectedMetric}" data-metric="${key}">${item.label}</button>`).join("");
    const values = rooms.map(room => ({ room, reading: latestReading(room, selectedMetric) })).filter(item => item.reading);
    $("#room-chart").innerHTML = values.length ? values.map(({ room, reading }) => {
      const value = Number(reading.value);
      return `<div class="bar-row"><span class="bar-room">${escapeHtml(room.name)}</span><div class="bar-track"><div class="bar-fill" style="width:${Math.min(100, Math.max(2, value / metric.max * 100))}%"></div></div><span class="bar-value">${escapeHtml(format(value, selectedMetric === "temperature" ? 1 : 0))} ${escapeHtml(reading.unit)}</span></div>`;
    }).join("") : '<p class="empty-state">No readings for this metric yet.</p>';
    $("#chart-updated").textContent = values.length ? `Latest server readings · ${values.length} room${values.length === 1 ? "" : "s"}` : "Waiting for readings";
  }

  function renderAlerts() {
    const open = alerts.filter(alert => alert.status === "active").length;
    $("#nav-alert-count").textContent = open;
    $("#open-alert-count").textContent = open;
    $("#alert-open-stat").textContent = alerts.filter(alert => alert.status === "active").length;
    $("#alert-ack-stat").textContent = alerts.filter(alert => alert.status === "acknowledged").length;
    $("#alert-clear-stat").textContent = alerts.filter(alert => alert.status === "all_clear").length;
    const filtered = alertFilter === "all"
      ? alerts
      : alertFilter === "open"
        ? alerts.filter(alert => alert.status === "active")
        : alerts.filter(alert => alert.status === alertFilter);
    $("#alert-list").innerHTML = filtered.map(alert => `<article class="alert-item"><div><span class="status-pill status-${statusClass(alert.level)}">${escapeHtml(statusText(alert.level))}</span><div class="alert-room">${escapeHtml(alert.room)}<span class="alert-metric">${escapeHtml(alert.metric_name || alert.metric)} · ${escapeHtml(valueLabel({ value: alert.latest_value, unit: alert.threshold_unit, metric: alert.metric }))}</span></div></div><span class="alert-status">${escapeHtml(statusText(alert.status))} · ${escapeHtml(dateTime(alert.created_at))}</span><div class="alert-description">${escapeHtml(alert.detail)}</div>${alert.status === "active" ? `<form class="ack-form" data-ack="${alert.id}"><button class="button button-outline" type="submit">Acknowledge</button></form>` : alert.acknowledged_by ? `<span class="muted">Acknowledged by ${escapeHtml(alert.acknowledged_by)}</span>` : ""}</article>`).join("") || '<p class="empty-state">No alerts in this view.</p>';
    $("#overview-alerts").innerHTML = alerts.filter(alert => alert.status === "active").slice(0, 2).map(alert => `<div class="preview-alert"><span class="status-pill status-${statusClass(alert.level)}">${escapeHtml(statusText(alert.level))}</span><strong>${escapeHtml(alert.room)}</strong><span>${escapeHtml(valueLabel({ value: alert.latest_value, unit: alert.threshold_unit, metric: alert.metric }))}</span></div>`).join("") || '<p class="empty-state">No active alerts.</p>';
  }

  function renderSensors(query = $("#sensor-search").value) {
    const filtered = sensors.filter(sensor => `${sensor.name} ${sensor.room}`.toLowerCase().includes(query.toLowerCase()));
    $("#sensor-count").textContent = `${sensors.length} device${sensors.length === 1 ? "" : "s"}`;
    $("#sensor-table-body").innerHTML = filtered.map(sensor => {
      const state = sensor.status === "revoked" ? "Revoked" : statusText(sensor.state);
      return `<tr><td><strong>${escapeHtml(sensor.name)}</strong><small>${escapeHtml(sensor.id)}</small></td><td>${escapeHtml(sensor.room)}</td><td><span class="source-pill">${sensor.status === "active" ? "Device" : "Revoked"}</span></td><td>${escapeHtml(dateTime(sensor.last_seen_at))}</td><td><span class="status-pill ${sensor.state === "fresh" ? "status-none" : "status-elevated"}">${escapeHtml(state)}</span></td><td>${config.role === "owner" && sensor.status === "active" ? `<button class="text-button" type="button" data-rotate-sensor="${escapeHtml(sensor.id)}">Rotate key</button> <button class="text-button" type="button" data-revoke-sensor="${escapeHtml(sensor.id)}">Revoke</button>` : ""}</td></tr>`;
    }).join("") || '<tr><td colspan="6">No sensors found.</td></tr>';
  }

  function renderThresholds() {
    $("#threshold-table-body").innerHTML = rooms.map(room => {
      const policy = thresholds.find(item => item.room_id === room.id && item.metric === "CO2") || {
        elevated_threshold: config.defaults.elevated_threshold,
        high_threshold: config.defaults.high_threshold,
        elevated_duration_seconds: config.defaults.elevated_duration_seconds,
        rapid_rise_per_minute: config.defaults.rapid_rise_per_minute,
        all_clear_duration_seconds: config.defaults.all_clear_duration_seconds,
        max_reading_gap_seconds: config.defaults.max_reading_gap_seconds
      };
      return `<tr data-room-id="${escapeHtml(room.id)}"><td><strong>${escapeHtml(room.name)}</strong></td><td><input aria-label="${escapeHtml(room.name)} elevated threshold" type="number" min="1" data-threshold="elevated_threshold" value="${escapeHtml(policy.elevated_threshold)}"></td><td><input aria-label="${escapeHtml(room.name)} high threshold" type="number" min="1" data-threshold="high_threshold" value="${escapeHtml(policy.high_threshold)}"></td><td><input aria-label="${escapeHtml(room.name)} elevated duration" type="number" min="1" data-threshold="elevated_duration_seconds" value="${Math.ceil(policy.elevated_duration_seconds / 60)}"> min</td><td><input aria-label="${escapeHtml(room.name)} rapid rise" type="number" min="1" data-threshold="rapid_rise_per_minute" value="${escapeHtml(policy.rapid_rise_per_minute)}"> ppm</td></tr>`;
    }).join("") || '<tr><td colspan="5">Add a room to configure thresholds.</td></tr>';
    const first = thresholds[0] || config.defaults;
    $("#clear-duration").value = Math.max(1, Math.ceil(first.all_clear_duration_seconds / 60));
    $("#sample-gap").value = Math.max(1, Math.ceil(first.max_reading_gap_seconds / 60));
    $("#save-thresholds").hidden = config.role !== "owner";
    $$(".owner-only").forEach(element => { element.hidden = config.role !== "owner"; });
  }

  function renderMembers() {
    $("#member-table-body").innerHTML = members.map(member => `<tr><td><strong>${escapeHtml(member.display_name)}</strong><small>${escapeHtml(member.email)}</small></td><td><span class="role-pill">${escapeHtml(member.role)}</span></td><td>${escapeHtml(dateOnly(member.joined_at))}</td><td>${config.role === "owner" && member.role !== "owner" ? `<button class="text-button" type="button" data-remove-member="${escapeHtml(member.user_id)}">Remove</button>` : ""}</td></tr>`).join("") || '<tr><td colspan="4">No members found.</td></tr>';
  }

  function renderActivity() {
    $("#activity-table-body").innerHTML = activity.map(item => {
      const who = item.actor_user_id === config.userId ? config.userName : item.actor_user_id ? "Household member" : "Sensor / system";
      const details = Object.keys(item.details || {}).length
        ? Object.entries(item.details).map(([key, value]) => `${key}: ${typeof value === "object" ? JSON.stringify(value) : value}`).join(" · ")
        : `${item.entity_type}${item.entity_id ? ` · ${item.entity_id}` : ""}`;
      return `<tr><td><strong>${escapeHtml(item.event_type)}</strong></td><td>${escapeHtml(who)}</td><td>${escapeHtml(dateTime(item.created_at))}</td><td>${escapeHtml(details)}</td></tr>`;
    }).join("") || '<tr><td colspan="4">No activity has been recorded yet.</td></tr>';
  }

  async function loadActivity() {
    if (config.role !== "owner") {
      $("#activity-table-body").innerHTML = '<tr><td colspan="4">Only a home owner can view the activity log.</td></tr>';
      return;
    }
    const result = await runAction(() => api(`/api/homes/${encodeURIComponent(config.homeId)}/activity`));
    if (!result) return;
    activity = result.events;
    renderActivity();
  }

  async function loadHistory() {
    const roomId = $("#history-room").value;
    if (!roomId) {
      historyReadings = [];
      renderHistory();
      return;
    }
    const end = new Date();
    const start = new Date(end.getTime() - 90 * 86400000);
    const params = new URLSearchParams({
      room_id: roomId,
      metric: $("#history-metric").value || "CO2",
      from: start.toISOString(),
      to: end.toISOString(),
      limit: "10000"
    });
    const result = await runAction(() => api(`/api/homes/${encodeURIComponent(config.homeId)}/history?${params}`));
    if (!result) return;
    historyReadings = result.readings;
    renderHistory();
  }

  function renderHistory() {
    const room = rooms.find(item => item.id === $("#history-room").value);
    const metricKey = $("#history-metric").value || "CO2";
    const metric = metrics[metricKey] || { label: metricKey, unit: "", max: 100 };
    const days = Number($("#history-range").value || 30);
    if (!room) {
      $("#history-series-title").textContent = "No room selected";
      $("#history-current-value").textContent = "—";
      $("#history-chart").innerHTML = "";
      $("#heatmap-grid").innerHTML = "";
      $("#heatmap-months").innerHTML = "";
      $("#history-axis").innerHTML = "";
      return;
    }
    const recent = latestReading(room, metricKey);
    $("#history-series-title").textContent = `${room.name} · ${metric.label}`;
    $("#history-current-value").innerHTML = `${recent ? format(recent.value, metricKey === "temperature" ? 1 : 0) : "—"} <small>${escapeHtml(recent?.unit || metric.unit)}</small>`;
    const now = new Date();
    const visibleStart = new Date(now.getTime() - days * 86400000);
    const daily = new Map();
    historyReadings.filter(reading => new Date(reading.measured_at) >= visibleStart).forEach(reading => {
      const key = new Date(reading.measured_at).toLocaleDateString();
      const values = daily.get(key) || [];
      values.push(Number(reading.value));
      daily.set(key, values);
    });
    const dates = Array.from({ length: days }, (_, index) => {
      const date = new Date(visibleStart.getFullYear(), visibleStart.getMonth(), visibleStart.getDate() + index + 1);
      const values = daily.get(date.toLocaleDateString()) || [];
      return { date, value: values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : null, count: values.length };
    });
    const svg = $("#history-chart");
    const width = 1000, height = 320, left = 64, right = 18, top = 18, bottom = 54;
    const plotWidth = width - left - right, plotHeight = height - top - bottom, step = plotWidth / days;
    const barWidth = Math.max(2, Math.min(20, step * 0.66));
    const maximum = Math.max(metric.max, ...dates.map(item => item.value || 0)) * 1.05;
    const grid = [0, 0.25, 0.5, 0.75, 1].map(fraction => {
      const y = top + plotHeight * (1 - fraction);
      return `<line class="history-gridline" x1="${left}" y1="${y}" x2="${width - right}" y2="${y}"/><text class="history-y-label" x="${left - 10}" y="${y + 4}" text-anchor="end">${format(maximum * fraction)}</text>`;
    }).join("");
    const bars = dates.map((item, index) => {
      if (item.value === null) return "";
      const barHeight = Math.max(2, Math.min(plotHeight, item.value / maximum * plotHeight));
      const x = left + index * step + (step - barWidth) / 2;
      const y = top + plotHeight - barHeight;
      const fullDate = item.date.toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric", year: "numeric" });
      return `<rect class="history-bar" x="${x.toFixed(2)}" y="${y.toFixed(2)}" width="${barWidth.toFixed(2)}" height="${barHeight.toFixed(2)}" rx="${Math.min(4, barWidth / 3)}"><title>${escapeHtml(fullDate)}: ${format(item.value)} ${escapeHtml(metric.unit)} · ${item.count} reading${item.count === 1 ? "" : "s"}</title></rect>`;
    }).join("");
    const ticks = [...new Set([0, Math.round((days - 1) / 4), Math.round((days - 1) / 2), Math.round((days - 1) * 3 / 4), days - 1])].map(index => {
      const x = left + index * step + step / 2;
      return `<text class="history-date-label" x="${x.toFixed(2)}" y="${height - 16}" text-anchor="middle">${dates[index].date.toLocaleDateString(undefined, { month: "short", day: "numeric" })}</text>`;
    }).join("");
    svg.setAttribute("aria-label", `Stored ${metric.label} readings in ${room.name} for the last ${days} days`);
    svg.innerHTML = `${grid}${bars}${ticks}`;
    $("#history-axis").textContent = historyReadings.length
      ? `${historyReadings.length} stored readings in this range`
      : "No readings were recorded in this date range.";
    renderHeatmap(metricKey, now);
  }

  function renderHeatmap(metric, now) {
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const rangeStart = new Date(today);
    rangeStart.setDate(today.getDate() - 89);
    const first = new Date(rangeStart);
    first.setDate(first.getDate() - ((first.getDay() + 6) % 7));
    const last = new Date(today);
    last.setDate(last.getDate() + (6 - ((last.getDay() + 6) % 7)));
    const dates = [];
    for (const date = new Date(first); date <= last; date.setDate(date.getDate() + 1)) dates.push(new Date(date));
    const countByDate = new Map();
    if (historyReadings.length) {
      historyReadings.forEach(reading => {
        const key = new Date(reading.measured_at).toLocaleDateString();
        countByDate.set(key, (countByDate.get(key) || 0) + 1);
      });
    }
    const totalWeeks = Math.ceil(dates.length / 7);
    const monthFormat = new Intl.DateTimeFormat(undefined, { month: "short", year: "numeric" });
    const monthLabels = [];
    for (let week = 0; week < totalWeeks; week += 1) {
      const date = dates[week * 7];
      if (date && date.getDate() <= 7) monthLabels.push(`<span style="grid-column:${week + 1}">${escapeHtml(monthFormat.format(date))}</span>`);
    }
    $("#heatmap-months").style.gridTemplateColumns = `repeat(${totalWeeks}, 12px)`;
    $("#heatmap-months").innerHTML = monthLabels.join("");
    $("#heatmap-grid").style.gridTemplateColumns = `repeat(${totalWeeks}, 12px)`;
    const fullDate = new Intl.DateTimeFormat(undefined, { weekday: "long", month: "long", day: "numeric", year: "numeric" });
    $("#heatmap-grid").innerHTML = dates.map((date, index) => {
      const inRange = date >= rangeStart && date <= today;
      const count = inRange ? countByDate.get(date.toLocaleDateString()) || 0 : 0;
      const level = !inRange ? "empty" : count === 0 ? 0 : count < 3 ? 1 : count < 8 ? 2 : 3;
      const label = `${fullDate.format(date)} · ${count} ${metric} reading${count === 1 ? "" : "s"}`;
      return `<span class="heat-cell heat-${level}" role="img" aria-label="${escapeHtml(label)}" title="${escapeHtml(label)}" style="grid-column:${Math.floor(index / 7) + 1};grid-row:${(index % 7) + 1}"></span>`;
    }).join("");
  }

  async function loadHome() {
    const root = `/api/homes/${encodeURIComponent(config.homeId)}`;
    const [roomData, sensorData, thresholdData, dashboardData] = await Promise.all([
      api(`${root}/rooms`),
      api(`${root}/sensors`),
      api(`${root}/thresholds`),
      api(`${root}/dashboard`)
    ]);
    rooms = roomData.rooms.map(room => ({ ...room, readings: room.readings || [], sensors: room.sensors || [] }));
    sensors = sensorData.sensors;
    thresholds = thresholdData.thresholds;
    alerts = dashboardData.alerts.map(alert => ({
      ...alert,
      status: alert.status === "active" ? "active" : alert.status
    }));
    rooms.forEach(room => {
      const latest = dashboardData.readings.filter(reading => reading.room === room.name);
      if (latest.length) room.readings = latest;
    });
    sensors.forEach(sensor => {
      sensor.room = rooms.find(room => room.id === sensor.room_id)?.name || "Unknown room";
    });
    const allMetrics = new Set(rooms.flatMap(room => room.readings.map(reading => reading.metric)));
    Object.keys(metrics).forEach(key => {
      const available = allMetrics.has(key) || (key === "CO2" && allMetrics.size === 0);
      $$(`#history-metric option[value="${key}"]`).forEach(option => { option.disabled = !available; });
    });
    if (!allMetrics.has($("#history-metric").value) && allMetrics.size) {
      $("#history-metric").value = Array.from(allMetrics)[0];
    }
    renderRooms();
    renderChart();
    renderAlerts();
    renderSensors();
    renderThresholds();
    $("#today-label").textContent = new Intl.DateTimeFormat(undefined, { weekday: "long", month: "long", day: "numeric" }).format(new Date()).toUpperCase();
    $("#snapshot-updated").textContent = dashboardData.readings.length
      ? dateTime(dashboardData.readings.map(item => item.measured_at).sort().slice(-1)[0])
      : "—";
    $("#preview-chip-label").textContent = "Connected";
    if (config.role !== "owner") {
      $("#view-activity .page-subtitle").textContent = "Activity log is available to the home owner.";
      $("#view-activity .info-banner").hidden = true;
    }
    renderHistory();
  }

  function openModal(id) {
    const modal = document.getElementById(id);
    if (!modal) return;
    modal.hidden = false;
    const input = $("input", modal);
    if (input) input.focus();
  }

  async function createRoom(form) {
    const formData = new FormData(form);
    const data = {
      name: formData.get("name"),
      ventilation_sources: formData.getAll("ventilation_sources")
    };
    if (!data.ventilation_sources.length) {
      throw new Error("Choose at least one ventilation source.");
    }
    await api(`/api/homes/${encodeURIComponent(config.homeId)}/rooms`, {
      method: "POST",
      body: JSON.stringify(data)
    });
    form.reset();
    form.closest(".modal-backdrop").hidden = true;
    await loadHome();
    showMessage("Room added.");
  }

  async function provisionSensor(form) {
    const data = Object.fromEntries(new FormData(form));
    data.reporting_interval_seconds = Number(data.reporting_interval_seconds);
    const result = await api(`/api/homes/${encodeURIComponent(config.homeId)}/sensors`, {
      method: "POST",
      body: JSON.stringify(data)
    });
    const previousKeyResult = $("#sensor-key-result");
    if (previousKeyResult) previousKeyResult.remove();
    const box = document.createElement("div");
    box.id = "sensor-key-result";
    box.className = "invite-code-box";
    box.setAttribute("role", "alert");
    box.textContent = `Copy this device key now. It cannot be shown again: ${result.device_key}`;
    $("#sensor-modal .modal").append(box);
    form.reset();
    $("#sensor-room-select").value = data.room_id;
    await loadHome();
  }

  async function inviteMember(form) {
    const data = Object.fromEntries(new FormData(form));
    const result = await api(`/api/homes/${encodeURIComponent(config.homeId)}/invitations`, {
      method: "POST",
      body: JSON.stringify(data)
    });
    const inviteUrl = `${window.location.origin}/join?token=${encodeURIComponent(result.invitation.token)}`;
    $("#invite-code-box").hidden = false;
    $("#invite-code-box").textContent = `${result.invitation.delivery} Invitation link: ${inviteUrl}`;
    await loadActivity();
  }

  function bindEvents() {
    $("#theme-toggle").addEventListener("click", event => {
      const button = event.currentTarget;
      const dark = document.body.classList.toggle("theme-dark");
      localStorage.setItem("airsense-theme", dark ? "dark" : "light");
      button.textContent = dark ? "☀" : "☾";
      button.setAttribute("aria-label", dark ? "Switch to light theme" : "Switch to dark theme");
      button.setAttribute("title", dark ? "Switch to light theme" : "Switch to dark theme");
      button.setAttribute("aria-pressed", String(dark));
    });
    const savedTheme = localStorage.getItem("airsense-theme");
    if (savedTheme === "dark") $("#theme-toggle").click();

    document.addEventListener("click", event => {
      const target = event.target.closest("[data-nav], [data-open-modal], [data-close-modal], [data-filter], [data-alert-filter], [data-metric], [data-remove-member], [data-scenario], [data-rotate-sensor], [data-revoke-sensor], #mobile-menu, #banner-dismiss");
      if (!target) return;
      if (target.dataset.nav) showView(target.dataset.nav);
      if (target.dataset.openModal) openModal(target.dataset.openModal);
      if (target.hasAttribute("data-close-modal")) target.closest(".modal-backdrop").hidden = true;
      if (target.dataset.filter) {
        roomFilter = target.dataset.filter;
        renderRooms();
      }
      if (target.dataset.alertFilter) {
        alertFilter = target.dataset.alertFilter;
        $$("#alert-filters [data-alert-filter]").forEach(button => button.classList.toggle("selected", button === target));
        renderAlerts();
      }
      if (target.dataset.metric) {
        selectedMetric = target.dataset.metric;
        renderChart();
      }
      if (target.dataset.removeMember) runAction(async () => {
        await api(`/api/homes/${encodeURIComponent(config.homeId)}/members/${encodeURIComponent(target.dataset.removeMember)}`, { method: "DELETE" });
        await loadMembers();
        showMessage("Member removed.");
      });
      if (target.dataset.rotateSensor) runAction(async () => {
        const result = await api(`/api/homes/${encodeURIComponent(config.homeId)}/sensors/${encodeURIComponent(target.dataset.rotateSensor)}/rotate-key`, { method: "POST", body: "{}" });
        showMessage(`Copy the new device key now. It cannot be retrieved again: ${result.device_key}`);
      });
      if (target.dataset.revokeSensor && window.confirm("Revoke this sensor? It will no longer be able to submit readings.")) {
        runAction(async () => {
          await api(`/api/homes/${encodeURIComponent(config.homeId)}/sensors/${encodeURIComponent(target.dataset.revokeSensor)}/revoke`, { method: "POST", body: "{}" });
          await loadHome();
          showMessage("Sensor revoked.");
        });
      }
      if (target.dataset.scenario) runAction(() => runScenario(target.dataset.scenario));
      if (target.id === "run-dalton-replay") runAction(runDaltonReplay);
      if (target.id === "mobile-menu") {
        const isOpen = $(".sidebar").classList.toggle("mobile-open");
        target.setAttribute("aria-expanded", String(isOpen));
      }
      if (target.id === "banner-dismiss") $(".prototype-banner").hidden = true;
    });

    document.addEventListener("submit", event => {
      const form = event.target;
      if (form.id === "room-form") {
        event.preventDefault();
        runAction(() => createRoom(form));
      } else if (form.id === "sensor-form") {
        event.preventDefault();
        runAction(() => provisionSensor(form));
      } else if (form.id === "invite-form") {
        event.preventDefault();
        runAction(() => inviteMember(form));
      } else if (form.matches("[data-ack]")) {
        event.preventDefault();
        runAction(async () => {
          await api(`/api/alerts/${encodeURIComponent(form.dataset.ack)}/acknowledge`, { method: "POST", body: "{}" });
          await loadHome();
          showMessage("Alert acknowledged.");
        });
      }
    });

    $("#home-picker").addEventListener("change", event => runAction(async () => {
      await api("/api/active-home", {
        method: "POST",
        body: JSON.stringify({ home_id: event.target.value })
      });
      window.location.assign(`/alerts?home_id=${encodeURIComponent(event.target.value)}`);
    }));
    $("#sign-out").addEventListener("click", () => runAction(async () => {
      await api("/api/auth/logout", { method: "POST", body: "{}" });
      window.location.assign("/login");
    }));
    $("#room-filters").addEventListener("click", event => {
      if (event.target.closest("[data-filter]")) renderRooms();
    });
    $$("#room-form input[name=ventilation_sources]").forEach(input => {
      input.addEventListener("change", () => {
        if (!input.checked) return;
        const notSpecified = $('#room-form input[value="Not specified"]');
        if (input.value === "Not specified") {
          $$("#room-form input[name=ventilation_sources]").forEach(option => {
            if (option !== input) option.checked = false;
          });
        } else if (notSpecified) {
          notSpecified.checked = false;
        }
      });
    });
    $("#sensor-search").addEventListener("input", event => renderSensors(event.target.value));
    $("#history-room").addEventListener("change", loadHistory);
    $("#history-metric").addEventListener("change", loadHistory);
    $("#history-range").addEventListener("change", loadHistory);
    $("#export-csv").addEventListener("click", () => {
      const roomId = $("#history-room").value;
      if (!roomId) return showMessage("Select a room before exporting history.", "error");
      const end = new Date();
      const start = new Date(end.getTime() - Number($("#history-range").value || 30) * 86400000);
      const params = new URLSearchParams({
        room_id: roomId,
        metric: $("#history-metric").value || "CO2",
        from: start.toISOString(),
        to: end.toISOString(),
        limit: "10000"
      });
      window.location.assign(`/api/homes/${encodeURIComponent(config.homeId)}/history.csv?${params}`);
    });
    $("#save-thresholds").addEventListener("click", () => runAction(saveThresholds));
    $("#rotation-button").addEventListener("click", event => {
      const button = event.currentTarget;
      if (metricTimer) {
        clearInterval(metricTimer);
        metricTimer = null;
        button.textContent = "Ⅱ";
        button.setAttribute("aria-label", "Pause metric rotation");
        button.setAttribute("aria-pressed", "false");
      } else {
        metricTimer = window.setInterval(() => {
          const keys = Object.keys(metrics).filter(key => rooms.some(room => latestReading(room, key)));
          if (!keys.length) return;
          selectedMetric = keys[(keys.indexOf(selectedMetric) + 1) % keys.length];
          renderChart();
        }, 4000);
        button.textContent = "▶";
        button.setAttribute("aria-label", "Resume metric rotation");
        button.setAttribute("aria-pressed", "true");
      }
    });
  }

  async function loadMembers() {
    const result = await api(`/api/homes/${encodeURIComponent(config.homeId)}/members`);
    members = result.members;
    renderMembers();
  }

  async function saveThresholds() {
    const rows = $$("#threshold-table-body tr[data-room-id]");
    if (!rows.length) return showMessage("Add a room before setting thresholds.", "error");
    const allClearSeconds = Number($("#clear-duration").value) * 60;
    const maxGapSeconds = Number($("#sample-gap").value) * 60;
    const updates = rows.map(row => {
      const values = Object.fromEntries($$("[data-threshold]", row).map(input => [input.dataset.threshold, Number(input.value)]));
      if (Object.values(values).some(value => !Number.isFinite(value) || value <= 0) || values.elevated_threshold >= values.high_threshold) {
        throw new Error(`Enter valid positive values for ${row.querySelector("strong").textContent}; elevated must be lower than high.`);
      }
      return {
        room_id: row.dataset.roomId,
        ...values,
        elevated_duration_seconds: values.elevated_duration_seconds * 60,
        all_clear_duration_seconds: allClearSeconds,
        max_reading_gap_seconds: maxGapSeconds
      };
    });
    await api(`/api/homes/${encodeURIComponent(config.homeId)}/thresholds`, {
      method: "PUT",
      body: JSON.stringify({ thresholds: updates })
    });
    const result = await api(`/api/homes/${encodeURIComponent(config.homeId)}/thresholds`);
    thresholds = result.thresholds;
    renderThresholds();
    await loadActivity();
    showMessage("Thresholds saved for this home.");
  }

  async function runScenario(scenario) {
    const room = rooms.find(item => item.name.toLowerCase() === "bedroom") || rooms[0];
    if (!room) throw new Error("Add a room before submitting a simulated reading.");
    const scenarios = new Set(["high", "elevated", "rapid", "clear"]);
    if (!scenarios.has(scenario)) throw new Error("Unknown simulator scenario.");
    await api(`/api/homes/${encodeURIComponent(config.homeId)}/demo/readings`, {
      method: "POST",
      body: JSON.stringify({ room_id: room.id, scenario, metric: "CO2", unit: "ppm" })
    });
    await loadHome();
    showView("alerts");
    showMessage("Simulated reading sent through the server alert pipeline.");
  }

  async function runDaltonReplay() {
    const room = rooms.find(item => item.name.toLowerCase() === "bedroom") || rooms[0];
    if (!room) throw new Error("Add a room before replaying DALTON data.");
    const csvPath = $("#dalton-csv-path").value.trim();
    if (!csvPath) throw new Error("Enter a path to a DALTON CSV file before replaying.");
    const limit = Number($("#dalton-limit").value || 250);
    const result = await api(`/api/homes/${encodeURIComponent(config.homeId)}/demo/replay`, {
      method: "POST",
      body: JSON.stringify({ room_id: room.id, csv_path: csvPath, limit, valid_co2_only: true })
    });
    await loadHome();
    showView("alerts");
    showMessage(`Imported ${result.imported} DALTON reading${result.imported === 1 ? "" : "s"} from ${result.source_file}.`);
  }

  async function init() {
    $("#history-metric").innerHTML = Object.entries(metrics).map(([key, metric]) => `<option value="${key}">${metric.label}</option>`).join("");
    bindEvents();
    try {
      await loadHome();
      await Promise.all([loadMembers(), config.role === "owner" ? loadActivity() : Promise.resolve()]);
    } catch (error) {
      showMessage(error.message || "Unable to load home data.", "error");
    }
  }

  document.addEventListener("DOMContentLoaded", init);
})();
