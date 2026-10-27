(() => {
  const body = document.body;
  const apiTokenRequired = body.dataset.apiTokenRequired === "true";
  const tokenStorageKey = "airsenseApiToken";
  let apiToken = apiTokenRequired ? sessionStorage.getItem(tokenStorageKey) || "" : "";
  let dashboard = { readings: [], alerts: [] };
  let selectedMetric = "";
  let rotationPaused = false;
  let metricRotationTimer;

  const elements = {
    connection: document.getElementById("connection-state"),
    error: document.getElementById("error-message"),
    success: document.getElementById("success-message"),
    tokenPanel: document.getElementById("token-panel"),
    tokenForm: document.getElementById("token-form"),
    tokenInput: document.getElementById("api-token"),
    homeForm: document.getElementById("home-form"),
    homeId: document.getElementById("home-id"),
    refresh: document.getElementById("refresh-button"),
    roomCount: document.getElementById("room-count"),
    roomCountLabel: document.getElementById("room-count-label"),
    openAlertCount: document.getElementById("open-alert-count"),
    latestReport: document.getElementById("latest-report"),
    lastUpdated: document.getElementById("last-updated"),
    lastRefresh: document.getElementById("last-refresh"),
    metricTabs: document.getElementById("metric-tabs"),
    chart: document.getElementById("room-chart"),
    chartEmpty: document.getElementById("chart-empty"),
    chartUpdated: document.getElementById("chart-updated"),
    rotation: document.getElementById("rotation-button"),
    roomGrid: document.getElementById("room-grid"),
    readingForm: document.getElementById("reading-form"),
    policyForm: document.getElementById("policy-form"),
    alertList: document.getElementById("alert-list"),
  };

  const sourceNames = {
    dataset: "Recorded Data: Replay",
    simulated: "Simulated Data",
    device: "Live Sensor",
  };
  const levelNames = {
    high: "High",
    elevated: "Elevated",
    rapid_rise: "Rapid rise",
  };
  const levelOrder = { high: 0, elevated: 1, rapid_rise: 2 };

  function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>"']/g, (character) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    })[character]);
  }

  function showError(message) {
    elements.error.textContent = message;
    elements.error.hidden = false;
    elements.success.hidden = true;
  }

  function showSuccess(message) {
    elements.success.textContent = message;
    elements.success.hidden = false;
    elements.error.hidden = true;
    window.setTimeout(() => {
      elements.success.hidden = true;
    }, 4000);
  }

  function setConnection(online, label) {
    elements.connection.classList.toggle("is-online", online);
    elements.connection.classList.toggle("is-offline", !online);
    elements.connection.lastChild.textContent = ` ${label}`;
  }

  function currentHomeId() {
    return elements.homeId.value.trim();
  }

  function setTokenPanelVisible(visible) {
    if (elements.tokenPanel) {
      elements.tokenPanel.hidden = !visible;
    }
  }

  async function apiRequest(path, options = {}) {
    const headers = new Headers(options.headers || {});
    if (options.body && !headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }
    if (apiTokenRequired && apiToken) {
      headers.set("Authorization", `Bearer ${apiToken}`);
    }
    const response = await fetch(path, {
      ...options,
      headers,
      cache: "no-store",
    });
    const result = await response.json();
    if (!response.ok) {
      if (response.status === 401 && apiTokenRequired) {
        setTokenPanelVisible(true);
      }
      throw new Error(result.error || `Request failed (${response.status}).`);
    }
    return result;
  }

  function relativeAge(timestamp) {
    const milliseconds = Date.parse(timestamp);
    if (!Number.isFinite(milliseconds)) return "time unavailable";
    const seconds = Math.max(0, Math.floor((Date.now() - milliseconds) / 1000));
    if (seconds < 60) return `${seconds}s ago`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
    return `${Math.floor(seconds / 86400)}d ago`;
  }

  function sourceClass(source) {
    return `source-${source === "dataset" ? "dataset" : source === "device" ? "device" : "simulated"}`;
  }

  function readingsForMetric() {
    return dashboard.readings
      .filter((reading) => reading.metric === selectedMetric)
      .sort((left, right) => left.room.localeCompare(right.room));
  }

  function renderMetricTabs() {
    const metrics = [...new Set(dashboard.readings.map((reading) => reading.metric))].sort();
    if (!metrics.includes(selectedMetric)) selectedMetric = metrics[0] || "";
    elements.metricTabs.innerHTML = metrics.map((metric) => {
      const metricName = dashboard.readings.find((reading) => reading.metric === metric)?.metric_name || metric;
      return `<button class="metric-tab" type="button" role="tab" data-metric="${escapeHtml(metric)}" aria-selected="${metric === selectedMetric}">${escapeHtml(metricName)}</button>`;
    }).join("");
    elements.metricTabs.querySelectorAll("[data-metric]").forEach((tab) => {
      tab.addEventListener("click", () => {
        selectedMetric = tab.dataset.metric;
        rotationPaused = true;
        updateRotationButton();
        renderMetricTabs();
        renderChart();
      });
    });
  }

  function renderChart() {
    const readings = readingsForMetric();
    elements.chart.replaceChildren();
    elements.chartEmpty.hidden = readings.length > 0;
    elements.chartEmpty.textContent = dashboard.readings.length
      ? "No readings for this metric yet."
      : "No readings yet. Record a sample or connect a data replay.";
    if (!readings.length) return;

    const maximum = Math.max(...readings.map((reading) => Number(reading.value)), 1);
    for (const reading of readings) {
      const row = document.createElement("div");
      row.className = "bar-row";
      const percent = Math.max(2, (Number(reading.value) / maximum) * 100);
      row.innerHTML = `
        <span class="bar-room">${escapeHtml(reading.room)}</span>
        <span class="bar-track" aria-hidden="true"><span class="bar-fill" style="width:${percent}%"></span></span>
        <span class="bar-value">${escapeHtml(reading.value)} ${escapeHtml(reading.unit)}</span>`;
      row.setAttribute("aria-label", `${reading.room}: ${reading.value} ${reading.unit}`);
      elements.chart.append(row);
    }
  }

  function alertsForRoom(roomName) {
    return dashboard.alerts.filter((alert) => alert.room === roomName);
  }

  function highestOpenAlert(alerts) {
    return alerts
      .filter((alert) => alert.status === "active" || alert.status === "acknowledged")
      .sort((left, right) => (levelOrder[left.level] ?? 9) - (levelOrder[right.level] ?? 9))[0];
  }

  function roomStatus(alerts) {
    const openAlert = highestOpenAlert(alerts);
    if (openAlert) {
      const label = levelNames[openAlert.level] || "Alert";
      return {
        label: openAlert.status === "acknowledged" ? `${label} · Acknowledged` : label,
        className: openAlert.level === "rapid_rise" ? "status-rapid-rise" : "status-elevated",
      };
    }
    if (alerts.some((alert) => alert.status === "all_clear")) {
      return { label: "All clear", className: "status-all-clear" };
    }
    return { label: "No open alerts", className: "status-none" };
  }

  function renderRooms() {
    const rooms = new Map();
    for (const reading of dashboard.readings) {
      if (!rooms.has(reading.room)) rooms.set(reading.room, []);
      rooms.get(reading.room).push(reading);
    }
    for (const alert of dashboard.alerts) {
      if (!rooms.has(alert.room)) rooms.set(alert.room, []);
    }
    const entries = [...rooms.entries()].sort(([left], [right]) => left.localeCompare(right));
    elements.roomCount.textContent = String(entries.length);
    elements.roomCountLabel.textContent = `${entries.length} room${entries.length === 1 ? "" : "s"} · refreshes every 20 seconds`;

    if (!entries.length) {
      elements.roomGrid.innerHTML = '<p class="empty-state">No rooms are reporting yet.</p>';
      return;
    }

    elements.roomGrid.innerHTML = entries.map(([roomName, roomReadings]) => {
      const alerts = alertsForRoom(roomName);
      const status = roomStatus(alerts);
      const openAlerts = alerts.filter((alert) => alert.status === "active" || alert.status === "acknowledged");
      const readingsMarkup = roomReadings
        .sort((left, right) => left.metric.localeCompare(right.metric))
        .map((reading) => {
          const trend = reading.trend || "unavailable";
          const trendLabel = trend === "rising"
            ? `↑ Rising${reading.change === null ? "" : ` ${escapeHtml(Math.abs(reading.change))}`}`
            : trend === "falling"
              ? `↓ Falling${reading.change === null ? "" : ` ${escapeHtml(Math.abs(reading.change))}`}`
              : trend === "steady" ? "→ Steady" : "Trend unavailable";
          return `
            <div class="reading-line">
              <span class="reading-name">${escapeHtml(reading.metric_name || reading.metric)}</span>
              <strong class="reading-value">${escapeHtml(reading.value)}<span class="reading-unit">${escapeHtml(reading.unit)}</span></strong>
            </div>
            <div class="reading-details">
              <span class="source-pill ${sourceClass(reading.source)}">${escapeHtml(sourceNames[reading.source] || reading.source)}</span>
              <span class="trend trend-${escapeHtml(trend)}">${trendLabel}</span>
            </div>
            <div class="reading-age" data-measured-at="${escapeHtml(reading.measured_at)}">Reported ${escapeHtml(relativeAge(reading.measured_at))}</div>`;
        }).join("");
      const alertMarkup = openAlerts.map((alert) => `
        <div class="room-alert">${escapeHtml(levelNames[alert.level] || "Alert")}: ${escapeHtml(alert.detail)}</div>`).join("");
      return `
        <article class="room-card">
          <div class="room-card-header">
            <div>
              <h3 class="room-name">${escapeHtml(roomName)}</h3>
              <p class="room-meta">${roomReadings.length} metric${roomReadings.length === 1 ? "" : "s"} reporting</p>
            </div>
            <span class="status-pill ${status.className}">${escapeHtml(status.label)}</span>
          </div>
          <div class="reading-list">${readingsMarkup || '<p class="field-help">No reading recorded for this room yet.</p>'}</div>
          ${alertMarkup ? `<div class="room-alerts">${alertMarkup}</div>` : ""}
        </article>`;
    }).join("");
  }

  function renderAlerts() {
    const alerts = dashboard.alerts;
    if (!alerts.length) {
      elements.alertList.innerHTML = '<p class="empty-state">No alerts recorded.</p>';
      return;
    }

    elements.alertList.innerHTML = alerts.map((alert) => {
      const levelClass = alert.status === "all_clear"
        ? "status-all-clear"
        : alert.level === "rapid_rise" ? "status-rapid-rise" : "status-elevated";
      const statusText = alert.status === "all_clear"
        ? `All clear at ${escapeHtml(relativeAge(alert.all_clear_at))}`
        : alert.status === "acknowledged"
          ? `Acknowledged by ${escapeHtml(alert.acknowledged_by)}`
          : "Needs acknowledgement";
      const acknowledgementForm = alert.status === "active"
        ? `<form class="ack-form" data-alert-id="${escapeHtml(alert.id)}">
             <input name="acknowledged_by" maxlength="120" aria-label="Acknowledged by" placeholder="Your name" required>
             <button class="button button-dark" type="submit">Acknowledge</button>
           </form>`
        : "";
      return `
        <article class="alert-item">
          <div>
            <span class="alert-room">${escapeHtml(alert.room)}</span>
            <span class="alert-metric">${escapeHtml(alert.metric_name || alert.metric)} · ${escapeHtml(alert.level === "rapid_rise" ? `${alert.latest_value} ${alert.threshold_unit}` : `${alert.latest_value} ${alert.threshold_unit}`)}</span>
          </div>
          <span class="status-pill ${levelClass}">${escapeHtml(levelNames[alert.level] || "Alert")}</span>
          <span class="alert-description">${escapeHtml(alert.detail)}<br><span class="alert-status">${statusText}</span></span>
          ${acknowledgementForm}
        </article>`;
    }).join("");
    elements.alertList.querySelectorAll(".ack-form").forEach((form) => {
      form.addEventListener("submit", acknowledgeAlert);
    });
  }

  function updateRotationButton() {
    elements.rotation.textContent = rotationPaused ? "Resume rotation" : "Pause rotation";
    elements.rotation.setAttribute("aria-pressed", String(rotationPaused));
  }

  function startMetricRotation() {
    window.clearInterval(metricRotationTimer);
    metricRotationTimer = window.setInterval(() => {
      const metrics = [...new Set(dashboard.readings.map((reading) => reading.metric))];
      if (rotationPaused || metrics.length < 2) return;
      const currentIndex = metrics.indexOf(selectedMetric);
      selectedMetric = metrics[(currentIndex + 1) % metrics.length];
      renderMetricTabs();
      renderChart();
    }, 8000);
  }

  function renderDashboard() {
    renderMetricTabs();
    renderChart();
    renderRooms();
    renderAlerts();

    const openAlerts = dashboard.alerts.filter((alert) => alert.status === "active" || alert.status === "acknowledged");
    elements.openAlertCount.textContent = String(openAlerts.length);
    const latest = [...dashboard.readings].sort(
      (left, right) => Date.parse(right.measured_at) - Date.parse(left.measured_at),
    )[0];
    elements.latestReport.textContent = latest
      ? `${latest.room} · ${latest.value} ${latest.unit}`
      : "Waiting for data";
    elements.lastUpdated.textContent = latest
      ? `Most recent sample reported ${relativeAge(latest.measured_at)}`
      : "Dashboard refreshes every 20 seconds";
    elements.chartUpdated.textContent = latest
      ? `Latest sample ${relativeAge(latest.measured_at)}`
      : "Waiting for data";
    elements.lastRefresh.textContent = `Dashboard checked ${new Date().toLocaleTimeString()}`;
    startMetricRotation();
  }

  async function loadDashboard() {
    if (apiTokenRequired && !apiToken) {
      setConnection(false, "API token required");
      setTokenPanelVisible(true);
      return;
    }
    const homeId = currentHomeId();
    if (!homeId) {
      showError("Enter a home ID to load its demo readings.");
      return;
    }
    try {
      const result = await apiRequest(`/api/dashboard?home_id=${encodeURIComponent(homeId)}`);
      dashboard = result;
      setConnection(true, "Connected");
      setTokenPanelVisible(false);
      elements.error.hidden = true;
      renderDashboard();
    } catch (error) {
      setConnection(false, "Connection issue");
      showError(error instanceof Error ? error.message : "The dashboard could not be loaded.");
    }
  }

  async function acknowledgeAlert(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const alertId = form.dataset.alertId;
    const acknowledgedBy = new FormData(form).get("acknowledged_by");
    try {
      await apiRequest(`/api/alerts/${encodeURIComponent(alertId)}/acknowledge`, {
        method: "POST",
        body: JSON.stringify({ acknowledged_by: acknowledgedBy }),
      });
      showSuccess("Alert acknowledgement recorded.");
      await loadDashboard();
    } catch (error) {
      showError(error instanceof Error ? error.message : "The alert could not be acknowledged.");
    }
  }

  elements.refresh.addEventListener("click", loadDashboard);
  elements.homeForm.addEventListener("submit", (event) => {
    event.preventDefault();
    loadDashboard();
  });
  elements.rotation.addEventListener("click", () => {
    rotationPaused = !rotationPaused;
    updateRotationButton();
  });

  elements.readingForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const values = new FormData(elements.readingForm);
    const payload = {
      home_id: currentHomeId(),
      home_name: "Demo Home",
      room: values.get("room"),
      metric: "CO2",
      unit: "ppm",
      value: Number(values.get("value")),
      source: values.get("source"),
    };
    try {
      const result = await apiRequest("/api/readings", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      elements.policyForm.elements.room.value = payload.room;
      showSuccess(
        result.created.length
          ? `Reading saved; ${result.created.length} alert opened.`
          : result.cleared.length
            ? `Reading saved; ${result.cleared.length} alert(s) moved to all clear.`
            : "Reading saved. No alert state changed.",
      );
      elements.readingForm.elements.value.value = "";
      await loadDashboard();
    } catch (error) {
      showError(error instanceof Error ? error.message : "The reading could not be saved.");
    }
  });

  elements.policyForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const values = new FormData(elements.policyForm);
    const payload = {
      home_id: currentHomeId(),
      home_name: "Demo Home",
      room: values.get("room"),
      metric: "CO2",
      unit: "ppm",
      high_threshold: Number(values.get("high_threshold")),
      elevated_threshold: Number(values.get("elevated_threshold")),
      elevated_duration_seconds: Number(values.get("elevated_duration_seconds")),
      rapid_rise_per_minute: Number(values.get("rapid_rise_per_minute")),
      all_clear_duration_seconds: Number(values.get("all_clear_duration_seconds")),
      max_reading_gap_seconds: Number(values.get("max_reading_gap_seconds")),
    };
    if (payload.high_threshold <= payload.elevated_threshold) {
      showError("The High threshold must be greater than the Elevated threshold.");
      return;
    }
    try {
      await apiRequest("/api/policies", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      showSuccess(`CO₂ thresholds saved for ${payload.room}.`);
      await loadDashboard();
    } catch (error) {
      showError(error instanceof Error ? error.message : "Thresholds could not be saved.");
    }
  });

  if (elements.tokenForm) {
    elements.tokenForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      apiToken = elements.tokenInput.value;
      sessionStorage.setItem(tokenStorageKey, apiToken);
      await loadDashboard();
    });
  }

  document.getElementById("high-threshold").value = body.dataset.highThreshold;
  document.getElementById("elevated-threshold").value = body.dataset.elevatedThreshold;
  elements.homeId.value = body.dataset.homeId;
  setTokenPanelVisible(apiTokenRequired && !apiToken);
  updateRotationButton();
  loadDashboard();
  window.setInterval(loadDashboard, 20_000);
  window.setInterval(() => {
    document.querySelectorAll(".reading-age").forEach((element) => {
      element.textContent = `Reported ${relativeAge(element.dataset.measuredAt)}`;
    });
  }, 15_000);
})();
