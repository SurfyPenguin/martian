const DATA_ROOT = "/data/processed/";
const layers = {};

function formatNumber(value, unit, digits = 2) {
  return `${Number(value).toFixed(digits)} ${unit}`;
}

function makeRasterOverlay(grid, mode) {
  const canvas = document.createElement("canvas");
  canvas.width = grid.cols;
  canvas.height = grid.rows;
  const context = canvas.getContext("2d");
  const pixels = context.createImageData(grid.cols, grid.rows);
  const maxSlope = 15;
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
        pixels.data[index] = Math.round(40 + ratio * 210);
        pixels.data[index + 1] = Math.round(190 - ratio * 140);
        pixels.data[index + 2] = 255;
        pixels.data[index + 3] = 170;
      }
    }
  }
  context.putImageData(pixels, 0, 0);
  const [west, south, east, north] = grid.bounds;
  return L.imageOverlay(canvas.toDataURL(), [[south, west], [north, east]]);
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

async function loadPlanner() {
  const [stats, grid, route] = await Promise.all([
    fetch(`${DATA_ROOT}stats.json`).then((response) => response.json()),
    fetch(`${DATA_ROOT}grid.json`).then((response) => response.json()),
    fetch(`${DATA_ROOT}route.geojson`).then((response) => response.json()),
  ]);
  const [west, south, east, north] = grid.bounds;
  window.map = L.map("map", { zoomControl: false, attributionControl: false });
  L.control.zoom({ position: "bottomright" }).addTo(window.map);
  window.map.fitBounds([[south, west], [north, east]]);

  layers.slope = makeRasterOverlay(grid, "slope").addTo(window.map);
  layers.hazard = makeRasterOverlay(grid, "hazard").addTo(window.map);
  layers.route = L.geoJSON(route, {
    style: { color: "#68e1fd", weight: 5, opacity: 1 },
  }).addTo(window.map);
  layers.targets = L.layerGroup();
  grid.targets.forEach((target) => {
    const marker = L.circleMarker([target.lat, target.lon], {
      radius: 8, color: "#fbbf24", fillColor: "#fbbf24", fillOpacity: 1,
    });
    marker.bindPopup(`<strong>${target.id}</strong><div class="photo-slot">PLACEHOLDER PHOTO<br>surface preview</div>`);
    marker.addTo(layers.targets);
  });
  L.circleMarker([grid.habitat.lat, grid.habitat.lon], {
    radius: 7, color: "#fff", fillColor: "#68e1fd", fillOpacity: 1,
  }).bindPopup("<strong>Habitat / rover</strong><br>Placeholder departure point.").addTo(layers.targets);
  layers.targets.addTo(window.map);

  document.getElementById("distance").textContent = formatNumber(stats.distance_km, "km", 3);
  document.getElementById("time").textContent = formatNumber(stats.time_h, "h", 3);
  document.getElementById("margin").textContent = formatNumber(stats.return_margin_h, "h", 3);
  document.getElementById("dose").textContent = formatNumber(stats.est_dose_msv, "mSv", 4);
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
