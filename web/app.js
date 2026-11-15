const layers = {};
const siteLayers = {};
const siteData = {};
const SITE_OPTIONS = {
  site1: "Gale crater floor",
  site2: "Southern box",
};
let selectedSite = null;
let pendingSite = null;
let backdropBounds = null;

function formatNumber(value, unit, digits = 2) {
  return `${Number(value).toFixed(digits)} ${unit}`;
}

function makeImageOverlay(path, bounds, pane, options = {}) {
  return L.imageOverlay(`/${path}`, bounds, { pane, ...options });
}

function setLayerControl(name, toggleId, opacityId) {
  const toggle = document.getElementById(toggleId);
  const opacity = document.getElementById(opacityId);
  toggle.addEventListener("change", () => {
    Object.values(siteLayers).forEach((site) => {
      setLayerVisible(site[name], site === siteLayers[selectedSite] && toggle.checked);
    });
  });
  opacity.addEventListener("input", () => {
    Object.values(siteLayers).forEach((site) => {
      setLayerOpacity(site[name], Number(opacity.value));
    });
  });
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
  if (!layer) return;
  layer._desiredOpacity = value;
  if (layer.setOpacity) {
    layer.setOpacity(layer._siteVisible ? value : 0);
  } else if (layer.setStyle) {
    layer.setStyle({
      opacity: layer._siteVisible ? value : 0,
      fillOpacity: layer._siteVisible ? value : 0,
    });
  } else if (layer.eachLayer) {
    layer.eachLayer((child) => setLayerOpacity(child, value));
  }
}

function setLayerVisible(layer, visible) {
  if (!layer) return;
  layer._siteVisible = visible;
  const opacity = layer._desiredOpacity ?? 1;
  if (layer.setOpacity) {
    layer.setOpacity(visible ? opacity : 0);
  } else if (layer.setStyle) {
    layer.setStyle({
      opacity: visible ? opacity : 0,
      fillOpacity: visible ? opacity : 0,
    });
  } else if (layer.eachLayer) {
    layer.eachLayer((child) => setLayerVisible(child, visible));
  }
}

function addScaleBar(map) {
  const control = L.control({ position: "bottomleft" });
  control.onAdd = () => {
    const element = L.DomUtil.create("div", "map-scale");
    const scaleValuesM = [
      10, 20, 50, 100, 200, 500, 1000, 2000, 5000,
      10000, 20000, 50000, 100000, 200000,
    ];
    element.setAttribute("aria-label", "Map scale");
    const update = () => {
      const start = map.latLngToContainerPoint([0, 0]);
      const oneCell = map.latLngToContainerPoint([0, 1]);
      const metersPixels = Math.abs(oneCell.x - start.x);
      const targetPixels = 120;
      const maxScaleM = targetPixels / metersPixels;
      const desiredM = scaleValuesM.reduce(
        (value, candidate) => candidate <= maxScaleM ? candidate : value,
        scaleValuesM[0],
      );
      const scalePixels = desiredM * metersPixels;
      const label = desiredM < 1000 ? `${desiredM} m` : `${desiredM / 1000} km`;
      element.style.width = `${Math.max(40, Math.min(targetPixels, scalePixels))}px`;
      element.textContent = label;
    };
    map.on("zoomend moveend", update);
    update();
    return element;
  };
  control.addTo(map);
}

function createNorthArrow() {
  const element = L.DomUtil.create("div", "north-arrow");
  element.setAttribute("aria-label", "Grid north");
  element.innerHTML = "<span class=\"north-arrow-label\">GRID NORTH</span>"
    + "<span class=\"north-arrow-compass\"><i></i><b>N</b></span>";
  return element;
}

function createResetControl(map, bounds) {
  const button = L.DomUtil.create("button", "map-action");
  button.type = "button";
  button.textContent = "Reset view";
  button.title = "Fit the full mission area";
  L.DomEvent.on(button, "click", () => {
    map.fitBounds(bounds, { padding: [24, 24] });
  });
  return button;
}

function createZoomPercentageControl(map, minZoom) {
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
  L.DomEvent.on(slider, "input", () => {
    map.setZoom((window.mapMinZoom || minZoom) + Math.log2(Number(slider.value) / 100));
  });
  map.on("zoomend", sync);
  sync();
  return element;
}

function createZoomButtons(map) {
  const element = L.DomUtil.create("div", "map-zoom-buttons");
  const zoomIn = L.DomUtil.create("button", "map-zoom-button", element);
  zoomIn.type = "button";
  zoomIn.textContent = "+";
  zoomIn.setAttribute("aria-label", "Zoom in");
  const zoomOut = L.DomUtil.create("button", "map-zoom-button", element);
  zoomOut.type = "button";
  zoomOut.textContent = "−";
  zoomOut.setAttribute("aria-label", "Zoom out");
  L.DomEvent.on(zoomIn, "click", () => map.zoomIn());
  L.DomEvent.on(zoomOut, "click", () => map.zoomOut());
  return element;
}

function addNavigationDock(map, bounds, minZoom) {
  const control = L.control({ position: "bottomright" });
  control.onAdd = () => {
    const dock = L.DomUtil.create("div", "map-control-dock");
    const toggle = L.DomUtil.create("button", "map-control-dock-toggle", dock);
    toggle.type = "button";
    toggle.setAttribute("aria-expanded", "false");
    toggle.setAttribute("aria-controls", "map-navigation-panel");
    toggle.innerHTML = "<span class=\"map-control-dock-label\">MAP TOOLS</span>"
      + "<i aria-hidden=\"true\"></i>";
    const panel = L.DomUtil.create("div", "map-control-dock-panel", dock);
    panel.id = "map-navigation-panel";
    panel.hidden = true;
    panel.append(
      createZoomPercentageControl(map, minZoom),
      createResetControl(map, bounds),
      createNorthArrow(),
      createZoomButtons(map),
    );
    L.DomEvent.disableClickPropagation(dock);
    L.DomEvent.on(toggle, "click", () => {
      const isOpen = !panel.hidden;
      panel.hidden = isOpen;
      dock.classList.toggle("is-open", !isOpen);
      toggle.setAttribute("aria-expanded", String(!isOpen));
    });
    return dock;
  };
  control.addTo(map);
}

function renderCoordinateStatus({ latitude, longitude, row, col, rangeKm, gridLabel } = {}) {
  const status = document.getElementById("map-inspector");
  if (!latitude) {
    status.innerHTML =
      '<span class="statusbar-label">COORDINATES</span>'
      + '<strong class="statusbar-coordinate">LAT --° · LON --°</strong>'
      + '<span class="statusbar-grid">GRID --</span>'
      + '<span class="statusbar-distance">FROM HABITAT --</span>';
    return;
  }
  status.innerHTML =
    '<span class="statusbar-label">COORDINATES</span>'
    + `<strong class="statusbar-coordinate">LAT ${latitude}° · LON ${longitude}°</strong>`
    + `<span class="statusbar-grid">${gridLabel || `GRID ${row}, ${col}`}</span>`
    + `<span class="statusbar-distance">FROM HABITAT ${rangeKm.toFixed(2)} KM</span>`;
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

function jumpToCheckpoint(checkpointId) {
  if (!selectedSite) return;
  const site = siteData[selectedSite];
  const point = checkpointId === "habitat" || checkpointId === "return"
    ? site.grid.habitat
    : site.grid.targets.find((target) => target.id === checkpointId);
  if (!point) return;
  const zoom = Math.min(window.map.getMaxZoom(), window.siteMinZoom + 3);
  window.map.flyTo(gridToMap(site, point.row, point.col), zoom, { duration: 0.45 });
  document.querySelectorAll(".checkpoint").forEach((checkpoint) => {
    checkpoint.classList.toggle("is-selected", checkpoint.dataset.checkpoint === checkpointId);
  });
}

function buildSiteLayers(siteKey, stats, grid) {
  const site = { key: siteKey, name: grid.site_name, stats, grid };
  site.bounds = boundsToMap(grid.geo_reference.bounds);
  const outboundPixels = grid.route_segments.slice(0, -1).flatMap((segment, index) =>
    index === 0 ? segment : segment.slice(1));
  const returnPixels = grid.route_segments.at(-1);
  const route = L.layerGroup([
    L.polyline(outboundPixels.map(([row, col]) => gridToMap(site, row, col)), {
      color: "#080d16", weight: 7, opacity: .9, lineCap: "round", lineJoin: "round",
      pane: "route-pane",
    }),
    L.polyline(outboundPixels.map(([row, col]) => gridToMap(site, row, col)), {
      color: "#fbbf24", weight: 3, opacity: 1, dashArray: "10 8",
      lineCap: "round", lineJoin: "round", pane: "route-pane",
    }).bindTooltip("Outbound leg · Habitat → science targets"),
    L.polyline(returnPixels.map(([row, col]) => gridToMap(site, row, col)), {
      color: "#080d16", weight: 8, opacity: .9, lineCap: "round", lineJoin: "round",
      pane: "route-pane",
    }),
    L.polyline(returnPixels.map(([row, col]) => gridToMap(site, row, col)), {
      color: "#68e1fd", weight: 4, opacity: 1,
      lineCap: "round", lineJoin: "round", pane: "route-pane",
    }).bindTooltip("Return leg · Target 3 → Habitat"),
  ]).addTo(window.map);
  const targets = L.layerGroup();
  grid.targets.forEach((target) => {
    const marker = L.circleMarker(gridToMap(site, target.row, target.col), {
      radius: 9, color: "#080d16", weight: 3, fillColor: "#fbbf24", fillOpacity: 1,
      pane: "targets-pane",
    });
    const label = `Target ${target.id.split("-")[1]}`;
    const leg = grid.legs.find((item) => item.name === target.id);
    marker.bindTooltip(`${label} · ${leg.distance_km.toFixed(3)} km · ${leg.time_h.toFixed(3)} h`);
    marker.bindPopup(`<strong>${label}</strong><div class="photo-slot">CTX imagery<br>real surface preview</div>`);
    marker.addTo(targets);
  });
  L.circleMarker(gridToMap(site, grid.habitat.row, grid.habitat.col), {
    radius: 8, color: "#080d16", weight: 3, fillColor: "#68e1fd", fillOpacity: 1,
    pane: "targets-pane",
  }).bindTooltip(`Habitat · return ${grid.legs.at(-1).distance_km.toFixed(3)} km · ${grid.legs.at(-1).time_h.toFixed(3)} h`)
    .bindPopup("<strong>Habitat</strong><br>Placeholder departure point.").addTo(targets);

  const output = {
    terrain: makeImageOverlay(grid.layer_paths.elevation, site.bounds, "terrain-pane").addTo(window.map),
    imagery: makeImageOverlay(grid.layer_paths.imagery, site.bounds, "imagery-pane").addTo(window.map),
    slope: makeImageOverlay(grid.layer_paths.slope, site.bounds, "slope-pane").addTo(window.map),
    hazard: makeImageOverlay(grid.layer_paths.hazard, site.bounds, "hazard-pane").addTo(window.map),
    route,
    targets,
  };
  const defaults = {
    terrain: .9, imagery: .65, slope: .35, hazard: .7, route: 1, targets: 1,
  };
  Object.entries(output).forEach(([name, layer]) => {
    layer._desiredOpacity = defaults[name];
    setLayerVisible(layer, false);
  });
  siteData[siteKey] = site;
  siteLayers[siteKey] = output;
}

function updateSiteSummary(site) {
  const { grid, stats } = site;
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
    "Real DEM, CTX imagery and lower-resolution surrounding NASA context loaded. Habitat and target coordinates are placeholders.";
  document.getElementById("site-name").textContent = grid.site_name;
  document.getElementById("site-region").textContent = "Real NASA data";
  document.getElementById("site-select").value = site.key;
  document.getElementById("slope-limit").textContent = `${grid.max_walkable_slope_deg}°+`;
  renderCheckpointDetails(grid, stats);
  renderCoordinateStatus();
}

function activateSite(siteKey) {
  selectedSite = siteKey;
  const site = siteData[siteKey];
  window.siteMinZoom = window.map.getBoundsZoom(site.bounds);
  window.siteBounds = site.bounds;
  Object.keys(siteLayers).forEach((key) => {
    const active = key === siteKey;
    Object.entries(siteLayers[key]).forEach(([name, layer]) => {
      const toggle = document.getElementById(`${name}-toggle`);
      setLayerVisible(layer, active && toggle.checked);
    });
  });
  Object.assign(layers, siteLayers[siteKey]);
  updateSiteSummary(site);
  layers.boundaries?.eachLayer((boundary) => {
    if (!boundary.setStyle) return;
    boundary.setStyle(boundary._siteKey === siteKey
      ? { color: "#68e1fd", weight: 2, opacity: 1 }
      : { color: "#9c8bd0", weight: 1, opacity: .7 });
  });
}

function flyToSite(siteKey) {
  if (!siteData[siteKey]) return;
  pendingSite = siteKey;
  document.getElementById("site-select").value = siteKey;
  const finish = () => {
    if (pendingSite !== siteKey) return;
    pendingSite = null;
    window.map.off("moveend", finish);
    activateSite(siteKey);
  };
  window.map.once("moveend", finish);
  window.map.flyToBounds(siteData[siteKey].bounds, { duration: 1.2, padding: [24, 24] });
}

async function loadSiteData(siteKey) {
  const root = `/data/processed/${siteKey}/`;
  const [stats, grid] = await Promise.all([
    fetch(`${root}stats.json`).then((response) => response.json()),
    fetch(`${root}grid.json`).then((response) => response.json()),
  ]);
  buildSiteLayers(siteKey, stats, grid);
}

function addSiteBoundaries() {
  const boundaries = L.layerGroup();
  Object.keys(SITE_OPTIONS).forEach((siteKey) => {
    const site = siteData[siteKey];
    const boundary = L.rectangle(site.bounds, {
      color: "#9c8bd0",
      weight: 1,
      opacity: .7,
      fill: false,
      pane: "boundaries-pane",
      className: "site-boundary",
    });
    boundary._siteKey = siteKey;
    boundary.on("click", () => flyToSite(siteKey));
    boundary.addTo(boundaries);
    L.marker([site.bounds[1][0], site.bounds[0][1]], {
      icon: L.divIcon({ className: "site-boundary-label-anchor", iconSize: [0, 0] }),
      interactive: false,
      pane: "boundaries-pane",
    }).bindTooltip(site.name, {
      permanent: true,
      direction: "right",
      offset: [4, 2],
      className: "site-boundary-label",
    }).addTo(boundaries);
  });
  boundaries.addTo(window.map);
  layers.boundaries = boundaries;
}

function addBackdrop(backdrop) {
  const imagery = backdrop.layers.imagery;
  const hillshade = backdrop.layers.hillshade;
  const imageryBounds = boundsToMap(imagery.bounds);
  const hillshadeBounds = boundsToMap(hillshade.bounds);
  const imageryLayer = makeImageOverlay(imagery.path, imageryBounds, "backdrop-imagery-pane", {
    opacity: .7,
  }).addTo(window.map);
  const hillshadeLayer = makeImageOverlay(hillshade.path, hillshadeBounds, "backdrop-hillshade-pane", {
    opacity: .7,
  }).addTo(window.map);
  backdropBounds = mapBoundsUnion([imageryBounds, hillshadeBounds]);
  layers.backdrop = L.layerGroup([imageryLayer, hillshadeLayer]);
  const spanY = backdropBounds[1][0] - backdropBounds[0][0];
  const spanX = backdropBounds[1][1] - backdropBounds[0][1];
  const labelPoint = [
    backdropBounds[1][0] - spanY * .1,
    backdropBounds[0][1] + spanX * .36,
  ];
  L.marker(labelPoint, {
    icon: L.divIcon({
      className: "backdrop-context-label",
      html: "Surrounding area: low resolution,<br>context only, no route data · real NASA data",
    }),
    interactive: false,
    pane: "boundaries-pane",
  }).addTo(window.map);
}

async function loadPlanner() {
  const backdrop = await fetch("data/backdrop.json").then((response) => response.json());
  setGeoReference(backdrop);
  window.map = L.map("map", {
    crs: L.CRS.Simple,
    minZoom: -12,
    maxZoom: 18,
    zoomControl: false,
    attributionControl: false,
  });
  const paneOrder = {
    "backdrop-imagery": 100,
    "backdrop-hillshade": 110,
    imagery: 205,
    terrain: 210,
    slope: 220,
    hazard: 230,
    boundaries: 440,
    route: 450,
    targets: 460,
  };
  Object.entries(paneOrder).forEach(([name, zIndex]) => {
    const pane = window.map.createPane(`${name}-pane`);
    pane.style.zIndex = zIndex;
  });
  addBackdrop(backdrop);
  const paddedBackdropBounds = padMapBounds(backdropBounds);
  const backdropMinZoom = window.map.getBoundsZoom(backdropBounds);
  window.map.setMaxBounds(paddedBackdropBounds);
  window.map.setMinZoom(backdropMinZoom);
  window.mapMinZoom = backdropMinZoom;

  const siteSelect = document.getElementById("site-select");
  siteSelect.addEventListener("change", () => flyToSite(siteSelect.value));
  setLayerControl("terrain", "terrain-toggle", "terrain-opacity");
  setLayerControl("imagery", "imagery-toggle", "imagery-opacity");
  setLayerControl("slope", "slope-toggle", "slope-opacity");
  setLayerControl("hazard", "hazard-toggle", "hazard-opacity");
  setLayerControl("route", "route-toggle", "route-opacity");
  setLayerControl("targets", "targets-toggle", "targets-opacity");
  const checkpointToggle = document.getElementById("checkpoint-toggle");
  checkpointToggle.addEventListener("click", () => {
    const chip = document.querySelector(".map-route-chip");
    const expanded = chip.classList.toggle("is-expanded");
    chip.classList.toggle("is-collapsed", !expanded);
    checkpointToggle.setAttribute("aria-expanded", String(expanded));
    checkpointToggle.innerHTML = `${expanded ? "Collapse" : "Expand"} <i></i>`;
  });
  document.getElementById("checkpoint-track").addEventListener("click", (event) => {
    const checkpoint = event.target.closest(".checkpoint");
    if (checkpoint) jumpToCheckpoint(checkpoint.dataset.checkpoint);
  });
  window.map.on("mousemove", (event) => {
    if (!selectedSite) return;
    const site = siteData[selectedSite];
    const mapPosition = event.latlng;
    const location = mapToLatLon(mapPosition[0], mapPosition[1]);
    const cell = mapToGrid(site, mapPosition[0], mapPosition[1]);
    const habitat = gridToMap(site, site.grid.habitat.row, site.grid.habitat.col);
    const rangeKm = Math.hypot(
      mapPosition[0] - habitat[0],
      mapPosition[1] - habitat[1],
    ) / 1000;
    const latitude = location.lat.toFixed(5);
    const longitude = location.lon.toFixed(5);
    document.getElementById("coordinate-readout").textContent =
      `Lat ${latitude} · Lon ${longitude}`;
    renderCoordinateStatus({
      latitude,
      longitude,
      row: cell.row,
      col: cell.col,
      rangeKm,
      gridLabel: cell.inside ? `GRID ${cell.row}, ${cell.col}` : "SURROUNDING AREA",
    });
  });
  await Promise.all(Object.keys(SITE_OPTIONS).map((site) => loadSiteData(site)));
  addSiteBoundaries();
  activateSite(siteSelect.value);
  window.map.fitBounds(backdropBounds, { padding: [24, 24] });
  addScaleBar(window.map);
  addNavigationDock(window.map, backdropBounds, backdropMinZoom);
}

setupSidebarResizer();
loadPlanner().catch((error) => {
  console.error(error);
  document.getElementById("load-status").textContent = "Could not load processed layers.";
});
