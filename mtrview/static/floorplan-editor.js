const overlay = document.querySelector("#overlay");
const areaList = document.querySelector("#area-list");
const areaName = document.querySelector("#area-name");
const areaLocation = document.querySelector("#area-location");
const areaProfile = document.querySelector("#area-profile");
const duplicateWarning = document.querySelector("#duplicate-warning");
const snapAngles = document.querySelector("#snap-angles");
const saveButton = document.querySelector("#save");
const layoutStatus = document.querySelector("#layout-status");
const layoutUpload = document.querySelector("#layout-upload");
const resetLayoutButton = document.querySelector("#reset-layout");
const profileEditorSelect = document.querySelector("#profile-editor-select");
const addProfileButton = document.querySelector("#add-profile");
const profileColorEnabled = document.querySelector("#profile-color-enabled");
const profileInputs = {
  cold: document.querySelector("#profile-cold"),
  cool: document.querySelector("#profile-cool"),
  normal_min: document.querySelector("#profile-normal-min"),
  normal_max: document.querySelector("#profile-normal-max"),
  warm: document.querySelector("#profile-warm"),
  hot: document.querySelector("#profile-hot"),
};

let config = null;
let sensors = [];
let selectedId = null;
let dragging = null;
let labelPlacementMode = false;
let savedSnapshot = "";
let saving = false;
let savedFeedbackTimer = null;
const SNAP_DISTANCE = 18;

function configSnapshot() {
  return JSON.stringify(config);
}

function hasUnsavedChanges() {
  return Boolean(config) && configSnapshot() !== savedSnapshot;
}

function showSavedFeedback() {
  if (savedFeedbackTimer) {
    window.clearTimeout(savedFeedbackTimer);
  }
  saveButton.textContent = "Saved";
  saveButton.classList.add("saved");
  savedFeedbackTimer = window.setTimeout(() => {
    savedFeedbackTimer = null;
    saveButton.classList.remove("saved");
    updateSaveButton();
  }, 1600);
}

function updateSaveButton() {
  if (saving) {
    saveButton.disabled = true;
    saveButton.textContent = "Saving...";
    return;
  }
  if (savedFeedbackTimer) return;
  const dirty = hasUnsavedChanges();
  saveButton.disabled = !dirty;
  saveButton.textContent = dirty ? "Save changes" : "No changes";
}

function renderLayoutStatus() {
  const source = layoutInfo.uploaded ? "Uploaded SVG" : "Bundled SVG";
  layoutStatus.textContent = `${source} · ${Math.round(layoutInfo.width)} x ${Math.round(
    layoutInfo.height,
  )}`;
  resetLayoutButton.disabled = !layoutInfo.uploaded;
}

function selectedArea() {
  return config.areas.find((area) => area.id === selectedId) || null;
}

function selectArea(id) {
  selectedId = id;
  const area = selectedArea();
  if (area) {
    areaName.value = area.name;
    areaLocation.value = area.sensor_key || area.location;
    areaProfile.value = area.profile;
    profileEditorSelect.value = area.profile;
  }
  renderEditor();
}

function syncSelectedFromForm() {
  const area = selectedArea();
  if (!area) return;
  const sensor = sensors.find((candidate) => candidate.key === areaLocation.value);
  const configuredArea = config.areas.find((candidate) => {
    return (candidate.sensor_key || candidate.location) === areaLocation.value;
  });
  const source = sensor || configuredArea;
  area.name = areaName.value || area.id;
  area.sensor_key = areaLocation.value;
  area.location = source?.location || area.location || areaLocation.value;
  area.description = source?.description || null;
  area.quantity = source?.quantity || "Temperature";
  area.profile = areaProfile.value;
  renderEditor();
}

function editorSensorLabel(item) {
  const parts = [item.location].filter(Boolean);
  if (item.description) parts.push(item.description);
  if (item.quantity) parts.push(item.quantity);
  return parts.join(" - ") || item.sensor_key || item.key || "No sensor";
}

function renderSelects() {
  const profileOptions = Object.keys(config.profiles).map((profile) => {
    const option = document.createElement("option");
    option.value = profile;
    option.textContent = profile;
    return option;
  });
  areaProfile.replaceChildren(...profileOptions.map((option) => option.cloneNode(true)));
  profileEditorSelect.replaceChildren(...profileOptions);

  const sensorOptions = sensors.map((sensor) => ({
    key: sensor.key,
    label: sensor.label,
  }));
  const configuredOptions = config.areas
    .filter((area) => area.sensor_key || area.location)
    .map((area) => ({
      key: area.sensor_key || area.location,
      label: editorSensorLabel(area),
    }));
  const allOptions = [...sensorOptions, ...configuredOptions]
    .filter((option, index, options) => {
      return options.findIndex((candidate) => candidate.key === option.key) === index;
    })
    .sort((left, right) => left.label.localeCompare(right.label));
  areaLocation.replaceChildren(
    ...allOptions.map((sensor) => {
      const option = document.createElement("option");
      option.value = sensor.key;
      option.textContent = sensor.label;
      return option;
    }),
  );
}

function selectedProfileName() {
  return profileEditorSelect.value || Object.keys(config.profiles)[0] || "";
}

function renderProfileEditor() {
  const profileName = selectedProfileName();
  const profile = config.profiles[profileName];
  if (!profile) return;
  profileColorEnabled.checked = profile.color_enabled !== false;
  Object.entries(profileInputs).forEach(([key, input]) => {
    input.value = profile[key];
    input.disabled = profile.color_enabled === false;
  });
}

function syncSelectedProfileFromForm() {
  const profileName = selectedProfileName();
  const profile = config.profiles[profileName];
  if (!profile) return;
  profile.color_enabled = profileColorEnabled.checked;
  Object.entries(profileInputs).forEach(([key, input]) => {
    profile[key] = Number(input.value);
    input.disabled = !profile.color_enabled;
  });
  updateSaveButton();
}

function addProfile() {
  const rawName = window.prompt("Preset name");
  const name = normalizeProfileName(rawName);
  if (!name) return;
  if (config.profiles[name]) {
    alert(`${name} already exists.`);
    return;
  }
  const source = config.profiles[selectedProfileName()] || config.profiles.room;
  config.profiles[name] = { ...source };
  renderSelects();
  profileEditorSelect.value = name;
  areaProfile.value = name;
  const area = selectedArea();
  if (area) area.profile = name;
  renderProfileEditor();
  renderEditor();
  updateSaveButton();
}

function normalizeProfileName(value) {
  return String(value || "")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
}

function renderAreaList() {
  areaList.replaceChildren(
    ...config.areas.map((area) => {
      const item = document.createElement("li");
      item.classList.toggle("active", area.id === selectedId);
      item.innerHTML = `<strong></strong><span></span>`;
      item.querySelector("strong").textContent = area.name || area.id;
      item.querySelector("span").textContent = `${editorSensorLabel(area)} · ${area.profile}`;
      item.addEventListener("click", () => selectArea(area.id));
      return item;
    }),
  );
}

function renderDuplicateWarning() {
  const area = selectedArea();
  const sensor = sensors.find((candidate) => {
    return candidate.key === (area?.sensor_key || area?.location);
  });
  duplicateWarning.hidden = !sensor?.duplicate;
  duplicateWarning.textContent = sensor?.duplicate
    ? `Duplicate sensor identity from ${sensor.topics.length} topics. The latest message wins.`
    : "";
}

function areaLabelPosition(area) {
  if (area.label_position) return area.label_position;
  const label = labelLayout(area.points, area.name || area.id);
  return { x: label.x, y: label.y };
}

function snappedPoint(area, event, movingIndex = null) {
  const point = svgPointFromEvent(overlay, event);
  if (!snapAngles.checked || event.shiftKey || !area) return point;

  const candidates = area.points.filter((_point, index) => index !== movingIndex);
  const snapped = { ...point };
  for (const candidate of candidates) {
    if (Math.abs(candidate.x - point.x) <= SNAP_DISTANCE) {
      snapped.x = candidate.x;
    }
    if (Math.abs(candidate.y - point.y) <= SNAP_DISTANCE) {
      snapped.y = candidate.y;
    }
  }
  return snapped;
}

function renderSnapGuides(area, movingPoint = null) {
  if (!movingPoint || !snapAngles.checked) return;
  const matchingX = area.points.some((point, index) => {
    return index !== dragging?.index && point.x === movingPoint.x;
  });
  const matchingY = area.points.some((point, index) => {
    return index !== dragging?.index && point.y === movingPoint.y;
  });
  if (!matchingX && !matchingY) return;

  const group = document.createElementNS("http://www.w3.org/2000/svg", "g");
  group.classList.add("snap-guides");
  if (matchingX) {
    const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
    line.setAttribute("x1", movingPoint.x);
    line.setAttribute("x2", movingPoint.x);
    line.setAttribute("y1", 0);
    line.setAttribute("y2", layoutHeight());
    group.appendChild(line);
  }
  if (matchingY) {
    const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
    line.setAttribute("x1", 0);
    line.setAttribute("x2", layoutWidth());
    line.setAttribute("y1", movingPoint.y);
    line.setAttribute("y2", movingPoint.y);
    group.appendChild(line);
  }
  overlay.appendChild(group);
}

function renderEditor() {
  overlay.replaceChildren();
  config.areas.forEach((area) => {
    const polygon = document.createElementNS("http://www.w3.org/2000/svg", "polygon");
    polygon.setAttribute("points", polygonPoints(area.points));
    polygon.setAttribute("fill", area.id === selectedId ? "#14b8a6" : "#64748b");
    polygon.classList.add("area-edit-shape");
    polygon.addEventListener("click", (event) => {
      event.stopPropagation();
      selectArea(area.id);
    });
    overlay.appendChild(polygon);

    if (area.id === selectedId) {
      area.points.forEach((point, index) => {
        const vertex = document.createElementNS("http://www.w3.org/2000/svg", "circle");
        vertex.setAttribute("cx", point.x);
        vertex.setAttribute("cy", point.y);
        vertex.setAttribute("r", 12);
        vertex.classList.add("vertex");
        vertex.addEventListener("pointerdown", (event) => {
          event.stopPropagation();
          dragging = { areaId: area.id, index };
          vertex.setPointerCapture(event.pointerId);
        });
        overlay.appendChild(vertex);
      });
      if (dragging?.areaId === area.id && !dragging.label) {
        renderSnapGuides(area, area.points[dragging.index]);
      }
      const label = areaLabelPosition(area);
      const labelHandle = document.createElementNS("http://www.w3.org/2000/svg", "g");
      labelHandle.classList.add("label-handle");
      const labelCircle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
      labelCircle.setAttribute("cx", label.x);
      labelCircle.setAttribute("cy", label.y);
      labelCircle.setAttribute("r", 18);
      const labelText = document.createElementNS("http://www.w3.org/2000/svg", "text");
      labelText.setAttribute("x", label.x);
      labelText.setAttribute("y", label.y);
      labelText.setAttribute("dominant-baseline", "middle");
      labelText.textContent = "T";
      labelHandle.append(labelCircle, labelText);
      labelHandle.addEventListener("pointerdown", (event) => {
        event.stopPropagation();
        dragging = { areaId: area.id, label: true };
        labelHandle.setPointerCapture(event.pointerId);
      });
      overlay.appendChild(labelHandle);
    }
  });
  renderAreaList();
  renderDuplicateWarning();
  renderProfileEditor();
  updateSaveButton();
}

function newArea() {
  const id = `area-${Date.now()}`;
  const sensor = sensors[0] || null;
  config.areas.push({
    id,
    name: "New area",
    location: sensor?.location || "",
    description: sensor?.description || null,
    quantity: sensor?.quantity || "Temperature",
    sensor_key: sensor?.key || "",
    profile: "room",
    points: [],
  });
  if (sensor?.key && ![...areaLocation.options].some((option) => option.value === sensor.key)) {
    renderSelects();
  }
  selectArea(id);
}

overlay.addEventListener("click", (event) => {
  const area = selectedArea();
  if (!area) return;
  if (labelPlacementMode) {
    area.label_position = svgPointFromEvent(overlay, event);
    labelPlacementMode = false;
    document.querySelector("#set-label-position").classList.remove("active");
    renderEditor();
    return;
  }
  area.points.push(snappedPoint(area, event));
  renderEditor();
});

overlay.addEventListener("pointermove", (event) => {
  if (!dragging) return;
  const area = config.areas.find((candidate) => candidate.id === dragging.areaId);
  if (!area) return;
  if (dragging.label) {
    area.label_position = svgPointFromEvent(overlay, event);
  } else {
    area.points[dragging.index] = snappedPoint(area, event, dragging.index);
  }
  renderEditor();
});

overlay.addEventListener("pointerup", () => {
  dragging = null;
});

document.querySelector("#new-area").addEventListener("click", newArea);
document.querySelector("#delete-area").addEventListener("click", () => {
  config.areas = config.areas.filter((area) => area.id !== selectedId);
  selectedId = config.areas[0]?.id || null;
  renderEditor();
});
document.querySelector("#set-label-position").addEventListener("click", (event) => {
  labelPlacementMode = !labelPlacementMode;
  event.currentTarget.classList.toggle("active", labelPlacementMode);
});
document.querySelector("#reset-label-position").addEventListener("click", () => {
  const area = selectedArea();
  if (!area) return;
  area.label_position = null;
  labelPlacementMode = false;
  document.querySelector("#set-label-position").classList.remove("active");
  renderEditor();
});
saveButton.addEventListener("click", async () => {
  if (!hasUnsavedChanges() || saving) return;
  const invalid = config.areas.find((area) => area.points.length < 3);
  if (invalid) {
    alert(`${invalid.name || invalid.id} needs at least three points.`);
    return;
  }
  syncSelectedFromForm();
  syncSelectedProfileFromForm();
  saving = true;
  updateSaveButton();
  try {
    config = await fetchJson("/api/floorplan/config", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(config),
    });
    savedSnapshot = configSnapshot();
    renderEditor();
    showSavedFeedback();
  } finally {
    saving = false;
    updateSaveButton();
  }
});
layoutUpload.addEventListener("change", async () => {
  const file = layoutUpload.files[0];
  if (!file) return;
  try {
    const svg = await file.text();
    const metadata = await fetchJson("/api/floorplan/layout", {
      method: "POST",
      headers: { "Content-Type": "image/svg+xml" },
      body: svg,
    });
    applyLayoutInfo(metadata);
    renderLayoutStatus();
  } catch (error) {
    alert(error.message);
  } finally {
    layoutUpload.value = "";
  }
});
resetLayoutButton.addEventListener("click", async () => {
  const metadata = await fetchJson("/api/floorplan/layout", { method: "DELETE" });
  applyLayoutInfo(metadata);
  renderLayoutStatus();
});

[areaName, areaLocation, areaProfile].forEach((input) => {
  input.addEventListener("change", syncSelectedFromForm);
  input.addEventListener("input", syncSelectedFromForm);
});

profileEditorSelect.addEventListener("change", renderProfileEditor);
addProfileButton.addEventListener("click", addProfile);
profileColorEnabled.addEventListener("change", syncSelectedProfileFromForm);
Object.values(profileInputs).forEach((input) => {
  input.addEventListener("input", syncSelectedProfileFromForm);
  input.addEventListener("change", syncSelectedProfileFromForm);
});

async function boot() {
  await refreshLayoutInfo();
  renderLayoutStatus();
  config = await fetchJson("/api/floorplan/config");
  sensors = await fetchJson("/api/floorplan/sensors");
  savedSnapshot = configSnapshot();
  renderSelects();
  profileEditorSelect.value = Object.keys(config.profiles)[0] || "";
  renderProfileEditor();
  if (config.areas[0]) {
    selectArea(config.areas[0].id);
  } else {
    newArea();
  }
  renderEditor();
}

boot().catch((error) => {
  console.error(error);
});
