const state = {
  config: null,
  readings: [],
};

const els = {
  floorplanView: document.getElementById("floorplanView"),
  floorplanStage: document.getElementById("floorplanStage"),
  floorplanOverlay: document.getElementById("floorplanOverlay"),
};

function renderFloorplan() {
  if (!state.config || !els.floorplanOverlay) return;
  els.floorplanOverlay.replaceChildren();
  const fillLayer = document.createElementNS("http://www.w3.org/2000/svg", "g");
  const labelLayer = document.createElementNS("http://www.w3.org/2000/svg", "g");
  els.floorplanOverlay.append(fillLayer, labelLayer);

  const measurements = floorplanStateFromReadings(state.readings);
  state.config.areas.forEach((area) => {
    const profile = state.config.profiles[area.profile] || state.config.profiles.room;
    const measurement = measurementForArea(measurements, area);
    const value = measurement ? measurement.value : null;
    const classification = classifyTemperature(value, profile);
    const poly = document.createElementNS("http://www.w3.org/2000/svg", "polygon");
    poly.setAttribute("points", polygonPoints(area.points));
    poly.setAttribute("fill", classification.color);
    poly.classList.add("area-fill");
    if (classification.band === "no_color") {
      poly.classList.add("no-color");
    }
    if (measurement && measurement.received_at) {
      const receivedAt = Date.parse(measurement.received_at);
      if (!Number.isNaN(receivedAt) && Date.now() - receivedAt > STALE_AFTER_MS) {
        poly.classList.add("stale");
      }
    }
    fillLayer.appendChild(poly);

    const labelText =
      value === null || value === undefined ? "--" : `${Number(value).toFixed(1)}${measurement.unit || ""}`;
    const label = labelLayout(area.points, labelText, area.label_position);
    const group = document.createElementNS("http://www.w3.org/2000/svg", "g");
    group.classList.add("area-label-group");
    const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
    text.setAttribute("x", label.x);
    text.setAttribute("y", label.y);
    text.setAttribute("font-size", label.fontSize);
    text.setAttribute("dominant-baseline", "middle");
    text.classList.add("area-label");
    text.textContent = labelText;
    group.appendChild(text);
    labelLayer.appendChild(group);

    const textBox = text.getBBox();
    const paddingX = Math.max(6, label.fontSize * 0.28);
    const paddingY = Math.max(4, label.fontSize * 0.18);
    const plate = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    plate.setAttribute("x", textBox.x - paddingX);
    plate.setAttribute("y", textBox.y - paddingY);
    plate.setAttribute("width", textBox.width + paddingX * 2);
    plate.setAttribute("height", textBox.height + paddingY * 2);
    plate.setAttribute("rx", Math.min(8, label.fontSize * 0.18));
    plate.classList.add("area-label-plate");
    group.insertBefore(plate, text);
  });
}

async function refreshSummary() {
  const summary = await fetchJson("/api/summary", { cache: "no-store" });
  state.readings = Array.isArray(summary.readings) ? summary.readings : [];
  renderFloorplan();
}

async function initialize() {
  await refreshLayoutInfo();
  state.config = await fetchJson("/api/floorplan/config", { cache: "no-store" });
  await refreshSummary();
}

async function toggleBrowserFullscreen() {
  if (!els.floorplanView) return;
  if (document.fullscreenElement) {
    await document.exitFullscreen();
    return;
  }
  if (els.floorplanView.requestFullscreen && document.fullscreenEnabled) {
    await els.floorplanView.requestFullscreen();
  }
}

if (els.floorplanStage) {
  els.floorplanStage.addEventListener("click", () => {
    toggleBrowserFullscreen().catch(() => {});
  });
  els.floorplanStage.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      toggleBrowserFullscreen().catch(() => {});
    }
  });
}

initialize().catch(() => {});
setInterval(() => {
  refreshSummary().catch(() => {});
}, Math.max(5, window.MTRVIEW_REFRESH_INTERVAL || 20) * 1000);
