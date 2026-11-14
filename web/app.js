const DATA_ROOT = "/data/processed/";
const layers = {};

function formatNumber(value, unit, digits = 2) {
  return `${Number(value).toFixed(digits)} ${unit}`;
}

function gridToLeaflet([row, col]) {
  return [window.grid.rows - row, col];
}

function slopeColor(ratio) {
  const clamped = Math.min(1, Math.max(0, ratio));
  const hue = 210 - clamped * 172;
  const lightness = 22 + clamped * 30;
  const saturation = 0.45;
  const normalizedHue = hue / 360;
  const normalizedLightness = lightness / 100;
  const chroma = (1 - Math.abs(2 * normalizedLightness - 1)) * saturation;
  const x = chroma * (1 - Math.abs((normalizedHue * 6) % 2 - 1));
  const match = normalizedHue * 6;
  const rgb = match < 1 ? [chroma, x, 0]
    : match < 2 ? [x, chroma, 0]
      : match < 3 ? [0, chroma, x]
        : match < 4 ? [0, x, chroma]
          : match < 5 ? [x, 0, chroma] : [chroma, 0, x];
  const offset = normalizedLightness - chroma / 2;
  return rgb.map((channel) => Math.round((channel + offset) * 255));
}

function makeTerrainOverlay(grid, bounds) {
  const canvas = document.createElement("canvas");
  canvas.width = grid.cols;
  canvas.height = grid.rows;
  const context = canvas.getContext("2d");
  const pixels = context.createImageData(grid.cols, grid.rows);
  const elevations = grid.elevation_m;
  const values = elevations.flat();
  const minimum = Math.min(...values);
  const maximum = Math.max(...values);
  for (let row = 0; row < grid.rows; row += 1) {
    for (let col = 0; col < grid.cols; col += 1) {
      const elevation = elevations[row][col];
      const left = elevations[row][Math.max(0, col - 1)];
      const right = elevations[row][Math.min(grid.cols - 1, col + 1)];
      const north = elevations[Math.max(0, row - 1)][col];
      const south = elevations[Math.min(grid.rows - 1, row + 1)][col];
      const shade = Math.max(-1, Math.min(1, (left - right + north - south) / 100));
      const heightRatio = (elevation - minimum) / (maximum - minimum);
      const index = (row * grid.cols + col) * 4;
      pixels.data[index] = Math.round(34 + heightRatio * 58 + shade * 22);
      pixels.data[index + 1] = Math.round(42 + heightRatio * 42 + shade * 18);
      pixels.data[index + 2] = Math.round(48 + heightRatio * 26 + shade * 14);
      pixels.data[index + 3] = 235;
      const contour = elevation % 80;
      if (contour < 3 || contour > 77) {
        pixels.data[index] = Math.min(150, pixels.data[index] + 35);
        pixels.data[index + 1] = Math.min(135, pixels.data[index + 1] + 28);
        pixels.data[index + 2] = Math.min(105, pixels.data[index + 2] + 18);
      }
    }
  }
  context.putImageData(pixels, 0, 0);
  return L.imageOverlay(canvas.toDataURL(), bounds);
}

function makeRasterOverlay(grid, mode, bounds) {
  const canvas = document.createElement("canvas");
  canvas.width = grid.cols;
  canvas.height = grid.rows;
  const context = canvas.getContext("2d");
  const pixels = context.createImageData(grid.cols, grid.rows);
  const maxSlope = grid.max_walkable_slope_deg;
  for (let row = 0; row < grid.rows; row += 1) {
    for (let col = 0; col < grid.cols; col += 1) {
      const index = (row * grid.cols + col) * 4;
      const slope = grid.slope_deg[row][col];
      const walkable = grid.walkable[row][col];
      if (mode === "hazard" && walkable) {
        pixels.data[index + 3] = 0;
        continue;
      }
      if (mode === "hazard") {
        pixels.data[index] = 239;
        pixels.data[index + 1] = 68;
        pixels.data[index + 2] = 68;
        pixels.data[index + 3] = 220;
      } else {
        const ratio = Math.min(1, Math.max(0, slope / maxSlope));
        const [red, green, blue] = slopeColor(ratio);
        pixels.data[index] = red;
        pixels.data[index + 1] = green;
        pixels.data[index + 2] = blue;
        pixels.data[index + 3] = Math.round(105 + ratio * 100);
      }
    }
  }
  context.putImageData(pixels, 0, 0);
  return L.imageOverlay(canvas.toDataURL(), bounds);
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
      const gridWidth = desiredKm * 1000 / grid.cell_size_m.x;
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
    element.innerHTML = "<span class=\"north-arrow-mark\"></span><small>N</small>";
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
    L.DomEvent.on(button, "click", () => map.fitBounds(bounds, { padding: [24, 24] }));
    return button;
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
    elevation: grid.elevation_m[row][col],
    slope: grid.slope_deg[row][col],
  };
}

async function loadPlanner() {
  const [stats, grid] = await Promise.all([
    fetch(`${DATA_ROOT}stats.json`).then((response) => response.json()),
    fetch(`${DATA_ROOT}grid.json`).then((response) => response.json()),
  ]);
  window.grid = grid;
  const bounds = [[0, 0], [grid.rows, grid.cols]];
  window.map = L.map("map", {
    crs: L.CRS.Simple,
    zoomControl: false,
    attributionControl: false,
  });
  L.control.zoom({ position: "bottomright" }).addTo(window.map);
  const minZoom = window.map.getBoundsZoom(bounds);
  window.map.setMinZoom(minZoom);
  console.info("Grid bounds:", bounds);
  console.info("Route endpoints (row, col):", grid.route_pixels[0],
    grid.route_pixels.at(-1));
  window.map.fitBounds(bounds, { padding: [24, 24] });
  addScaleBar(window.map, grid);
  addNorthArrow(window.map);
  addResetControl(window.map, bounds);
  const center = gridToLatLon(grid, [grid.rows / 2, grid.cols / 2]);
  document.getElementById("map-inspector").innerHTML =
    `<strong>${center.lat.toFixed(5)}°, ${center.lon.toFixed(5)}°</strong>`
    + "<span>Move over terrain to inspect elevation and slope</span>";

  layers.terrain = makeTerrainOverlay(grid, bounds).addTo(window.map);
  layers.slope = makeRasterOverlay(grid, "slope", bounds).addTo(window.map);
  layers.hazard = makeRasterOverlay(grid, "hazard", bounds).addTo(window.map);
  const outboundPixels = grid.route_segments.slice(0, -1).flatMap((segment, index) =>
    index === 0 ? segment : segment.slice(1));
  const returnPixels = grid.route_segments.at(-1);
  layers.route = L.layerGroup([
    L.polyline(outboundPixels.map(gridToLeaflet), {
      color: "#fbbf24", weight: 4, opacity: 1, dashArray: "8 8",
    }).bindTooltip("Outbound leg · Habitat → science targets"),
    L.polyline(returnPixels.map(gridToLeaflet), {
      color: "#68e1fd", weight: 5, opacity: 1,
    }).bindTooltip("Return leg · Target 3 → Habitat"),
  ]).addTo(window.map);
  layers.targets = L.layerGroup();
  grid.targets.forEach((target) => {
    const marker = L.circleMarker(gridToLeaflet([target.row, target.col]), {
      radius: 8, color: "#fbbf24", fillColor: "#fbbf24", fillOpacity: 1,
    });
    const label = `Target ${target.id.split("-")[1]}`;
    const leg = grid.legs.find((item) => item.name === target.id);
    marker.bindTooltip(
      `${label} · ${leg.distance_km.toFixed(3)} km · ${leg.time_h.toFixed(3)} h`,
    );
    marker.bindPopup(`<strong>${label}</strong><div class="photo-slot">PLACEHOLDER PHOTO<br>surface preview</div>`);
    marker.addTo(layers.targets);
  });
  L.circleMarker(gridToLeaflet([grid.habitat.row, grid.habitat.col]), {
    radius: 7, color: "#fff", fillColor: "#68e1fd", fillOpacity: 1,
  }).bindTooltip(`Habitat · return ${grid.legs.at(-1).distance_km.toFixed(3)} km · ${grid.legs.at(-1).time_h.toFixed(3)} h`)
    .bindPopup("<strong>Habitat</strong><br>Placeholder departure point.").addTo(layers.targets);
  layers.targets.addTo(window.map);

  window.map.on("mousemove", (event) => {
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
      `<strong>${latitude}°, ${longitude}°</strong>`
      + `<span>${cell.elevation.toFixed(1)} m elevation · ${cell.slope.toFixed(1)}° slope</span>`
      + `<span>From Habitat: ${rangeKm.toFixed(2)} km</span>`;
  });

  document.getElementById("distance").textContent = formatNumber(stats.distance_km, "km", 3);
  document.getElementById("time").textContent = formatNumber(stats.time_h, "h", 3);
  document.getElementById("margin").textContent = formatNumber(stats.return_margin_h, "h", 3);
  document.getElementById("dose").textContent = formatNumber(stats.est_dose_msv, "mSv", 4);
  document.getElementById("slope-limit").textContent = `${grid.max_walkable_slope_deg}°+`;
  const safetyStatus = document.getElementById("safety-status");
  const withinLimit = stats.return_margin_h >= 0;
  const tightMargin = withinLimit && stats.return_margin_h < 0.25;
  safetyStatus.textContent = !withinLimit
    ? "OVER EVA LIMIT"
    : tightMargin ? "LOW RETURN MARGIN" : "WITHIN EVA LIMIT";
  safetyStatus.classList.toggle("warning", !withinLimit);
  safetyStatus.classList.toggle("caution", tightMargin);
  document.getElementById("load-status").textContent = "Layers loaded. All mission points are placeholders.";

  setLayerControl("terrain", "terrain-toggle", "terrain-opacity");
  setLayerControl("slope", "slope-toggle", "slope-opacity");
  setLayerControl("hazard", "hazard-toggle", "hazard-opacity");
  setLayerControl("route", "route-toggle", "route-opacity");
  setLayerControl("targets", "targets-toggle", "targets-opacity");
}

loadPlanner().catch((error) => {
  console.error(error);
  document.getElementById("load-status").textContent = "Could not load processed layers.";
});
