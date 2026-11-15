const MARS_RADIUS_M = 3389500;
let geoReference = null;

function setGeoReference(backdrop) {
  geoReference = {
    lat0: Number(backdrop.center.lat),
    lon0: Number(backdrop.center.lon),
  };
}

function latLonToMap(lat, lon) {
  if (!geoReference) throw new Error("Map projection is not initialized");
  const lat0Radians = geoReference.lat0 * Math.PI / 180;
  const metersPerDegree = MARS_RADIUS_M * Math.PI / 180;
  return [
    (lat - geoReference.lat0) * metersPerDegree,
    (lon - geoReference.lon0) * metersPerDegree * Math.cos(lat0Radians),
  ];
}

function mapToLatLon(y, x) {
  if (!geoReference) throw new Error("Map projection is not initialized");
  const lat0Radians = geoReference.lat0 * Math.PI / 180;
  const metersPerDegree = MARS_RADIUS_M * Math.PI / 180;
  return {
    lat: geoReference.lat0 + y / metersPerDegree,
    lon: geoReference.lon0 + x / (metersPerDegree * Math.cos(lat0Radians)),
  };
}

function boundsToMap(bounds) {
  const southWest = latLonToMap(bounds.min_lat, bounds.min_lon);
  const northEast = latLonToMap(bounds.max_lat, bounds.max_lon);
  return [southWest, northEast];
}

function gridToMap(site, row, col) {
  const bounds = site.grid.geo_reference.bounds;
  const lat = bounds.max_lat
    - (row + 0.5) / site.grid.rows * (bounds.max_lat - bounds.min_lat);
  const lon = bounds.min_lon
    + (col + 0.5) / site.grid.cols * (bounds.max_lon - bounds.min_lon);
  return latLonToMap(lat, lon);
}

function mapToGrid(site, y, x) {
  const latLon = mapToLatLon(y, x);
  const bounds = site.grid.geo_reference.bounds;
  const row = Math.floor(
    (bounds.max_lat - latLon.lat) / (bounds.max_lat - bounds.min_lat)
      * site.grid.rows,
  );
  const col = Math.floor(
    (latLon.lon - bounds.min_lon) / (bounds.max_lon - bounds.min_lon)
      * site.grid.cols,
  );
  return {
    row: Math.max(0, Math.min(site.grid.rows - 1, row)),
    col: Math.max(0, Math.min(site.grid.cols - 1, col)),
    inside: latLon.lat >= bounds.min_lat && latLon.lat <= bounds.max_lat
      && latLon.lon >= bounds.min_lon && latLon.lon <= bounds.max_lon,
    lat: latLon.lat,
    lon: latLon.lon,
  };
}

function mapBoundsUnion(boundsList) {
  return [
    [
      Math.min(...boundsList.map((bounds) => bounds[0][0])),
      Math.min(...boundsList.map((bounds) => bounds[0][1])),
    ],
    [
      Math.max(...boundsList.map((bounds) => bounds[1][0])),
      Math.max(...boundsList.map((bounds) => bounds[1][1])),
    ],
  ];
}

function padMapBounds(bounds, fraction = 0.03) {
  const yPadding = (bounds[1][0] - bounds[0][0]) * fraction;
  const xPadding = (bounds[1][1] - bounds[0][1]) * fraction;
  return [
    [bounds[0][0] - yPadding, bounds[0][1] - xPadding],
    [bounds[1][0] + yPadding, bounds[1][1] + xPadding],
  ];
}
