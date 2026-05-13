let layoutInfo = {
  source: "bundled",
  uploaded: false,
  url: "/floorplan.svg",
  width: 2507,
  height: 1107,
  updated_at: "",
};
const STALE_AFTER_MS = 15 * 60 * 1000;

function setOverlayViewBox(overlay) {
  overlay.setAttribute("viewBox", `0 0 ${layoutInfo.width} ${layoutInfo.height}`);
  overlay.setAttribute("preserveAspectRatio", "xMidYMid meet");
}

function applyLayoutInfo(nextLayoutInfo) {
  layoutInfo = nextLayoutInfo;
  document.querySelectorAll(".floorplan-stage").forEach((stage) => {
    stage.style.setProperty("--layout-aspect", `${layoutInfo.width} / ${layoutInfo.height}`);
    stage.style.setProperty("--layout-ratio", layoutInfo.width / layoutInfo.height);
  });
  document.querySelectorAll(".floorplan-overlay").forEach(setOverlayViewBox);
  document.querySelectorAll(".floorplan-image").forEach((image) => {
    image.src = `${layoutInfo.url}?v=${encodeURIComponent(layoutInfo.updated_at)}`;
  });
}

async function refreshLayoutInfo() {
  applyLayoutInfo(await fetchJson("/api/floorplan/layout"));
  return layoutInfo;
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  if (!response.ok) {
    throw new Error(`${url} failed with ${response.status}`);
  }
  return response.json();
}

function classifyTemperature(value, profile) {
  if (profile && profile.color_enabled === false) {
    return { band: "no_color", color: "transparent" };
  }
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return { band: "missing", color: "#3b4252" };
  }
  const numeric = Number(value);
  if (numeric < profile.cold) return { band: "cold", color: "#1f6feb" };
  if (numeric < profile.cool) {
    return {
      band: "cool",
      color: interpolateColor("#1f6feb", "#58a6ff", ratio(numeric, profile.cold, profile.cool)),
    };
  }
  if (numeric < profile.normal_min) {
    return {
      band: "slightly_cool",
      color: interpolateColor(
        "#58a6ff",
        "#2ea043",
        ratio(numeric, profile.cool, profile.normal_min),
      ),
    };
  }
  if (numeric <= profile.normal_max) return { band: "normal", color: "#2ea043" };
  if (numeric <= profile.warm) {
    return {
      band: "slightly_warm",
      color: interpolateColor(
        "#2ea043",
        "#d29922",
        ratio(numeric, profile.normal_max, profile.warm),
      ),
    };
  }
  if (numeric <= profile.hot) {
    return {
      band: "warm",
      color: interpolateColor("#d29922", "#f97316", ratio(numeric, profile.warm, profile.hot)),
    };
  }
  return { band: "hot", color: "#f85149" };
}

function polygonPoints(points) {
  return points.map((point) => `${point.x},${point.y}`).join(" ");
}

function floorplanSensorKey(location, description = null, quantity = "Temperature") {
  const parts = [location];
  if (description) parts.push(description);
  if (quantity) parts.push(quantity);
  return parts.join("::");
}

function measurementForArea(measurements, area) {
  const candidates = [
    area.sensor_key,
    floorplanSensorKey(area.location, area.description, area.quantity || "Temperature"),
    area.description ? `${area.location}::${area.description}` : null,
    area.location,
  ].filter(Boolean);

  for (const key of candidates) {
    if (measurements[key]) return measurements[key];
  }
  return null;
}

function floorplanStateFromReadings(readings) {
  const measurements = {};
  readings.forEach((reading) => {
    const description = reading.description || null;
    const quantity = reading.quantity || "Temperature";
    const key = floorplanSensorKey(reading.location, description, quantity);
    const measurement = {
      key,
      label: [reading.location, description, quantity].filter(Boolean).join(" - "),
      location: reading.location,
      description,
      quantity,
      value: reading.value,
      topic: `summary/${reading.receiver}/${reading.transmitter_id}`,
      sensor_id: reading.transmitter_id,
      unit: reading.unit,
      observed_at: reading.measured_at,
      received_at: reading.updated_at || reading.measured_at,
    };
    measurements[key] = measurement;
    if (description) measurements[`${reading.location}::${description}`] = measurement;
    measurements[reading.location] = measurement;
  });
  return measurements;
}

function boundingBox(points) {
  if (!points.length) return { x: 0, y: 0, width: 0, height: 0 };
  const xs = points.map((point) => point.x);
  const ys = points.map((point) => point.y);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  return { x: minX, y: minY, width: maxX - minX, height: maxY - minY };
}

function labelLayout(points, text, preferredPosition = null) {
  const box = boundingBox(points);
  const center = { x: box.x + box.width / 2, y: box.y + box.height / 2 };
  const preferredOutsideBox =
    preferredPosition &&
    (preferredPosition.x < box.x ||
      preferredPosition.x > box.x + box.width ||
      preferredPosition.y < box.y ||
      preferredPosition.y > box.y + box.height);
  if (preferredOutsideBox) {
    return { ...preferredPosition, fontSize: 34 };
  }

  const estimatedCharWidth = 0.62;
  const horizontalFit = box.width / Math.max(text.length * estimatedCharWidth, 1);
  const verticalFit = box.height * 0.46;
  const fontSize = Math.max(13, Math.min(38, horizontalFit, verticalFit));
  return { ...(preferredPosition || center), fontSize };
}

function svgPointFromEvent(svg, event) {
  const point = svg.createSVGPoint();
  point.x = event.clientX;
  point.y = event.clientY;
  const transformed = point.matrixTransform(svg.getScreenCTM().inverse());
  return {
    x: Math.round(transformed.x * 10) / 10,
    y: Math.round(transformed.y * 10) / 10,
  };
}

function layoutWidth() {
  return layoutInfo.width;
}

function layoutHeight() {
  return layoutInfo.height;
}

function ratio(value, min, max) {
  if (max <= min) return 1;
  return Math.max(0, Math.min(1, (value - min) / (max - min)));
}

function interpolateColor(start, end, amount) {
  const left = hexToRgb(start);
  const right = hexToRgb(end);
  const mixed = left.map((channel, index) => {
    return Math.round(channel + (right[index] - channel) * amount);
  });
  return `#${mixed.map((channel) => channel.toString(16).padStart(2, "0")).join("")}`;
}

function hexToRgb(hex) {
  const normalized = hex.replace("#", "");
  return [0, 2, 4].map((index) => parseInt(normalized.slice(index, index + 2), 16));
}
