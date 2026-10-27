(() => {
  "use strict";

  const rooms = [
    { name: "Living room", ventilation: "Window", co2: 780, temperature: 23.4, humidity: 46, threshold: 1000, high: 1500, rise: 500 },
    { name: "Bedroom", ventilation: "Window", co2: 1180, temperature: 24.1, humidity: 51, threshold: 1000, high: 1500, rise: 500 },
    { name: "Kitchen", ventilation: "Exhaust fan", co2: 1420, temperature: 25.8, humidity: 57, threshold: 1000, high: 1500, rise: 500 },
    { name: "Study", ventilation: "Window", co2: 890, temperature: 22.7, humidity: 43, threshold: 1000, high: 1500, rise: 500 }
  ];
  const metrics = {
    CO2: { label: "CO₂", unit: "ppm", key: "co2", max: 1800 },
    temperature: { label: "Temperature", unit: "°C", key: "temperature", max: 32 },
    humidity: { label: "Humidity", unit: "%", key: "humidity", max: 80 }
  };
  const sensors = [
    { name: "Living room monitor", room: "Living room", active: true },
    { name: "Bedroom monitor", room: "Bedroom", active: true },
    { name: "Kitchen monitor", room: "Kitchen", active: true },
    { name: "Study monitor", room: "Study", active: false }
  ];
  const members = [
    { name: "Meera Sharma", email: "meera@example.test", role: "Owner", joined: "Today" },
    { name: "Arjun Sharma", email: "arjun@example.test", role: "Member", joined: "12 Oct" }
  ];
  const alerts = [
    { id: 1, room: "Bedroom", kind: "elevated", value: 1180, status: "open", time: "8:42 PM", text: "Sample CO₂ reading is above the illustrative elevated level." },
    { id: 2, room: "Kitchen", kind: "high", value: 1420, status: "open", time: "8:35 PM", text: "Sample CO₂ reading is approaching the illustrative high level." },
    { id: 3, room: "Living room", kind: "rapid-rise", value: 780, status: "acknowledged", time: "7:18 PM", text: "A sample reading increased quickly. Acknowledged by Meera." },
    { id: 4, room: "Study", kind: "all-clear", value: 890, status: "all_clear", time: "6:50 PM", text: "Sample readings returned below the illustrative threshold." }
  ];
  const activity = [
    { kind: "sensor", event: "Sensor status changed", who: "Meera Sharma", when: "Today, 8:10 PM", details: "Study monitor marked inactive" },
    { kind: "threshold", event: "Threshold updated", who: "Meera Sharma", when: "Today, 7:55 PM", details: "Bedroom CO₂ demo rule" },
    { kind: "member", event: "Member added", who: "Meera Sharma", when: "12 Oct, 10:20 AM", details: "Arjun Sharma joined this preview" }
  ];
  let selectedMetric = "CO2";
  let roomFilter = "all";
  let alertFilter = "all";
  let metricTimer = null;

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));
  const escapeHtml = value => String(value).replace(/[&<>"']/g, char => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  })[char]);
  const format = (value, digits = 0) => Number(value).toLocaleString(undefined, { maximumFractionDigits: digits });
  const roomStatus = room => alerts.some(alert => alert.room === room.name && alert.status === "open")
    ? (alerts.find(alert => alert.room === room.name && alert.status === "open").kind)
    : "none";
  const statusText = status => ({ none: "Looks good", high: "High sample", elevated: "Elevated sample", "rapid-rise": "Rapid rise", "all-clear": "All clear" })[status] || "Needs a look";

  function showView(name) {
    $$("[data-view]").forEach(view => view.classList.toggle("active", view.dataset.view === name));
    $$("[data-nav]").forEach(button => button.classList.toggle("active", button.dataset.nav === name));
    const heading = $(`[data-view="${name}"] h1`);
    $("#breadcrumb-current").textContent = heading ? heading.textContent.trim() : "Overview";
    $(".sidebar").classList.remove("mobile-open");
    $("#mobile-menu").setAttribute("aria-expanded", "false");
    window.scrollTo({ top: 0, behavior: "smooth" });
    if (name === "history") renderHistory();
  }

  function roomCard(room) {
    const state = roomStatus(room);
    return `<article class="room-card"><div class="room-card-header"><div><h3 class="room-name">${escapeHtml(room.name)}</h3><p class="room-meta">${escapeHtml(room.ventilation)} · sample setup</p></div><span class="status-pill status-${state}">${statusText(state)}</span></div><div class="reading-list">${Object.entries(metrics).map(([key, metric]) => `<div class="reading-line"><span class="reading-name">${metric.label}</span><strong class="reading-value">${format(room[metric.key], key === "temperature" ? 1 : 0)}<span class="reading-unit">${metric.unit}</span></strong></div>`).join("")}</div><div class="reading-details"><span class="source-pill source-simulated">Illustrative sample</span><span class="reading-age">Not live</span></div></article>`;
  }

  function renderRooms() {
    $("#room-grid").innerHTML = rooms.slice(0, 3).map(roomCard).join("");
    const filtered = rooms.filter(room => roomFilter === "all" || roomStatus(room) !== "none");
    $("#all-room-grid").innerHTML = filtered.length ? filtered.map(roomCard).join("") : '<p class="empty-state">No rooms match this filter.</p>';
    $("#room-count").innerHTML = `${rooms.length}<span class="summary-denom"> / ${rooms.length}</span>`;
    const attention = rooms.filter(room => roomStatus(room) !== "none").length;
    $(".mini-room-status").innerHTML = `<span class="mini-status-dot good"></span>${rooms.length - attention} look good <span class="mini-status-dot attention"></span>${attention} need a look`;
    $(".snapshot-footer span:first-child strong").textContent = `${rooms.length} rooms`;
    $$("#room-filters [data-filter]").forEach(button => {
      button.innerHTML = `${button.dataset.filter === "all" ? "All rooms" : "Needs a look"} <span>${button.dataset.filter === "all" ? rooms.length : rooms.filter(room => roomStatus(room) !== "none").length}</span>`;
      button.classList.toggle("selected", button.dataset.filter === roomFilter);
    });
  }

  function renderChart() {
    const metric = metrics[selectedMetric];
    $("#metric-tabs").innerHTML = Object.entries(metrics).map(([key, item]) => `<button class="metric-tab" type="button" role="tab" aria-selected="${key === selectedMetric}" data-metric="${key}">${item.label}</button>`).join("");
    $("#room-chart").innerHTML = rooms.map(room => {
      const value = Number(room[metric.key]);
      return `<div class="bar-row"><span class="bar-room">${escapeHtml(room.name)}</span><div class="bar-track"><div class="bar-fill" style="width:${Math.min(100, Math.max(2, value / metric.max * 100))}%"></div></div><span class="bar-value">${format(value, selectedMetric === "temperature" ? 1 : 0)} ${metric.unit}</span></div>`;
    }).join("");
  }

  function renderAlerts() {
    const open = alerts.filter(alert => alert.status === "open").length;
    $("#nav-alert-count").textContent = open;
    $("#open-alert-count").textContent = open;
    $("#alert-open-stat").textContent = open;
    $("#alert-ack-stat").textContent = alerts.filter(alert => alert.status === "acknowledged").length;
    $("#alert-clear-stat").textContent = alerts.filter(alert => alert.status === "all_clear").length;
    const items = alertFilter === "all" ? alerts : alerts.filter(alert => alert.status === alertFilter);
    $("#alert-list").innerHTML = items.map(alert => `<article class="alert-item"><div><span class="status-pill status-${alert.kind}">${statusText(alert.kind)}</span><div class="alert-room">${escapeHtml(alert.room)}<span class="alert-metric">CO₂ · ${format(alert.value)} ppm · sample</span></div></div><span class="alert-status">${alert.status === "open" ? "Open" : alert.status === "acknowledged" ? "Acknowledged" : "All clear"} · ${escapeHtml(alert.time)}</span><div class="alert-description">${escapeHtml(alert.text)}</div>${alert.status === "open" ? `<form class="ack-form" data-ack="${alert.id}"><input name="name" aria-label="Acknowledged by" placeholder="Your name" value="Meera"><button class="button button-outline" type="submit">Acknowledge</button></form>` : '<span class="muted">Preview state</span>'}</article>`).join("") || '<p class="empty-state">No sample alerts in this view.</p>';
    $("#overview-alerts").innerHTML = alerts.filter(alert => alert.status === "open").slice(0, 2).map(alert => `<div class="preview-alert"><span class="status-pill status-${alert.kind}">${statusText(alert.kind)}</span><strong>${escapeHtml(alert.room)}</strong><span>${format(alert.value)} ppm · sample</span></div>`).join("") || '<p class="empty-state">No open sample alerts.</p>';
  }

  function renderSensors(query = "") {
    const filtered = sensors.filter(sensor => `${sensor.name} ${sensor.room}`.toLowerCase().includes(query.toLowerCase()));
    $("#sensor-count").textContent = `${sensors.length} devices`;
    $("#sensor-table-body").innerHTML = filtered.map((sensor, index) => `<tr><td><strong>${escapeHtml(sensor.name)}</strong><small>Sample device ${index + 1}</small></td><td>${escapeHtml(sensor.room)}</td><td><span class="source-pill source-simulated">Illustrative</span></td><td>Today · sample</td><td><span class="status-pill ${sensor.active ? "status-none" : "status-elevated"}">${sensor.active ? "Active preview" : "Inactive preview"}</span></td><td><button class="text-button" type="button" data-toggle-sensor="${sensors.indexOf(sensor)}">${sensor.active ? "Pause" : "Resume"}</button></td></tr>`).join("") || '<tr><td colspan="6">No matching sample devices.</td></tr>';
  }

  function renderThresholds() {
    $("#threshold-table-body").innerHTML = rooms.map((room, index) => `<tr><td><strong>${escapeHtml(room.name)}</strong></td><td><input aria-label="${escapeHtml(room.name)} elevated threshold" type="number" min="1" data-room="${index}" data-threshold="threshold" value="${room.threshold}"></td><td><input aria-label="${escapeHtml(room.name)} high threshold" type="number" min="1" data-room="${index}" data-threshold="high" value="${room.high}"></td><td><input aria-label="${escapeHtml(room.name)} elevated duration" type="number" min="1" data-room="${index}" data-threshold="duration" value="${room.duration || 5}"> min</td><td><input aria-label="${escapeHtml(room.name)} rapid rise" type="number" min="1" data-room="${index}" data-threshold="rise" value="${room.rise}"> ppm</td></tr>`).join("");
  }

  function renderMembers() {
    $("#member-table-body").innerHTML = members.map((member, index) => `<tr><td><strong>${escapeHtml(member.name)}</strong><small>${escapeHtml(member.email)}</small></td><td><span class="role-pill">${escapeHtml(member.role)}</span></td><td>${escapeHtml(member.joined)}</td><td>${member.role === "Owner" ? "" : `<button class="text-button" type="button" data-remove-member="${index}">Remove</button>`}</td></tr>`).join("");
  }

  function renderActivity() {
    const filter = $("#activity-filter").value;
    const items = activity.filter(item => filter === "all" || item.kind === filter);
    $("#activity-table-body").innerHTML = items.map(item => `<tr><td><strong>${escapeHtml(item.event)}</strong></td><td>${escapeHtml(item.who)}</td><td>${escapeHtml(item.when)}</td><td>${escapeHtml(item.details)}</td></tr>`).join("");
  }

  function renderHistory() {
    const room = rooms.find(item => item.name === $("#history-room").value) || rooms[0];
    const key = $("#history-metric").value || "CO2";
    const metric = metrics[key];
    const days = Number($("#history-range").value || 30);
    const center = Number(room[metric.key]);
    $("#history-series-title").textContent = `${room.name} · ${metric.label}`;
    $("#history-current-value").innerHTML = `${format(center, key === "temperature" ? 1 : 0)} <small>${metric.unit}</small>`;
    const now = new Date();
    const dates = Array.from({ length: days }, (_, index) => {
      const date = new Date(now.getFullYear(), now.getMonth(), now.getDate() - days + index + 1);
      return { date, value: center * (0.76 + ((index * 37 + Math.round(center)) % 42) / 100) };
    });
    const svg = $("#history-chart");
    const width = 1000;
    const height = 320;
    const left = 64;
    const right = 18;
    const top = 18;
    const bottom = 54;
    const plotWidth = width - left - right;
    const plotHeight = height - top - bottom;
    const step = plotWidth / days;
    const barWidth = Math.max(2, Math.min(20, step * 0.66));
    const tickIndexes = Array.from(new Set([0, Math.round((days - 1) / 4), Math.round((days - 1) / 2), Math.round((days - 1) * 3 / 4), days - 1]));
    const grid = [0, 0.25, 0.5, 0.75, 1].map(fraction => {
      const y = top + plotHeight * (1 - fraction);
      const value = metric.max * fraction;
      return `<line class="history-gridline" x1="${left}" y1="${y}" x2="${width - right}" y2="${y}"/><text class="history-y-label" x="${left - 10}" y="${y + 4}" text-anchor="end">${format(value, key === "temperature" ? 0 : 0)}</text>`;
    }).join("");
    const bars = dates.map((item, index) => {
      const barHeight = Math.max(2, Math.min(plotHeight, item.value / metric.max * plotHeight));
      const x = left + index * step + (step - barWidth) / 2;
      const y = top + plotHeight - barHeight;
      const dateLabel = item.date.toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric", year: "numeric" });
      return `<rect class="history-bar" x="${x.toFixed(2)}" y="${y.toFixed(2)}" width="${barWidth.toFixed(2)}" height="${barHeight.toFixed(2)}" rx="${Math.min(4, barWidth / 3)}"><title>${dateLabel}: ${format(item.value, key === "temperature" ? 1 : 0)} ${metric.unit} · illustrative sample</title></rect>`;
    }).join("");
    const dateTicks = tickIndexes.map(index => {
      const item = dates[index];
      const x = left + index * step + step / 2;
      const label = item.date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
      return `<text class="history-date-label" x="${x.toFixed(2)}" y="${height - 16}" text-anchor="middle">${label}</text>`;
    }).join("");
    svg.setAttribute("aria-label", `Daily illustrative ${metric.label} readings in ${room.name} for the last ${days} days`);
    svg.innerHTML = `${grid}${bars}${dateTicks}`;

    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const rangeStart = new Date(today);
    rangeStart.setDate(today.getDate() - 89);
    const first = new Date(today);
    first.setDate(today.getDate() - 89);
    first.setDate(first.getDate() - ((first.getDay() + 6) % 7));
    const last = new Date(today);
    last.setDate(today.getDate() + (6 - ((today.getDay() + 6) % 7)));
    const calendarDates = [];
    for (const date = new Date(first); date <= last; date.setDate(date.getDate() + 1)) {
      calendarDates.push(new Date(date));
    }
    const monthFormat = new Intl.DateTimeFormat(undefined, { month: "short", year: "numeric" });
    const fullDateFormat = new Intl.DateTimeFormat(undefined, { weekday: "long", month: "long", day: "numeric", year: "numeric" });
    const weekCount = Math.ceil(calendarDates.length / 7);
    const monthLabels = [];
    for (let week = 0; week < weekCount; week += 1) {
      const weekDates = calendarDates.slice(week * 7, week * 7 + 7);
      const monthDates = weekDates.filter(date => date >= rangeStart && date <= today && (date.getDate() === 1 || date.getTime() === rangeStart.getTime()));
      const monthNames = [...new Set(monthDates.map(date => monthFormat.format(date)))];
      if (monthNames.length) {
        monthLabels.push(`<span style="grid-column:${week + 1}">${escapeHtml(monthNames.join(" / "))}</span>`);
      }
    }
    $("#heatmap-months").style.gridTemplateColumns = `repeat(${weekCount}, 12px)`;
    $("#heatmap-months").innerHTML = monthLabels.join("");
    $("#heatmap-grid").style.gridTemplateColumns = `repeat(${weekCount}, 12px)`;
    $("#heatmap-grid").innerHTML = calendarDates.map((date, index) => {
      const inRange = date >= rangeStart && date <= today;
      const sampleCount = (date.getDate() * 7 + date.getMonth() * 11 + center) % 5;
      const level = inRange ? (sampleCount === 0 ? 0 : sampleCount < 2 ? 1 : sampleCount < 4 ? 2 : 3) : "empty";
      const label = inRange ? `${fullDateFormat.format(date)} · illustrative sample coverage` : `${fullDateFormat.format(date)} · outside the 90-day range`;
      return `<span class="heat-cell heat-${level}" role="img" aria-label="${escapeHtml(label)}" title="${escapeHtml(label)}" style="grid-column:${Math.floor(index / 7) + 1};grid-row:${(index % 7) + 1}"></span>`;
    }).join("");
  }

  function openModal(id) {
    const modal = document.getElementById(id);
    if (modal) {
      modal.hidden = false;
      const input = $("input", modal);
      if (input) input.focus();
    }
  }

  function addActivity(kind, event, details) {
    activity.unshift({ kind, event, who: "Meera Sharma", when: "Just now · preview", details });
    renderActivity();
  }

  function thresholdFeedback(message) {
    let feedback = $("#threshold-feedback");
    if (!feedback) {
      feedback = document.createElement("p");
      feedback.id = "threshold-feedback";
      feedback.className = "bottom-note";
      feedback.setAttribute("role", "status");
      $(".threshold-panel").after(feedback);
    }
    feedback.textContent = message;
  }

  function init() {
    $("#history-room").innerHTML = rooms.map(room => `<option>${escapeHtml(room.name)}</option>`).join("");
    $("#history-metric").innerHTML = Object.entries(metrics).map(([key, metric]) => `<option value="${key}">${metric.label}</option>`).join("");
    $("#sensor-room-select").innerHTML = rooms.map(room => `<option>${escapeHtml(room.name)}</option>`).join("");
    renderRooms();
    renderChart();
    renderAlerts();
    renderSensors();
    renderThresholds();
    renderMembers();
    renderActivity();
    renderHistory();
    $("#theme-toggle").addEventListener("click", event => {
      const button = event.currentTarget;
      const dark = document.body.classList.toggle("theme-dark");
      button.textContent = dark ? "☀" : "☾";
      button.setAttribute("aria-label", dark ? "Switch to light theme" : "Switch to dark theme");
      button.setAttribute("title", dark ? "Switch to light theme" : "Switch to dark theme");
      button.setAttribute("aria-pressed", String(dark));
    });

    document.addEventListener("click", event => {
      const target = event.target.closest("[data-nav], [data-open-modal], [data-close-modal], [data-filter], [data-alert-filter], [data-metric], [data-toggle-sensor], [data-remove-member], [data-scenario], #mobile-menu, #banner-dismiss");
      if (!target) return;
      if (target.dataset.nav) showView(target.dataset.nav);
      if (target.dataset.openModal) openModal(target.dataset.openModal);
      if (target.hasAttribute("data-close-modal")) target.closest(".modal-backdrop").hidden = true;
      if (target.dataset.filter) { roomFilter = target.dataset.filter; renderRooms(); }
      if (target.dataset.alertFilter) {
        alertFilter = target.dataset.alertFilter;
        $$("#alert-filters [data-alert-filter]").forEach(button => button.classList.toggle("selected", button === target));
        renderAlerts();
      }
      if (target.dataset.metric) { selectedMetric = target.dataset.metric; renderChart(); }
      if (target.dataset.toggleSensor !== undefined) {
        const sensor = sensors[Number(target.dataset.toggleSensor)];
        sensor.active = !sensor.active;
        renderSensors($("#sensor-search").value);
        addActivity("sensor", "Sensor preview updated", `${sensor.name} ${sensor.active ? "resumed" : "paused"}`);
      }
      if (target.dataset.removeMember !== undefined) {
        members.splice(Number(target.dataset.removeMember), 1);
        renderMembers();
      }
      if (target.dataset.scenario) runScenario(target.dataset.scenario);
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
        const data = new FormData(form);
        const name = String(data.get("name")).trim();
        const nameInput = $('input[name="name"]', form);
        nameInput.setCustomValidity(rooms.some(room => room.name.toLowerCase() === name.toLowerCase()) ? "A room with this name already exists." : "");
        if (!form.reportValidity() || !name) return;
        rooms.push({ name, ventilation: data.get("ventilation"), co2: 700, temperature: 22.5, humidity: 45, threshold: 1000, high: 1500, rise: 500 });
        $("#history-room").insertAdjacentHTML("beforeend", `<option>${escapeHtml(name)}</option>`);
        $("#sensor-room-select").insertAdjacentHTML("beforeend", `<option>${escapeHtml(name)}</option>`);
        form.reset();
        form.closest(".modal-backdrop").hidden = true;
        renderRooms(); renderChart(); renderThresholds(); renderHistory();
        addActivity("member", "Room added", name);
      } else if (form.id === "sensor-form") {
        event.preventDefault();
        const data = new FormData(form);
        sensors.push({ name: String(data.get("name")).trim(), room: String(data.get("room")), active: true });
        renderSensors($("#sensor-search").value);
        form.reset();
        form.closest(".modal-backdrop").hidden = true;
        addActivity("sensor", "Sample sensor added", sensors[sensors.length - 1].name);
      } else if (form.id === "invite-form") {
        event.preventDefault();
        const email = new FormData(form).get("email");
        $("#invite-code-box").hidden = false;
        $("#invite-code-box").textContent = `Preview only · invitation would be sent to ${email}`;
      } else if (form.matches("[data-ack]")) {
        event.preventDefault();
        const alert = alerts.find(item => item.id === Number(form.dataset.ack));
        if (alert) {
          alert.status = "acknowledged";
          alert.text = `Acknowledged by ${String(new FormData(form).get("name") || "Meera")}. Sample only.`;
          renderAlerts();
          addActivity("threshold", "Sample alert acknowledged", alert.room);
        }
      }
    });

    $("#room-filters").addEventListener("click", event => {
      if (event.target.closest("[data-filter]")) renderRooms();
    });
    $("#sensor-search").addEventListener("input", event => renderSensors(event.target.value));
    $("#activity-filter").addEventListener("change", renderActivity);
    ["history-room", "history-metric", "history-range"].forEach(id => document.getElementById(id).addEventListener("change", renderHistory));
    $("#save-thresholds").addEventListener("click", () => {
      const inputs = $$("[data-threshold]");
      const settings = [$("#clear-duration"), $("#sample-gap")];
      if (inputs.some(input => !input.checkValidity() || Number(input.value) <= 0) ||
        settings.some(input => !input.checkValidity() || Number(input.value) <= 0)) {
        thresholdFeedback("Enter positive values for every sample rule before saving.");
        return;
      }
      const values = rooms.map((room, index) => {
        const elevated = $(`[data-room="${index}"][data-threshold="threshold"]`);
        const high = $(`[data-room="${index}"][data-threshold="high"]`);
        return { room, elevated: Number(elevated.value), high: Number(high.value) };
      });
      if (values.some(item => item.elevated >= item.high)) {
        thresholdFeedback("Each elevated threshold must be lower than its high threshold.");
        return;
      }
      $$("[data-threshold]").forEach(input => {
        const room = rooms[Number(input.dataset.room)];
        const value = Number(input.value);
        room[input.dataset.threshold] = value;
      });
      thresholdFeedback("Sample thresholds saved in browser memory only.");
      addActivity("threshold", "Sample thresholds saved", "Browser memory only");
      const button = $("#save-thresholds");
      button.textContent = "Saved in preview";
      window.setTimeout(() => { button.textContent = "Save changes"; }, 1600);
    });
    $("#export-csv").addEventListener("click", () => {
      const room = rooms.find(item => item.name === $("#history-room").value) || rooms[0];
      const metricKey = $("#history-metric").value || "CO2";
      const metric = metrics[metricKey];
      const rows = [["timestamp", "room", "metric", "value", "unit", "source"]];
      for (let i = 23; i >= 0; i--) {
        const value = Number(room[metric.key]) * (0.82 + ((i * 37 + room[metric.key]) % 35) / 100);
        rows.push([new Date(Date.now() - i * 3600000).toISOString(), room.name, metric.label, value.toFixed(1), metric.unit, "illustrative sample"]);
      }
      const blob = new Blob([rows.map(row => row.map(cell => `"${String(cell).replace(/"/g, '""')}"`).join(",")).join("\r\n")], { type: "text/csv;charset=utf-8" });
      const link = document.createElement("a");
      link.href = URL.createObjectURL(blob);
      link.download = "airsense-illustrative-sample.csv";
      link.click();
      URL.revokeObjectURL(link.href);
    });
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
          const keys = Object.keys(metrics);
          selectedMetric = keys[(keys.indexOf(selectedMetric) + 1) % keys.length];
          renderChart();
        }, 4000);
        button.textContent = "▶";
        button.setAttribute("aria-label", "Resume metric rotation");
        button.setAttribute("aria-pressed", "true");
      }
    });
  }

  function runScenario(scenario) {
    const room = rooms.find(item => item.name === "Bedroom") || rooms[0];
    const kinds = { high: ["high", 1650], elevated: ["elevated", 1250], rapid: ["rapid-rise", 1380], clear: ["all-clear", 720] };
    const [kind, value] = kinds[scenario];
    room.co2 = value;
    if (scenario === "clear") {
      alerts.forEach(alert => { if (alert.room === room.name && alert.status === "open") alert.status = "all_clear"; });
      alerts.unshift({ id: Date.now(), room: room.name, kind, value, status: "all_clear", time: "Just now", text: "Demo all-clear scenario · illustrative sample only." });
    } else {
      alerts.unshift({ id: Date.now(), room: room.name, kind, value, status: "open", time: "Just now", text: `Demo ${scenario} scenario · illustrative CO₂ sample only.` });
    }
    addActivity("threshold", "Demo scenario run", `${scenario} · ${room.name}`);
    renderRooms(); renderChart(); renderAlerts(); renderHistory();
    showView("alerts");
  }

  document.addEventListener("DOMContentLoaded", init);
})();
