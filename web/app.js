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
  const hue = 215 - clamped * 185;
  const lightness = 42 + (1 - clamped) * 8;
  return `hsl(${hue} 84% ${lightness}%)`;
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
        const color = slopeColor(ratio);
        const match = color.match(/\d+/g).map(Number);
        const hue = match[0] / 360;
        const saturation = match[1] / 100;
        const lightness = match[2] / 100;
        const chroma = (1 - Math.abs(2 * lightness - 1)) * saturation;
        const x = chroma * (1 - Math.abs((hue * 6) % 2 - 1));
        const m = lightness - chroma / 2;
        const rgb = hue * 6 < 1 ? [chroma, x, 0]
          : hue * 6 < 2 ? [x, chroma, 0]
            : hue * 6 < 3 ? [0, chroma, x]
              : hue * 6 < 4 ? [0, x, chroma]
                : hue * 6 < 5 ? [x, 0, chroma] : [chroma, 0, x];
        pixels.data[index] = Math.round((rgb[0] + m) * 255);
        pixels.data[index + 1] = Math.round((rgb[1] + m) * 255);
        pixels.data[index + 2] = Math.round((rgb[2] + m) * 255);
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

  layers.slope = makeRasterOverlay(grid, "slope", bounds).addTo(window.map);
  layers.hazard = makeRasterOverlay(grid, "hazard", bounds).addTo(window.map);
  const outboundPixels = grid.route_segments.slice(0, -1).flatMap((segment, index) =>
    index === 0 ? segment : segment.slice(1));
  const returnPixels = grid.route_segments.at(-1);
  layers.route = L.layerGroup([
    L.polyline(outboundPixels.map(gridToLeaflet), {
      color: "#fbbf24", weight: 4, opacity: 1, dashArray: "8 8",
    }),
    L.polyline(returnPixels.map(gridToLeaflet), {
      color: "#68e1fd", weight: 5, opacity: 1,
    }),
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
    const eastKm = (event.latlng.lng - grid.habitat.col) * grid.cell_size_m.x / 1000;
    const northKm = (event.latlng.lat - gridToLeaflet([grid.habitat.row, 0])[0])
      * grid.cell_size_m.y / 1000;
    const rangeKm = Math.hypot(eastKm, northKm);
    document.getElementById("coordinate-readout").textContent =
      `From Habitat: E ${eastKm >= 0 ? "+" : ""}${eastKm.toFixed(2)} km · `
      + `N ${northKm >= 0 ? "+" : ""}${northKm.toFixed(2)} km · `
      + `${rangeKm.toFixed(2)} km`;
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

  setLayerControl("slope", "slope-toggle", "slope-opacity");
  setLayerControl("hazard", "hazard-toggle", "hazard-opacity");
  setLayerControl("route", "route-toggle", "route-opacity");
  setLayerControl("targets", "targets-toggle", "targets-opacity");
}

loadPlanner().catch((error) => {
  console.error(error);
  document.getElementById("load-status").textContent = "Could not load processed layers.";
});
