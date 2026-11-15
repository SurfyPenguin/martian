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
let routeMode = false;
const ALGORITHM_DESCRIPTIONS = {
  astar: "A* uses an octile-distance heuristic and is guaranteed optimal for this cost grid.",
  dijkstra: "Dijkstra expands without a heuristic; it is guaranteed optimal but explores more cells.",
  weighted: "Weighted A* biases toward the goal for speed; it is near-optimal, not guaranteed optimal.",
};

function formatNumber(value, unit, digits = 2) {
  return `${Number(value).toFixed(digits)} ${unit}`;
}

function selectedRoute(site) {
  return site.routeChoices.find((choice) => choice.key === site.selectedRouteKey)
    ?? site.routeChoices[0];
}

function updateAlgorithmControl(site) {
  const algorithm = document.getElementById("route-algorithm");
  const description = site.algorithm === "weighted"
    ? `${ALGORITHM_DESCRIPTIONS.weighted} Current epsilon: ${site.epsilon.toFixed(1)}.`
    : ALGORITHM_DESCRIPTIONS[site.algorithm];
  algorithm.value = site.algorithm;
  algorithm.title = description;
  document.getElementById("algorithm-description").textContent = description;
  const epsilonControl = document.getElementById("weighted-epsilon-control");
  epsilonControl.hidden = site.algorithm !== "weighted";
  document.getElementById("weighted-epsilon").value = String(site.epsilon);
  document.getElementById("weighted-epsilon-value").textContent = site.epsilon.toFixed(1);
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

function setupSidebarToggle(map) {
  const shell = document.querySelector(".shell");
  const toggle = document.getElementById("sidebar-toggle");
  const reopen = document.getElementById("sidebar-reopen");
  const setCollapsed = (collapsed) => {
    shell.classList.toggle("is-sidebar-collapsed", collapsed);
    toggle.setAttribute("aria-expanded", String(!collapsed));
    toggle.setAttribute("aria-label", collapsed
      ? "Mission panel hidden"
      : "Hide mission panel to view the map");
    reopen.hidden = !collapsed;
    requestAnimationFrame(() => map.invalidateSize({ pan: false }));
  };
  toggle.addEventListener("click", () => setCollapsed(true));
  reopen.addEventListener("click", () => setCollapsed(false));
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
      const start = map.project([0, 0]);
      const kilometer = map.project([0, 1000]);
      const metersPixels = Math.abs(kilometer.x - start.x) / 1000;
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

function nearestFreeCell(site, row, col, safetyMarginCells = site.safetyMarginCells) {
  let nearest = null;
  for (let index = 0; index < site.routeGrid.costs.length; index += 1) {
    const nextRow = Math.floor(index / site.routeGrid.cols);
    const nextCol = index % site.routeGrid.cols;
    if (!RoutePlanner.isWalkable(
      site.routeGrid,
      nextRow,
      nextCol,
      safetyMarginCells,
    )) continue;
    const rowOffset = nextRow - row;
    const colOffset = nextCol - col;
    const distanceSquared = (rowOffset * site.routeGrid.cellSizeM.y) ** 2
      + (colOffset * site.routeGrid.cellSizeM.x) ** 2;
    if (!nearest || distanceSquared < nearest.distanceSquared) {
      nearest = {
        row: nextRow,
        col: nextCol,
        distanceCells: Math.hypot(rowOffset, colOffset),
        distanceMeters: Math.sqrt(distanceSquared),
        distanceSquared,
      };
    }
  }
  return nearest;
}

function setRouteMessage(message, isError = false) {
  const status = document.getElementById("route-status");
  status.textContent = message;
  status.classList.toggle("is-error", isError);
}

function setRouteMode(enabled) {
  routeMode = enabled;
  const button = document.getElementById("add-checkpoint");
  button.textContent = enabled ? "Click map" : "Add checkpoint";
  button.setAttribute("aria-pressed", String(enabled));
  document.getElementById("map").classList.toggle("is-route-mode", enabled);
  setRouteMessage(enabled
    ? "Choose a point inside the active site."
    : "");
}

function recalculateSiteRoute(site, changedCheckpointIndex = null) {
  const previousPlan = site.plan;
  site.plan = RoutePlanner.planRoute(
    site.routeGrid,
    site.grid.habitat,
    site.checkpoints,
    site.returnToHabitat,
    changedCheckpointIndex === null ? null : previousPlan,
    changedCheckpointIndex,
    site.safetyMarginCells,
    { algorithm: site.algorithm, epsilon: site.epsilon },
  );
  site.selectedRouteKey = "fastest";
  site.routeChoices = [{ key: "fastest", name: "Fastest", plan: site.plan }];
  const requestId = site.alternativesRequestId + 1;
  site.alternativesRequestId = requestId;
  if (selectedSite === site.key) updateSiteSummary(site);
  else updateCheckpointUI(site);
  setRouteMessage("Fastest route ready; calculating alternatives.");
  window.setTimeout(() => {
    if (site.alternativesRequestId !== requestId) return;
    const choices = RoutePlanner.computeAlternatives(
      site.routeGrid,
      site.grid.habitat,
      site.checkpoints,
      site.returnToHabitat,
      site.plan,
      {
        safetyMarginCells: site.safetyMarginCells,
        algorithm: site.algorithm,
        epsilon: site.epsilon,
      },
    );
    if (site.alternativesRequestId !== requestId) return;
    site.routeChoices = choices;
    if (selectedSite === site.key) updateSiteSummary(site);
    else updateCheckpointUI(site);
    if (document.getElementById("route-status").textContent
      === "Fastest route ready; calculating alternatives.") {
      setRouteMessage(choices.length === 1 && site.plan.timeH !== null
        ? "Only one valid route found for this checkpoint sequence."
        : site.endpointSnapMessage || "");
    }
  }, 0);
}

function removeCheckpoint(site, index) {
  if (index < 0 || index >= site.checkpoints.length) return;
  window.map.closePopup();
  site.checkpoints.splice(index, 1);
  recalculateSiteRoute(site);
  setRouteMessage(`Checkpoint ${index + 1} deleted; remaining legs recalculated.`);
}

function addCheckpointAt(latlng) {
  if (!routeMode || !selectedSite) return;
  const site = siteData[selectedSite];
  const cell = mapToGrid(site, latlng.lat, latlng.lng);
  if (!cell.inside) {
    setRouteMessage("Outside planning area, no route data.", true);
    return;
  }
  const snapped = nearestFreeCell(site, cell.row, cell.col);
  if (!snapped) {
    setRouteMessage("No free cell remains at this safety margin.", true);
    return;
  }
  site.checkpoints.push({ row: snapped.row, col: snapped.col });
  recalculateSiteRoute(site);
  setRouteMessage(snapped.distanceCells
    ? `Checkpoint added and snapped ${snapped.distanceMeters.toFixed(1)} m clear of hazards.`
    : `Checkpoint ${site.checkpoints.length} added; route recalculated.`);
}

function renderCheckpointTrack(site) {
  const track = document.getElementById("checkpoint-track");
  track.replaceChildren();
  const stops = [
    { id: "habitat", label: "Habitat", start: true },
    ...site.checkpoints.map((point, index) => ({
      id: `checkpoint-${index}`,
      label: `C${index + 1}`,
    })),
  ];
  if (site.returnToHabitat) stops.push({ id: "return", label: "Habitat", end: true });
  stops.forEach((stop) => {
    const button = document.createElement("button");
    button.className = `checkpoint${stop.start ? " checkpoint-start" : ""}`
      + `${stop.end ? " checkpoint-end" : ""}`;
    button.type = "button";
    button.dataset.checkpoint = stop.id;
    button.setAttribute("aria-label", `Jump to ${stop.label}`);
    const marker = document.createElement("i");
    const label = document.createElement("span");
    label.textContent = stop.label;
    button.append(marker, label);
    track.append(button);
  });
}

function renderCheckpointDetails(site) {
  const { grid } = site;
  const plan = selectedRoute(site).plan;
  const details = [
    { id: "habitat", label: "Habitat", point: grid.habitat, leg: null },
    ...site.checkpoints.map((point, index) => ({
      id: `checkpoint-${index}`,
      label: `Checkpoint ${index + 1}`,
      point,
      leg: plan.legs[index],
    })),
  ];
  if (site.returnToHabitat) {
    details.push({
      id: "return",
      label: "Return",
      point: grid.habitat,
      leg: plan.legs.at(-1),
    });
  }
  document.getElementById("checkpoint-summary").textContent = plan.unreachable
    ? "No safe path for one or more legs"
    : `${plan.distanceKm.toFixed(3)} km total · ${plan.timeH.toFixed(3)} h EVA · `
      + `${plan.returnMarginH.toFixed(3)} h margin`;
  document.getElementById("checkpoint-leg-list").replaceChildren(
    ...details.map((item) => {
      const location = mapToLatLon(...gridToMap(site, item.point.row, item.point.col));
      const meta = item.leg?.unreachable
        ? "No safe path"
        : item.leg
          ? `${item.leg.distanceKm.toFixed(3)} km · ${item.leg.timeH.toFixed(3)} h`
          : "Departure point";
      const button = document.createElement("button");
      button.type = "button";
      button.className = "checkpoint-detail checkpoint-detail-jump";
      button.dataset.checkpoint = item.id;
      button.innerHTML = `<span class="checkpoint-detail-label">${item.label}</span>`
        + `<span class="checkpoint-detail-meta">${meta}</span>`
        + `<span class="checkpoint-detail-coord">${location.lat.toFixed(5)}°, `
        + `${location.lon.toFixed(5)}°</span>`;
      return button;
    }),
  );
}

function renderCheckpointMarkers(site) {
  site.checkpointMarkers.clearLayers();
  site.checkpoints.forEach((point, index) => {
    const marker = L.marker(gridToMap(site, point.row, point.col), {
      icon: L.divIcon({
        className: "manual-checkpoint-icon",
        html: `<span>${index + 1}</span>`,
        iconSize: [26, 26],
        iconAnchor: [13, 13],
      }),
      draggable: true,
      pane: "targets-pane",
      zIndexOffset: 500,
      bubblingMouseEvents: false,
    });
    marker.bindTooltip(`Checkpoint ${index + 1} · drag to move`);
    marker.bindPopup(
      `<div class="checkpoint-popup"><strong>Checkpoint ${index + 1}</strong>`
      + `<button type="button" class="checkpoint-delete">Delete checkpoint</button>`
      + `<button type="button" class="checkpoint-cancel">Cancel</button></div>`,
    );
    marker.on("popupopen", (event) => {
      const popup = event.popup.getElement();
      popup.querySelector(".checkpoint-delete").addEventListener("click", () => {
        removeCheckpoint(site, index);
      });
      popup.querySelector(".checkpoint-cancel").addEventListener("click", () => {
        window.map.closePopup();
      });
    });
    marker.on("dragend", (event) => {
      const current = site.checkpoints[index];
      const cell = mapToGrid(site, event.target.getLatLng().lat, event.target.getLatLng().lng);
      const snapped = cell.inside
        ? nearestFreeCell(site, cell.row, cell.col)
        : null;
      if (!snapped) {
        marker.setLatLng(gridToMap(site, current.row, current.col));
        setRouteMessage(cell.inside
          ? "No free cell remains at this safety margin; checkpoint kept at its previous location."
          : "Checkpoint must remain inside the active site.", true);
        return;
      }
      site.checkpoints[index] = { row: snapped.row, col: snapped.col };
      recalculateSiteRoute(site, index);
      setRouteMessage(snapped.distanceCells
        ? `Checkpoint moved ${snapped.distanceMeters.toFixed(1)} m clear of hazards.`
        : "Checkpoint moved; adjacent route legs recalculated.");
    });
    marker.addTo(site.checkpointMarkers);
  });
}

function renderRoute(site) {
  const route = siteLayers[site.key].route;
  route.clearLayers();
  const choices = [...site.routeChoices].sort((left, right) => (
    Number(left.key === site.selectedRouteKey) - Number(right.key === site.selectedRouteKey)
  ));
  choices.forEach((choice) => {
    const isSelected = choice.key === site.selectedRouteKey;
    choice.plan.legs.forEach((leg, index) => {
      if (leg.unreachable) return;
      const positions = leg.path.map(([row, col]) => gridToMap(site, row, col));
      if (positions.length < 2) return;
      L.polyline(positions, {
        color: isSelected ? "#c3adff" : "#8a8a8a",
        weight: isSelected ? 4 : 2,
        opacity: isSelected ? .95 : .55,
        lineCap: "round",
        lineJoin: "round",
        bubblingMouseEvents: false,
        pane: "route-pane",
      }).bindTooltip(`${choice.name} · leg ${index + 1}`)
        .on("click", () => selectRoute(site, choice.key))
        .addTo(route);
    });
  });
  const routeToggle = document.getElementById("route-toggle");
  setLayerVisible(route, selectedSite === site.key && routeToggle.checked);
}

function renderRouteCards(site) {
  const container = document.getElementById("route-cards");
  const fastest = site.routeChoices.find((choice) => choice.key === "fastest")?.plan;
  container.replaceChildren(...site.routeChoices.map((choice) => {
    const { plan } = choice;
    const button = document.createElement("button");
    const withinLimit = plan.timeH !== null
      && plan.timeH <= site.routeGrid.parameters.eva_hours;
    button.type = "button";
    button.className = `route-card${choice.key === site.selectedRouteKey ? " is-selected" : ""}`;
    button.dataset.routeKey = choice.key;
    button.setAttribute("aria-pressed", String(choice.key === site.selectedRouteKey));
    button.title = `${choice.name}: ${plan.computationMs.toFixed(1)} ms, `
      + `${plan.exploredCells} cells explored`;
    const name = document.createElement("span");
    name.className = "route-card-name";
    name.textContent = choice.name;
    const metrics = document.createElement("span");
    metrics.className = "route-card-metrics";
    metrics.textContent = plan.timeH === null
      ? "No safe route"
      : `${plan.timeH.toFixed(2)} h · ${plan.distanceKm.toFixed(2)} km · `
        + `${plan.doseMsv.toFixed(4)} mSv`;
    const clearance = document.createElement("span");
    clearance.className = "route-card-clearance";
    const differenceMinutes = !fastest || fastest.timeH === null || plan.timeH === null
      ? null
      : Math.round((plan.timeH - fastest.timeH) * 60);
    const difference = choice.key === "fastest"
      ? "0 min"
      : differenceMinutes === null
      ? "time unavailable"
      : differenceMinutes > 0
        ? `+${differenceMinutes} min`
        : differenceMinutes < 0 ? `${differenceMinutes} min` : "same time";
    clearance.textContent = `Min clearance ${plan.minimumClearanceM?.toFixed(1) ?? "--"} m · ${difference}`;
    const compute = document.createElement("span");
    compute.className = "route-card-compute";
    compute.textContent = `${plan.computationMs.toFixed(1)} ms · `
      + `${plan.exploredCells.toLocaleString()} cells explored`;
    const badge = document.createElement("span");
    badge.className = `route-card-badge${withinLimit ? "" : " is-over"}`;
    badge.textContent = plan.unreachable
      ? "NO SAFE PATH"
      : withinLimit ? "WITHIN EVA LIMIT" : "OVER EVA LIMIT";
    button.append(name, metrics, clearance, compute, badge);
    return button;
  }));
}

function selectRoute(site, routeKey) {
  if (!site.routeChoices.some((choice) => choice.key === routeKey)) return;
  site.selectedRouteKey = routeKey;
  if (selectedSite === site.key) updateSiteSummary(site);
  else updateCheckpointUI(site);
}

function updateCheckpointUI(site) {
  renderCheckpointTrack(site);
  renderCheckpointDetails(site);
  renderCheckpointMarkers(site);
  renderRouteCards(site);
  setLayerVisible(
    siteLayers[site.key].targets,
    selectedSite === site.key && document.getElementById("targets-toggle").checked,
  );
  renderRoute(site);
  document.getElementById("return-to-habitat").checked = site.returnToHabitat;
  document.getElementById("undo-checkpoint").disabled = site.checkpoints.length === 0;
  document.getElementById("clear-checkpoints").disabled = site.checkpoints.length === 0;
}

function jumpToCheckpoint(checkpointId) {
  if (!selectedSite) return;
  const site = siteData[selectedSite];
  const point = checkpointId === "habitat" || checkpointId === "return"
    ? site.grid.habitat
    : site.checkpoints[Number(checkpointId.slice("checkpoint-".length))];
  if (!point) return;
  const zoom = Math.min(window.map.getMaxZoom(), window.siteMinZoom + 3);
  window.map.flyTo(gridToMap(site, point.row, point.col), zoom, { duration: 0.45 });
  document.querySelectorAll(".checkpoint").forEach((checkpoint) => {
    checkpoint.classList.toggle("is-selected", checkpoint.dataset.checkpoint === checkpointId);
  });
}

function buildSiteLayers(siteKey, grid, routeGrid) {
  const site = {
    key: siteKey,
    name: grid.site_name,
    grid,
    routeGrid,
    safetyMarginCells: routeGrid.parameters.safety_margin_cells,
    originalHabitat: { ...grid.habitat },
    originalTargets: grid.targets.map((point) => ({ ...point })),
    checkpoints: grid.targets.map(({ row, col }) => ({ row, col })),
    algorithm: "astar",
    epsilon: routeGrid.parameters.weighted_astar_epsilon,
    returnToHabitat: true,
    checkpointMarkers: null,
    plan: null,
    routeChoices: [],
    selectedRouteKey: "fastest",
    alternativesRequestId: 0,
  };
  const snappedEndpoints = [grid.habitat, ...grid.targets]
    .filter((point) => point.snapped);
  site.endpointSnapMessage = snappedEndpoints.length
    ? `${snappedEndpoints.length} mission point(s) snapped outside the safety margin.`
    : "";
  site.bounds = boundsToMap(grid.geo_reference.bounds);
  const route = L.layerGroup().addTo(window.map);
  const targets = L.layerGroup().addTo(window.map);
  const checkpointMarkers = L.layerGroup().addTo(targets);
  site.checkpointMarkers = checkpointMarkers;
  L.circleMarker(gridToMap(site, grid.habitat.row, grid.habitat.col), {
    radius: 8, color: "#080d16", weight: 3, fillColor: "#68e1fd", fillOpacity: 1,
    pane: "targets-pane", bubblingMouseEvents: false,
  }).bindTooltip("Habitat · placeholder departure point")
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
  renderCheckpointMarkers(site);
  setLayerVisible(output.targets, false);
  recalculateSiteRoute(site);
}

function updateSiteSummary(site) {
  const { grid } = site;
  const plan = selectedRoute(site).plan;
  const parameters = site.routeGrid.parameters;
  document.getElementById("distance").textContent = plan.distanceKm === null
    ? "NO ROUTE"
    : formatNumber(plan.distanceKm, "km", 3);
  document.getElementById("time").textContent = plan.timeH === null
    ? "--"
    : formatNumber(plan.timeH, "h", 3);
  document.getElementById("margin").textContent = plan.returnMarginH === null
    ? "--"
    : formatNumber(plan.returnMarginH, "h", 3);
  document.getElementById("margin-label").textContent = site.returnToHabitat
    ? "Return margin"
    : "EVA margin · return off";
  document.getElementById("dose").textContent = plan.doseMsv === null
    ? "--"
    : formatNumber(plan.doseMsv, "mSv", 4);
  const safetyStatus = document.getElementById("safety-status");
  const withinLimit = plan.timeH !== null && plan.returnMarginH >= 0;
  const tightMargin = withinLimit && plan.returnMarginH < 0.25;
  safetyStatus.textContent = plan.unreachable
    ? "NO SAFE PATH"
    : !withinLimit
      ? "OVER EVA LIMIT"
      : tightMargin ? "LOW EVA MARGIN" : "WITHIN EVA LIMIT";
  safetyStatus.classList.toggle("warning", plan.unreachable || !withinLimit);
  safetyStatus.classList.toggle("caution", !plan.unreachable && tightMargin);
  document.getElementById("load-status").textContent =
    `Live ${site.algorithm === "weighted" ? "Weighted A*" : site.algorithm === "astar" ? "A*" : "Dijkstra"} route uses the shared hazard mask. Habitat and science locations are placeholders.`;
  document.getElementById("site-name").textContent = grid.site_name;
  document.getElementById("site-region").textContent = "Real NASA data";
  document.getElementById("site-select").value = site.key;
  document.getElementById("slope-limit").textContent =
    `${parameters.max_walkable_slope_deg}°+`;
  document.getElementById("safety-margin").value = String(site.safetyMarginCells);
  document.getElementById("safety-margin-value").textContent =
    `${site.safetyMarginCells} cells`;
  const choice = selectedRoute(site);
  document.getElementById("safety-intro").textContent = site.returnToHabitat
    ? `${choice.name} route · return to Habitat included`
    : `${choice.name} route · return to Habitat is off`;
  document.getElementById("route-assumptions").textContent =
    `ASSUMPTIONS · ${parameters.walking_speed_kmh} km/h · `
    + `${parameters.eva_hours} h EVA · `
    + `${parameters.dose_rate_msv_per_hour} mSv/h dose`;
  updateAlgorithmControl(site);
  updateCheckpointUI(site);
  renderCoordinateStatus();
}

function updateSafetyMargin(site, safetyMarginCells) {
  const hasWalkableCell = site.routeGrid.costs.some((cost, index) => (
    Number.isFinite(cost)
      && site.routeGrid.clearanceCells[index] > safetyMarginCells
  ));
  if (!hasWalkableCell) {
    setRouteMessage("No free cells remain at that safety margin.", true);
    return false;
  }

  const snappedMessages = [];
  const snapPoint = (point, label) => {
    const snapped = nearestFreeCell(site, point.row, point.col, safetyMarginCells);
    if (!snapped) throw new Error("No free cell remains at this safety margin.");
    if (snapped.distanceMeters > 0) {
      snappedMessages.push(`${label} moved ${snapped.distanceMeters.toFixed(1)} m`);
    }
    return { ...point, row: snapped.row, col: snapped.col };
  };
  site.safetyMarginCells = safetyMarginCells;
  site.grid.habitat = snapPoint(site.originalHabitat, "Habitat");
  site.grid.targets = site.originalTargets.map((point, index) => (
    snapPoint(point, `Target ${index + 1}`)
  ));
  site.checkpoints = site.checkpoints.map((point, index) => (
    snapPoint(point, `Checkpoint ${index + 1}`)
  ));
  recalculateSiteRoute(site);
  setRouteMessage(snappedMessages.length
    ? `Safety margin ${safetyMarginCells} cells; ${snappedMessages.join(", ")} clear of hazards.`
    : `Safety margin set to ${safetyMarginCells} cells; routes recalculated.`);
  return true;
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
  setRouteMessage(site.endpointSnapMessage);
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
  const processedRoot = `/data/processed/${siteKey}/`;
  const costRoot = `data/${siteKey}/`;
  const [grid, costMetadata] = await Promise.all([
    fetchJson(`${processedRoot}grid.json`),
    fetchJson(`${costRoot}cost.json`),
  ]);
  const costFiles = [
    "cost.bin",
    costMetadata.clearance_files.cells,
    costMetadata.clearance_files.meters,
  ];
  const responses = await Promise.all(costFiles.map((file) => fetch(`${costRoot}${file}`)));
  const failedResponse = responses.find((response) => !response.ok);
  if (failedResponse) {
    throw new Error(
      `Could not load ${siteKey} route data: HTTP ${failedResponse.status}`,
    );
  }
  const [costBuffer, clearanceCellsBuffer, clearanceMetersBuffer] = await Promise.all(
    responses.map((response) => response.arrayBuffer()),
  );
  const routeGrid = RoutePlanner.decodeGrid(
    costMetadata,
    costBuffer,
    clearanceCellsBuffer,
    clearanceMetersBuffer,
  );
  if (routeGrid.site !== siteKey || routeGrid.rows !== grid.rows || routeGrid.cols !== grid.cols) {
    throw new Error(`${siteKey} route grid does not match the site data`);
  }
  buildSiteLayers(siteKey, grid, routeGrid);
}

async function fetchJson(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`Could not load ${url}: HTTP ${response.status}`);
  return response.json();
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
      bubblingMouseEvents: false,
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
    backdropBounds[0][1] + spanX * .04,
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
  const backdrop = await fetchJson("data/backdrop.json");
  setGeoReference(backdrop);
  window.map = L.map("map", {
    crs: L.CRS.Simple,
    minZoom: -12,
    maxZoom: 18,
    zoomControl: false,
    attributionControl: false,
  });
  setupSidebarToggle(window.map);
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
  const routeChip = document.querySelector(".map-route-chip");
  L.DomEvent.disableClickPropagation(routeChip);
  document.getElementById("add-checkpoint").addEventListener("click", () => {
    setRouteMode(!routeMode);
  });
  document.getElementById("auto-plan").addEventListener("click", () => {
    const site = siteData[selectedSite];
    setRouteMode(false);
    site.checkpoints = site.grid.targets.map(({ row, col }) => ({ row, col }));
    recalculateSiteRoute(site);
    setRouteMessage("Auto plan restored the three placeholder science targets.");
  });
  document.getElementById("undo-checkpoint").addEventListener("click", () => {
    const site = siteData[selectedSite];
    if (site.checkpoints.length) removeCheckpoint(site, site.checkpoints.length - 1);
  });
  document.getElementById("clear-checkpoints").addEventListener("click", () => {
    const site = siteData[selectedSite];
    setRouteMode(false);
    site.checkpoints = [];
    recalculateSiteRoute(site);
    setRouteMessage("All science checkpoints cleared.");
  });
  document.getElementById("return-to-habitat").addEventListener("change", (event) => {
    const site = siteData[selectedSite];
    site.returnToHabitat = event.target.checked;
    recalculateSiteRoute(site);
  });
  document.getElementById("safety-margin").addEventListener("change", (event) => {
    const site = siteData[selectedSite];
    const safetyMarginCells = Number(event.target.value);
    if (!Number.isInteger(safetyMarginCells) || safetyMarginCells < 0) {
      throw new RangeError("Safety margin must be a non-negative integer");
    }
    if (!updateSafetyMargin(site, safetyMarginCells)) {
      event.target.value = String(site.safetyMarginCells);
      document.getElementById("safety-margin-value").textContent =
        `${site.safetyMarginCells} cells`;
    }
  });
  document.getElementById("route-algorithm").addEventListener("change", (event) => {
    const site = siteData[selectedSite];
    site.algorithm = event.target.value;
    recalculateSiteRoute(site);
  });
  document.getElementById("weighted-epsilon").addEventListener("input", (event) => {
    document.getElementById("weighted-epsilon-value").textContent =
      Number(event.target.value).toFixed(1);
  });
  document.getElementById("weighted-epsilon").addEventListener("change", (event) => {
    const site = siteData[selectedSite];
    site.epsilon = Number(event.target.value);
    recalculateSiteRoute(site);
  });
  document.getElementById("route-cards").addEventListener("click", (event) => {
    const card = event.target.closest("[data-route-key]");
    if (card && selectedSite) selectRoute(siteData[selectedSite], card.dataset.routeKey);
  });
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
  document.getElementById("checkpoint-leg-list").addEventListener("click", (event) => {
    const checkpoint = event.target.closest("[data-checkpoint]");
    if (checkpoint) jumpToCheckpoint(checkpoint.dataset.checkpoint);
  });
  window.map.on("click", (event) => addCheckpointAt(event.latlng));
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
  document.getElementById("load-status").textContent =
    `Could not load the planner: ${error.message}`;
});
