const state = {
  data: window.MTRVIEW_INITIAL_DATA || { readings: [], counts: {}, zones: [], receivers: [] },
  fetchedAt: Date.now(),
  view: "table",
  sortKey: "status",
  sortDirection: "desc",
};

const els = {
  refreshTime: document.getElementById("refreshTime"),
  mqttStatus: document.getElementById("mqttStatus"),
  counts: {
    total: document.getElementById("countTotal"),
    online: document.getElementById("countOnline"),
    stale: document.getElementById("countStale"),
    offline: document.getElementById("countOffline"),
    receivers: document.getElementById("countReceivers"),
  },
  search: document.getElementById("searchInput"),
  status: document.getElementById("statusFilter"),
  zone: document.getElementById("zoneFilter"),
  receiver: document.getElementById("receiverFilter"),
  sort: document.getElementById("sortSelect"),
  priorityCards: document.getElementById("priorityCards"),
  sensorGroups: document.getElementById("sensorGroups"),
  sensorTable: document.getElementById("sensorTable"),
  cardView: document.getElementById("cardView"),
  tableView: document.getElementById("tableView"),
  cardButton: document.getElementById("cardViewButton"),
  tableButton: document.getElementById("tableViewButton"),
  sortHeaders: document.querySelectorAll(".sort-header"),
};

const sortDefaults = {
  status: "desc",
  location: "asc",
  quantity: "asc",
  value: "asc",
  unit: "asc",
  updated: "asc",
  zone: "asc",
  receiver: "asc",
  transmitter_id: "asc",
};

function readingStatus(reading) {
  if (reading.status !== "online") return "offline";
  if (reading.stale) return "stale";
  return "ok";
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
  const badgeClass = reading.status_label.replace(" ", "-");
  return `
    <article class="sensor-card ${reading.problem ? "problem" : ""} ${reading.stale ? "stale" : ""}">
      <div class="card-head">
        <div>
          <div class="name">${escapeHtml(reading.display_name)}</div>
          <div class="meta">${escapeHtml(reading.zone)} · ${escapeHtml(reading.receiver)} / ${escapeHtml(reading.transmitter_id)}</div>
        </div>
        <span class="badge ${escapeHtml(badgeClass || status)}">${escapeHtml(reading.status_label)}</span>
      </div>
      <div class="value">${escapeHtml(fmtValue(reading.value))} <span class="unit">${escapeHtml(reading.unit)}</span></div>
      <div class="meta">${escapeHtml(reading.quantity)}${reading.description ? ` · ${escapeHtml(reading.description)}` : ""}</div>
      <div class="timestamp">updated ${ageSpan(reading)} · ${escapeHtml(reading.measured_at || "no timestamp")}</div>
    </article>
  `;
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
      reading.receiver,
      reading.transmitter_id,
    ]
      .join(" ")
      .toLowerCase();
    return (
      (status === "all" || status === statusValue) &&
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

  if (key === "status") {
    result = statusRank(a) - statusRank(b);
  } else if (key === "updated") {
    result = (a.age_seconds ?? 999999999) - (b.age_seconds ?? 999999999);
  } else if (key === "value") {
    result = compareValues(a.value, b.value);
  } else {
    result = textValue(a, key).localeCompare(textValue(b, key));
  }

  if (result === 0) result = a.sort_key.localeCompare(b.sort_key);
  return result * direction;
}

function statusRank(reading) {
  if (reading.status !== "online") return 3;
  if (reading.critical_stale) return 2;
  if (reading.stale) return 1;
  return 0;
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
  els.counts.online.textContent = counts.online ?? 0;
  els.counts.stale.textContent = counts.stale ?? 0;
  els.counts.offline.textContent = counts.offline ?? 0;
  els.counts.receivers.textContent = counts.receivers ?? 0;
  fillSelect(els.zone, state.data.zones || [], "All zones");
  fillSelect(els.receiver, state.data.receivers || [], "All receivers");

  const mqtt = state.data.mqtt || {};
  els.mqttStatus.textContent = mqtt.connected ? "MQTT connected" : `MQTT ${mqtt.error || "disconnected"}`;
  els.mqttStatus.className = `pill ${mqtt.connected ? "ok" : "offline"}`;
  els.refreshTime.textContent = `Refreshed ${new Date().toLocaleTimeString()}`;

  const readings = filteredReadings();
  const priority = readings.filter((reading) => reading.problem).slice(0, 12);
  els.priorityCards.innerHTML = priority.length
    ? priority.map(card).join("")
    : '<p class="empty">No stale or offline sensors.</p>';

  renderGroups(readings);
  renderTable(readings);
  renderSortHeaders();
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
      const status = readingStatus(reading);
      return `
        <tr class="${reading.problem ? "problem" : ""} ${reading.stale ? "stale" : ""}">
          <td><span class="badge ${escapeHtml(status)}">${escapeHtml(reading.status_label)}</span></td>
          <td>${escapeHtml(reading.location)}</td>
          <td>${escapeHtml(reading.quantity)}</td>
          <td>${escapeHtml(fmtValue(reading.value))}</td>
          <td>${escapeHtml(reading.unit)}</td>
          <td>${ageSpan(reading)}</td>
          <td>${escapeHtml(reading.zone)}</td>
          <td>${escapeHtml(reading.receiver)}</td>
          <td>${escapeHtml(reading.transmitter_id)}</td>
        </tr>
      `;
    })
    .join("");
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
    els.mqttStatus.textContent = "Refresh failed";
    els.mqttStatus.className = "pill offline";
  }
}

function tickRelativeAges() {
  const elapsedSeconds = Math.floor((Date.now() - state.fetchedAt) / 1000);
  document.querySelectorAll(".relative-age[data-age-seconds]").forEach((element) => {
    const baseAge = Number(element.dataset.ageSeconds);
    if (!Number.isNaN(baseAge)) {
      element.textContent = ageLabel(baseAge + elapsedSeconds);
    }
  });
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

render();
tickRelativeAges();
setInterval(tickRelativeAges, 1000);
setInterval(refresh, Math.max(5, window.MTRVIEW_REFRESH_INTERVAL || 20) * 1000);
