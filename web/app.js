const layers = {};
const SITE_OPTIONS = {
  site1: "Gale crater floor",
  site2: "Southern box",
};

function formatNumber(value, unit, digits = 2) {
  return `${Number(value).toFixed(digits)} ${unit}`;
}

function makeImageOverlay(path, bounds, pane) {
  return L.imageOverlay(`/${path}`, bounds, { pane });
}

function gridToLeaflet([row, col]) {
  return [window.grid.rows - row, col];
}

function setLayerControl(name, toggleId, opacityId) {
  const toggle = document.getElementById(toggleId);
  const opacity = document.getElementById(opacityId);
  toggle.addEventListener("change", () => {
    if (toggle.checked) layers[name].addTo(window.map);
    else window.map.removeLayer(layers[name]);
  });
  opacity.addEventListener("input", () => setLayerOpacity(layers[name], Number(opacity.value)));
}

function setupSidebarResizer() {
  const shell = document.querySelector(".shell");
  const handle = document.querySelector(".sidebar-resizer");
  const mediaQuery = window.matchMedia("(max-width: 760px)");
  if (!shell || !handle) return;

  const setWidth = (width) => {
    const maxWidth = Math.min(480, window.innerWidth * 0.45);
    const nextWidth = Math.max(260, Math.min(maxWidth, width));
    shell.style.setProperty("--sidebar-width", `${nextWidth}px`);
    window.map?.invalidateSize({ pan: false });
  };
  let dragging = false;
  handle.addEventListener("pointerdown", (event) => {
    if (mediaQuery.matches) return;
    dragging = true;
    handle.setPointerCapture(event.pointerId);
    shell.classList.add("is-resizing");
    event.preventDefault();
  });
  handle.addEventListener("pointermove", (event) => {
    if (dragging) setWidth(event.clientX);
  });
  const stopDragging = () => {
    dragging = false;
    shell.classList.remove("is-resizing");
  };
  handle.addEventListener("pointerup", stopDragging);
  handle.addEventListener("pointercancel", stopDragging);
  handle.addEventListener("keydown", (event) => {
    if (mediaQuery.matches) return;
    if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
      setWidth(shell.querySelector(".sidebar").getBoundingClientRect().width
        + (event.key === "ArrowRight" ? 16 : -16));
      event.preventDefault();
    }
  });
}

function setLayerOpacity(layer, value) {
  if (layer.setOpacity) {
    layer.setOpacity(value);
  } else if (layer.setStyle) {
    layer.setStyle({ opacity: value, fillOpacity: value });
  } else if (layer.eachLayer) {
    layer.eachLayer((child) => setLayerOpacity(child, value));
  }
}

function addScaleBar(map, grid) {
  const control = L.control({ position: "bottomleft" });
  control.onAdd = () => {
    const element = L.DomUtil.create("div", "map-scale");
    const update = () => {
      const desiredKm = 1;
      const gridWidth = desiredKm * 1000 / (window.grid?.cell_size_m.x || grid.cell_size_m.x);
      const start = map.latLngToContainerPoint([0, 0]);
      const end = map.latLngToContainerPoint([0, gridWidth]);
      element.style.width = `${Math.max(40, end.x - start.x)}px`;
      element.textContent = `${desiredKm} km`;
    };
    map.on("zoomend moveend", update);
    update();
    return element;
  };
  control.addTo(map);
}

function addNorthArrow(map) {
  const control = L.control({ position: "topright" });
  control.onAdd = () => {
    const element = L.DomUtil.create("div", "north-arrow");
    element.setAttribute("aria-label", "Grid north");
    element.innerHTML = "<span class=\"north-arrow-label\">GRID NORTH</span>"
      + "<span class=\"north-arrow-compass\"><i></i><b>N</b></span>";
    return element;
  };
  control.addTo(map);
}

function addResetControl(map, bounds) {
  const control = L.control({ position: "topright" });
  control.onAdd = () => {
    const button = L.DomUtil.create("button", "map-action");
    button.type = "button";
    button.textContent = "Reset view";
    button.title = "Fit the full mission area";
    L.DomEvent.disableClickPropagation(button);
    L.DomEvent.on(button, "click", () => map.fitBounds(window.siteBounds || bounds, { padding: [24, 24] }));
    return button;
  };
  control.addTo(map);
}

function addZoomPercentageControl(map, minZoom) {
  const control = L.control({ position: "topright" });
  control.onAdd = () => {
    const element = L.DomUtil.create("label", "zoom-percent-control");
    element.innerHTML = "<span>ZOOM</span>";
    const output = L.DomUtil.create("output", "", element);
    const slider = L.DomUtil.create("input", "", element);
    slider.type = "range";
    slider.min = "100";
    slider.max = "300";
    slider.step = "25";
    slider.value = "100";
    slider.setAttribute("aria-label", "Map zoom percentage");
    const sync = () => {
      const percentage = 100 * (2 ** (map.getZoom() - (window.mapMinZoom || minZoom)));
      const value = Math.min(300, Math.max(100, Math.round(percentage / 25) * 25));
      slider.value = value;
      output.textContent = `${value}%`;
    };
    L.DomEvent.disableClickPropagation(slider);
    L.DomEvent.on(slider, "input", () => {
      map.setZoom((window.mapMinZoom || minZoom) + Math.log2(Number(slider.value) / 100));
    });
    map.on("zoomend", sync);
    sync();
    return element;
  };
  control.addTo(map);
}

function gridToLatLon(grid, [row, col]) {
  const bounds = grid.geo_reference.bounds;
  const latRatio = (grid.rows - row) / grid.rows;
  const lonRatio = col / grid.cols;
  return {
    lat: bounds.min_lat + latRatio * (bounds.max_lat - bounds.min_lat),
    lon: bounds.min_lon + lonRatio * (bounds.max_lon - bounds.min_lon),
  };
}

function inspectCell(grid, latlng) {
  const row = Math.max(0, Math.min(grid.rows - 1, Math.floor(grid.rows - latlng.lat)));
  const col = Math.max(0, Math.min(grid.cols - 1, Math.floor(latlng.lng)));
  return {
    row,
    col,
    latLon: gridToLatLon(grid, [row, col]),
  };
}

function renderCheckpointDetails(grid, stats) {
  const points = [
    { label: "Habitat", point: grid.habitat, leg: null },
    ...grid.targets.map((target, index) => ({
      label: `Target ${index + 1}`,
      point: target,
      leg: grid.legs[index],
    })),
    { label: "Return", point: grid.habitat, leg: grid.legs.at(-1) },
  ];
  document.getElementById("checkpoint-summary").textContent =
    `${stats.distance_km.toFixed(3)} km total · ${stats.time_h.toFixed(3)} h EVA · `
    + `${stats.return_margin_h.toFixed(3)} h margin`;
  document.getElementById("checkpoint-leg-list").innerHTML = points.map((item) => {
    const meta = item.leg
      ? `${item.leg.distance_km.toFixed(3)} km · ${item.leg.time_h.toFixed(3)} h`
      : "departure point";
    const coordinates = `${item.point.lat.toFixed(5)}°, ${item.point.lon.toFixed(5)}°`;
    return `<div class="checkpoint-detail"><span class="checkpoint-detail-label">${item.label}</span>`
      + `<span class="checkpoint-detail-meta">${meta}</span>`
      + `<span class="checkpoint-detail-coord">${coordinates}</span></div>`;
  }).join("");
}

async function loadSite(site) {
  const root = `/data/processed/${site}/`;
  const [stats, grid] = await Promise.all([
    fetch(`${root}stats.json`).then((response) => response.json()),
    fetch(`${root}grid.json`).then((response) => response.json()),
  ]);
  Object.values(layers).forEach((layer) => window.map.removeLayer(layer));
  window.grid = grid;
  const bounds = grid.grid_bounds;
  const minZoom = window.map.getBoundsZoom(bounds);
  window.siteBounds = bounds;
  window.mapMinZoom = minZoom;
  window.map.setMinZoom(minZoom);
  window.map.fitBounds(bounds, { padding: [24, 24] });
  document.getElementById("site-name").textContent = grid.site_name;
  document.getElementById("site-region").textContent = "Real NASA data";
  document.getElementById("site-select").value = site;
  document.getElementById("slope-limit").textContent = `${grid.max_walkable_slope_deg}°+`;
  renderCheckpointDetails(grid, stats);
  document.getElementById("map-inspector").innerHTML =
    "<span class=\"inspector-kicker\">TERRAIN INSPECTOR</span>"
    + "<strong class=\"inspector-coordinate\">SITE READY</strong>"
    + "<span class=\"inspector-terrain\">Move over the real DEM and imagery</span>";

  layers.terrain = makeImageOverlay(grid.layer_paths.elevation, bounds, "terrain-pane").addTo(window.map);
  layers.imagery = makeImageOverlay(grid.layer_paths.imagery, bounds, "imagery-pane").addTo(window.map);
  layers.slope = makeImageOverlay(grid.layer_paths.slope, bounds, "slope-pane").addTo(window.map);
  layers.hazard = makeImageOverlay(grid.layer_paths.hazard, bounds, "hazard-pane").addTo(window.map);
  const outboundPixels = grid.route_segments.slice(0, -1).flatMap((segment, index) =>
    index === 0 ? segment : segment.slice(1));
  const returnPixels = grid.route_segments.at(-1);
  layers.route = L.layerGroup([
    L.polyline(outboundPixels.map(gridToLeaflet), {
      color: "#080d16", weight: 7, opacity: .9, lineCap: "round", lineJoin: "round",
      pane: "route-pane",
    }),
    L.polyline(outboundPixels.map(gridToLeaflet), {
      color: "#fbbf24", weight: 3, opacity: 1, dashArray: "10 8",
      lineCap: "round", lineJoin: "round", pane: "route-pane",
    }).bindTooltip("Outbound leg · Habitat → science targets"),
    L.polyline(returnPixels.map(gridToLeaflet), {
      color: "#080d16", weight: 8, opacity: .9, lineCap: "round", lineJoin: "round",
      pane: "route-pane",
    }),
    L.polyline(returnPixels.map(gridToLeaflet), {
      color: "#68e1fd", weight: 4, opacity: 1,
      lineCap: "round", lineJoin: "round", pane: "route-pane",
    }).bindTooltip("Return leg · Target 3 → Habitat"),
  ]).addTo(window.map);
  layers.targets = L.layerGroup();
  grid.targets.forEach((target) => {
    const marker = L.circleMarker(gridToLeaflet([target.row, target.col]), {
      radius: 9, color: "#080d16", weight: 3, fillColor: "#fbbf24", fillOpacity: 1,
      pane: "targets-pane",
    });
    const label = `Target ${target.id.split("-")[1]}`;
    const leg = grid.legs.find((item) => item.name === target.id);
    marker.bindTooltip(`${label} · ${leg.distance_km.toFixed(3)} km · ${leg.time_h.toFixed(3)} h`);
    marker.bindPopup(`<strong>${label}</strong><div class="photo-slot">CTX imagery<br>real surface preview</div>`);
    marker.addTo(layers.targets);
  });
  L.circleMarker(gridToLeaflet([grid.habitat.row, grid.habitat.col]), {
    radius: 8, color: "#080d16", weight: 3, fillColor: "#68e1fd", fillOpacity: 1,
    pane: "targets-pane",
  }).bindTooltip(`Habitat · return ${grid.legs.at(-1).distance_km.toFixed(3)} km · ${grid.legs.at(-1).time_h.toFixed(3)} h`)
    .bindPopup("<strong>Habitat</strong><br>Placeholder departure point.").addTo(layers.targets);
  layers.targets.addTo(window.map);

  document.getElementById("distance").textContent = formatNumber(stats.distance_km, "km", 3);
  document.getElementById("time").textContent = formatNumber(stats.time_h, "h", 3);
  document.getElementById("margin").textContent = formatNumber(stats.return_margin_h, "h", 3);
  document.getElementById("dose").textContent = formatNumber(stats.est_dose_msv, "mSv", 4);
  const safetyStatus = document.getElementById("safety-status");
  const withinLimit = stats.return_margin_h >= 0;
  const tightMargin = withinLimit && stats.return_margin_h < 0.25;
  safetyStatus.textContent = !withinLimit
    ? "OVER EVA LIMIT"
    : tightMargin ? "LOW RETURN MARGIN" : "WITHIN EVA LIMIT";
  safetyStatus.classList.toggle("warning", !withinLimit);
  safetyStatus.classList.toggle("caution", tightMargin);
  document.getElementById("load-status").textContent =
    "Real DEM and CTX imagery loaded. Habitat and target coordinates are placeholders.";
}

async function loadPlanner() {
  window.map = L.map("map", {
    crs: L.CRS.Simple,
    zoomControl: false,
    attributionControl: false,
  });
  const paneOrder = {
    imagery: 205,
    terrain: 210,
    slope: 220,
    hazard: 230,
    route: 450,
    targets: 460,
  };
  Object.entries(paneOrder).forEach(([name, zIndex]) => {
    const pane = window.map.createPane(`${name}-pane`);
    pane.style.zIndex = zIndex;
  });
  L.control.zoom({ position: "bottomright" }).addTo(window.map);
  addNorthArrow(window.map);
  const siteSelect = document.getElementById("site-select");
  siteSelect.addEventListener("change", () => loadSite(siteSelect.value).catch((error) => {
    console.error(error);
    document.getElementById("load-status").textContent = "Could not load this site's processed layers.";
  }));
  setLayerControl("terrain", "terrain-toggle", "terrain-opacity");
  setLayerControl("imagery", "imagery-toggle", "imagery-opacity");
  setLayerControl("slope", "slope-toggle", "slope-opacity");
  setLayerControl("hazard", "hazard-toggle", "hazard-opacity");
  setLayerControl("route", "route-toggle", "route-opacity");
  setLayerControl("targets", "targets-toggle", "targets-opacity");
  const checkpointToggle = document.getElementById("checkpoint-toggle");
  checkpointToggle.addEventListener("click", () => {
    const details = document.getElementById("checkpoint-details");
    const expanded = checkpointToggle.getAttribute("aria-expanded") === "true";
    checkpointToggle.setAttribute("aria-expanded", String(!expanded));
    checkpointToggle.innerHTML = `${expanded ? "Show details" : "Hide details"} <i></i>`;
    document.querySelector(".map-route-chip").classList.toggle("is-expanded", !expanded);
    details.hidden = expanded;
  });
  window.map.on("mousemove", (event) => {
    if (!window.grid) return;
    const grid = window.grid;
    const cell = inspectCell(grid, event.latlng);
    const eastKm = (cell.col - grid.habitat.col) * grid.cell_size_m.x / 1000;
    const northKm = (event.latlng.lat - gridToLeaflet([grid.habitat.row, 0])[0])
      * grid.cell_size_m.y / 1000;
    const rangeKm = Math.hypot(eastKm, northKm);
    const latitude = cell.latLon.lat.toFixed(5);
    const longitude = cell.latLon.lon.toFixed(5);
    document.getElementById("coordinate-readout").textContent =
      `Lat ${latitude} · Lon ${longitude}`;
    document.getElementById("map-inspector").innerHTML =
      "<span class=\"inspector-kicker\">TERRAIN INSPECTOR</span>"
      + `<strong class="inspector-coordinate">${latitude}°, ${longitude}°</strong>`
      + `<span class="inspector-terrain">Grid ${cell.row}, ${cell.col} · real elevation layer</span>`
      + `<span class="inspector-distance">From Habitat: ${rangeKm.toFixed(2)} km</span>`;
  });
  await loadSite(siteSelect.value);
  addScaleBar(window.map, window.grid);
  addResetControl(window.map, window.siteBounds);
  addZoomPercentageControl(window.map, window.mapMinZoom);
}

setupSidebarResizer();
loadPlanner().catch((error) => {
  console.error(error);
  document.getElementById("load-status").textContent = "Could not load processed layers.";
});
