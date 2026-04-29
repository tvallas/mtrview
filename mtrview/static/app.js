const state = {
  data: window.MTRVIEW_INITIAL_DATA || { readings: [], counts: {}, zones: [], receivers: [] },
  fetchedAt: Date.now(),
  view: "table",
  sortKey: "location",
  sortDirection: "asc",
  selectedReadingKey: null,
};

const els = {
  refreshTime: document.getElementById("refreshTime"),
  mqttStatus: document.getElementById("mqttStatus"),
  counts: {
    total: document.getElementById("countTotal"),
    offline: document.getElementById("countOffline"),
  },
  search: document.getElementById("searchInput"),
  status: document.getElementById("statusFilter"),
  zone: document.getElementById("zoneFilter"),
  receiver: document.getElementById("receiverFilter"),
  sort: document.getElementById("sortSelect"),
  prioritySection: document.getElementById("prioritySection"),
  priorityCards: document.getElementById("priorityCards"),
  sensorGroups: document.getElementById("sensorGroups"),
  sensorTable: document.getElementById("sensorTable"),
  cardView: document.getElementById("cardView"),
  tableView: document.getElementById("tableView"),
  cardButton: document.getElementById("cardViewButton"),
  tableButton: document.getElementById("tableViewButton"),
  controls: document.getElementById("controls"),
  controlsToggle: document.getElementById("controlsToggle"),
  sortHeaders: document.querySelectorAll(".sort-header"),
  detailOverlay: document.getElementById("sensorDetailOverlay"),
  detailClose: document.getElementById("detailClose"),
  sensorDetail: document.getElementById("sensorDetail"),
  versionStatus: document.getElementById("versionStatus"),
};

const sortDefaults = {
  location: "asc",
  quantity: "asc",
  value: "asc",
  unit: "asc",
  updated: "asc",
  battery: "desc",
  zone: "asc",
  receiver: "asc",
  transmitter_id: "asc",
};

function readingStatus(reading) {
  return reading.status || "unknown";
}

function batteryLabel(reading) {
  const voltage = batteryVoltage(reading);
  if (voltage === null) {
    return "n/a";
  }
  if (voltage >= 3.1) return "full";
  if (voltage >= 2.9) return "good";
  if (voltage >= 2.7) return "medium";
  if (voltage >= 2.6) return "low";
  return "critical";
}

function batteryBadgeClass(reading) {
  const voltage = batteryVoltage(reading);
  if (voltage === null) return "unknown";
  if (voltage <= 2.5) return "problem";
  if (voltage <= 2.8) return "warning";
  return "online";
}

function batteryLevel(reading) {
  const label = batteryLabel(reading);
  return { critical: 1, low: 2, medium: 3, good: 4, full: 5 }[label] || 0;
}

function batteryVoltage(reading) {
  if (reading.battery === null || reading.battery === undefined || reading.battery === "") {
    return null;
  }
  const voltage = Number(reading.battery);
  return Number.isNaN(voltage) ? null : voltage;
}

function batteryIcon(reading) {
  const label = batteryLabel(reading);
  const level = batteryLevel(reading);
  const bars = [1, 2, 3, 4, 5]
    .map((bar) => `<span class="${bar <= level ? "filled" : ""}"></span>`)
    .join("");
  return `
    <span
      class="battery-icon ${escapeHtml(batteryBadgeClass(reading))}"
      title="Battery ${escapeHtml(label)}"
      aria-label="Battery ${escapeHtml(label)}"
      role="img"
    >
      ${bars}
    </span>
  `;
}

function ageLabel(seconds) {
  if (seconds === null || seconds === undefined) return "unknown age";
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 48) return `${hours} hr ago`;
  return `${Math.floor(hours / 24)} days ago`;
}

function ageSpan(reading) {
  if (reading.age_seconds === null || reading.age_seconds === undefined) {
    return '<span class="relative-age">unknown age</span>';
  }
  return `<span class="relative-age" data-age-seconds="${reading.age_seconds}">${ageLabel(reading.age_seconds)}</span>`;
}

function fmtValue(value) {
  if (value === null || value === undefined || value === "") return "n/a";
  if (typeof value === "number") return Number.isInteger(value) ? value : value.toFixed(1);
  return String(value);
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => {
    return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" }[char];
  });
}

function card(reading) {
  const status = readingStatus(reading);
  const badgeClass = reading.problem ? "problem" : "online";
  return `
    <article class="sensor-card ${reading.problem ? "problem" : ""}">
      <div class="card-head">
        <div>
          <div class="name">${escapeHtml(reading.display_name)}</div>
          <div class="meta">${escapeHtml(reading.zone)} · ${escapeHtml(reading.receiver)} / ${escapeHtml(reading.transmitter_id)}</div>
        </div>
        <span class="badge ${escapeHtml(badgeClass || status)}">${escapeHtml(reading.status_label)}</span>
      </div>
      <div class="value">${escapeHtml(fmtValue(reading.value))} <span class="unit">${escapeHtml(reading.unit)}</span></div>
      <div class="meta">${escapeHtml(reading.quantity)}${reading.description ? ` · ${escapeHtml(reading.description)}` : ""}</div>
      <div class="card-foot">
        ${batteryIcon(reading)}
        <span class="timestamp">updated ${ageSpan(reading)} · ${escapeHtml(reading.measured_at || "no timestamp")}</span>
      </div>
    </article>
  `;
}

function sensorLabel(reading) {
  const location = reading.location === "Unknown location" ? "" : reading.location;
  const detail =
    reading.description ||
    (reading.quantity === "Unknown measurement" ? "" : reading.quantity) ||
    reading.display_name ||
    `Transmitter ${reading.transmitter_id}`;
  return [location, detail].filter(Boolean).join(" ") || reading.display_name;
}

function readingKey(reading) {
  return `${reading.receiver}\u001f${reading.transmitter_id}`;
}

function fillSelect(select, values, allLabel) {
  const previous = select.value;
  select.innerHTML = `<option value="all">${allLabel}</option>`;
  values.forEach((value) => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = value;
    select.appendChild(option);
  });
  select.value = values.includes(previous) ? previous : "all";
}

function filteredReadings() {
  const search = els.search.value.trim().toLowerCase();
  const status = els.status.value;
  const zone = els.zone.value;
  const receiver = els.receiver.value;
  let readings = [...state.data.readings];

  readings = readings.filter((reading) => {
    const statusValue = readingStatus(reading);
    const haystack = [
      reading.display_name,
      reading.location,
      reading.zone,
      reading.quantity,
      reading.description,
      reading.battery,
      reading.receiver,
      reading.transmitter_id,
    ]
      .join(" ")
      .toLowerCase();
    return (
      (status === "all" ||
        status === statusValue ||
        (status === "problem" && reading.problem)) &&
      (zone === "all" || reading.zone === zone) &&
      (receiver === "all" || reading.receiver === receiver) &&
      (!search || haystack.includes(search))
    );
  });

  readings.sort(compareReadings);
  return readings;
}

function compareReadings(a, b) {
  const direction = state.sortDirection === "desc" ? -1 : 1;
  const key = state.sortKey;
  let result = 0;

  if (key === "updated") {
    result = (a.age_seconds ?? 999999999) - (b.age_seconds ?? 999999999);
  } else if (key === "value") {
    result = compareValues(a.value, b.value);
  } else if (key === "battery") {
    result = compareValues(a.battery, b.battery);
  } else {
    result = textValue(a, key).localeCompare(textValue(b, key));
  }

  if (result === 0) result = a.sort_key.localeCompare(b.sort_key);
  return result * direction;
}

function compareValues(a, b) {
  const aNumber = typeof a === "number" ? a : Number(a);
  const bNumber = typeof b === "number" ? b : Number(b);
  const aMissing = a === null || a === undefined || a === "" || Number.isNaN(aNumber);
  const bMissing = b === null || b === undefined || b === "" || Number.isNaN(bNumber);
  if (aMissing && bMissing) return 0;
  if (aMissing) return 1;
  if (bMissing) return -1;
  return aNumber - bNumber;
}

function textValue(reading, key) {
  if (key === "transmitter_id") return reading.transmitter_id || "";
  return String(reading[key] ?? "");
}

function render() {
  const counts = state.data.counts || {};
  els.counts.total.textContent = counts.total ?? 0;
  els.counts.offline.textContent = counts.offline ?? 0;
  fillSelect(els.zone, state.data.zones || [], "All zones");
  fillSelect(els.receiver, state.data.receivers || [], "All receivers");

  const mqtt = state.data.mqtt || {};
  setMqttStatus(mqtt.connected, mqtt.error || "disconnected");
  els.refreshTime.textContent = new Date().toLocaleTimeString();

  const readings = filteredReadings();
  const priority = readings.filter((reading) => reading.problem).slice(0, 12);
  els.prioritySection.classList.toggle("hidden", priority.length === 0);
  els.priorityCards.innerHTML = priority.map(card).join("");

  renderGroups(readings);
  renderTable(readings);
  renderOpenDetails();
  renderSortHeaders();
}

function setMqttStatus(connected, message) {
  const statusText = connected ? "connected" : mqttStatusLabel(message);
  els.mqttStatus.textContent = statusText;
  els.mqttStatus.title = connected ? "MQTT connected" : message || "MQTT disconnected";
  els.mqttStatus.closest(".metric-tile").className =
    `metric-tile status-tile connection-tile ${connected ? "ok" : "offline"}`;
}

function mqttStatusLabel(message) {
  if (message && message.toLowerCase().includes("refresh")) return "failed";
  return "offline";
}

function renderGroups(readings) {
  if (!readings.length) {
    els.sensorGroups.innerHTML = '<p class="empty">No sensors match the current filters.</p>';
    return;
  }
  const byZone = groupBy(readings, (reading) => reading.zone);
  els.sensorGroups.innerHTML = [...byZone.entries()]
    .map(([zone, zoneReadings]) => {
      const byLocation = groupBy(zoneReadings, (reading) => reading.location);
      const locations = [...byLocation.entries()]
        .map(([location, locationReadings]) => {
          return `<div class="location-group"><h3 class="location-title">${escapeHtml(location)}</h3><div class="card-grid">${locationReadings.map(card).join("")}</div></div>`;
        })
        .join("");
      return `<div class="zone-group"><h2>${escapeHtml(zone)}</h2>${locations}</div>`;
    })
    .join("");
}

function groupBy(items, keyFn) {
  const grouped = new Map();
  items.forEach((item) => {
    const key = keyFn(item);
    if (!grouped.has(key)) grouped.set(key, []);
    grouped.get(key).push(item);
  });
  return grouped;
}

function renderTable(readings) {
  els.sensorTable.innerHTML = readings
    .map((reading) => {
      const selected = state.selectedReadingKey === readingKey(reading);
      return `
        <tr
          class="${reading.problem ? "problem" : ""}${selected ? " selected" : ""}"
          data-receiver="${escapeHtml(reading.receiver)}"
          data-transmitter="${escapeHtml(reading.transmitter_id)}"
          tabindex="0"
          role="button"
          aria-label="Open ${escapeHtml(sensorLabel(reading))} details"
        >
          <td class="sensor-cell">${escapeHtml(sensorLabel(reading))}</td>
          <td class="value-cell">${escapeHtml(fmtValue(reading.value))} <span>${escapeHtml(reading.unit)}</span></td>
          <td>${ageSpan(reading)}</td>
          <td class="battery-cell">${batteryIcon(reading)}</td>
          <td class="optional-column">${escapeHtml(reading.zone)}</td>
          <td class="optional-column">${escapeHtml(reading.receiver)}</td>
          <td class="optional-column">${escapeHtml(reading.transmitter_id)}</td>
        </tr>
      `;
    })
    .join("");
}

function renderOpenDetails() {
  if (!state.selectedReadingKey || els.detailOverlay.classList.contains("hidden")) return;
  const reading = state.data.readings.find((item) => readingKey(item) === state.selectedReadingKey);
  if (!reading) {
    closeDetails();
    return;
  }
  renderDetails(reading);
}

function openDetails(reading) {
  state.selectedReadingKey = readingKey(reading);
  renderDetails(reading);
  els.detailOverlay.classList.remove("hidden");
  els.detailOverlay.setAttribute("aria-hidden", "false");
  document.body.classList.add("detail-open");
  els.detailClose.focus();
  renderTable(filteredReadings());
}

function closeDetails() {
  state.selectedReadingKey = null;
  els.detailOverlay.classList.add("hidden");
  els.detailOverlay.setAttribute("aria-hidden", "true");
  document.body.classList.remove("detail-open");
  renderTable(filteredReadings());
}

function renderDetails(reading) {
  const badgeClass = reading.problem ? "problem" : "online";
  els.sensorDetail.innerHTML = `
    <div class="detail-head">
      <div>
        <h2 id="detailTitle">${escapeHtml(sensorLabel(reading))}</h2>
        <p>${escapeHtml(reading.zone)} · ${escapeHtml(reading.receiver)} / ${escapeHtml(reading.transmitter_id)}</p>
      </div>
      <span class="badge ${escapeHtml(badgeClass)}">${escapeHtml(reading.status_label)}</span>
    </div>
    <div class="detail-value">${escapeHtml(fmtValue(reading.value))} <span>${escapeHtml(reading.unit)}</span></div>
    <dl class="detail-grid">
      ${detailRow("Location", reading.location)}
      ${detailRow("Quantity", reading.quantity)}
      ${detailRow("Description", reading.description || "n/a")}
      ${detailRow("Zone", reading.zone)}
      ${detailRow("Status", reading.status_label)}
      ${detailRow("Status code", reading.status_code ?? "n/a")}
      ${detailRow("Battery", batteryLabel(reading))}
      ${detailRow("Updated", `updated ${plainAge(reading)} · ${reading.measured_at || "no timestamp"}`)}
      ${detailRow("Receiver", reading.receiver)}
      ${detailRow("Transmitter", reading.transmitter_id)}
    </dl>
  `;
}

function detailRow(label, value) {
  return `<div><dt>${escapeHtml(label)}</dt><dd>${escapeHtml(value)}</dd></div>`;
}

function plainAge(reading) {
  return reading.age_seconds === null || reading.age_seconds === undefined
    ? "unknown age"
    : ageLabel(reading.age_seconds + Math.floor((Date.now() - state.fetchedAt) / 1000));
}

function renderSortHeaders() {
  els.sortHeaders.forEach((button) => {
    const tableHeader = button.closest("th");
    const isActive = button.dataset.sort === state.sortKey;
    button.classList.toggle("active", isActive);
    button.dataset.direction = isActive ? state.sortDirection : "";
    tableHeader.setAttribute(
      "aria-sort",
      isActive ? (state.sortDirection === "asc" ? "ascending" : "descending") : "none",
    );
  });
}

async function refresh() {
  try {
    const response = await fetch("/api/summary", { cache: "no-store" });
    state.data = await response.json();
    state.fetchedAt = Date.now();
    render();
  } catch (error) {
    setMqttStatus(false, "refresh failed");
  }
}

async function refreshVersionStatus() {
  if (!els.versionStatus) return;
  setVersionStatus("checking", "checking updates");
  try {
    const response = await fetch("/api/version", { cache: "no-store" });
    if (!response.ok) throw new Error(`version check failed: ${response.status}`);
    renderVersionStatus(await response.json());
  } catch (error) {
    setVersionStatus("unknown", "update check unavailable");
  }
}

function renderVersionStatus(status) {
  if (status.update_available === true) {
    const latest = status.latest_version ? ` ${status.latest_version}` : "";
    const label = `update${latest} available`;
    setVersionStatus("available", label);
    if (status.release_url) {
      els.versionStatus.innerHTML = `<a href="${escapeHtml(status.release_url)}" rel="noreferrer">${escapeHtml(label)}</a>`;
    }
    return;
  }
  if (status.update_available === false) {
    setVersionStatus("current", "up to date");
    return;
  }
  setVersionStatus(status.error === "disabled" ? "disabled" : "unknown", "update check unavailable");
}

function setVersionStatus(stateName, label) {
  els.versionStatus.dataset.state = stateName;
  els.versionStatus.textContent = label;
  els.versionStatus.title = label;
}

function tickRelativeAges() {
  const elapsedSeconds = Math.floor((Date.now() - state.fetchedAt) / 1000);
  document.querySelectorAll(".relative-age[data-age-seconds]").forEach((element) => {
    const baseAge = Number(element.dataset.ageSeconds);
    if (!Number.isNaN(baseAge)) {
      element.textContent = ageLabel(baseAge + elapsedSeconds);
    }
  });
  renderOpenDetails();
}

[els.search, els.status, els.zone, els.receiver].forEach((el) => {
  el.addEventListener("input", render);
  el.addEventListener("change", render);
});

els.sort.addEventListener("change", () => {
  setSort(els.sort.value);
});

els.sortHeaders.forEach((button) => {
  button.addEventListener("click", () => {
    setSort(button.dataset.sort);
  });
});

els.sensorTable.addEventListener("click", (event) => {
  const row = rowFromEvent(event);
  if (!row) return;
  const reading = findReadingForRow(row);
  if (reading) openDetails(reading);
});

els.sensorTable.addEventListener("keydown", (event) => {
  if (event.key !== "Enter" && event.key !== " ") return;
  const row = rowFromEvent(event);
  if (!row) return;
  event.preventDefault();
  const reading = findReadingForRow(row);
  if (reading) openDetails(reading);
});

els.detailClose.addEventListener("click", closeDetails);

els.detailOverlay.addEventListener("click", (event) => {
  if (event.target === els.detailOverlay) closeDetails();
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && !els.detailOverlay.classList.contains("hidden")) {
    closeDetails();
  }
});

function findReadingForRow(row) {
  return state.data.readings.find((reading) => {
    return (
      reading.receiver === row.dataset.receiver &&
      reading.transmitter_id === row.dataset.transmitter
    );
  });
}

function rowFromEvent(event) {
  if (!(event.target instanceof Element)) return null;
  return event.target.closest("tr[data-receiver][data-transmitter]");
}

function setSort(key) {
  if (state.sortKey === key) {
    state.sortDirection = state.sortDirection === "asc" ? "desc" : "asc";
  } else {
    state.sortKey = key;
    state.sortDirection = sortDefaults[key] || "asc";
  }
  els.sort.value = state.sortKey;
  render();
}

els.cardButton.addEventListener("click", () => {
  state.view = "cards";
  els.cardButton.classList.add("active");
  els.tableButton.classList.remove("active");
  els.cardView.classList.remove("hidden");
  els.tableView.classList.add("hidden");
});

els.tableButton.addEventListener("click", () => {
  state.view = "table";
  els.tableButton.classList.add("active");
  els.cardButton.classList.remove("active");
  els.tableView.classList.remove("hidden");
  els.cardView.classList.add("hidden");
});

els.controlsToggle.addEventListener("click", () => {
  const collapsed = document.body.classList.toggle("controls-collapsed");
  els.controlsToggle.setAttribute("aria-expanded", String(!collapsed));
  els.controlsToggle.title = collapsed ? "Show filters" : "Hide filters";
  els.controlsToggle.classList.toggle("active", !collapsed);
});

render();
tickRelativeAges();
refreshVersionStatus();
setInterval(tickRelativeAges, 1000);
setInterval(refresh, Math.max(5, window.MTRVIEW_REFRESH_INTERVAL || 20) * 1000);
setInterval(refreshVersionStatus, 6 * 60 * 60 * 1000);
