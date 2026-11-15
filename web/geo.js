let geoReference = null;

function setGeoReference(backdrop, body = "mars", radiusM = null) {
  if (body === "moon") {
    geoReference = {
      body,
      radiusM: Number(radiusM || 1737400),
    };
    return;
  }
  const MARS_RADIUS_M = 3389500;
  geoReference = {
    body,
    radiusM: MARS_RADIUS_M,
    lat0: Number(backdrop.center.lat),
    lon0: Number(backdrop.center.lon),
  };
}

function moonLonLatToXY(lat, lon) {
  if (!geoReference || geoReference.body !== "moon") {
    throw new Error("Moon projection is not initialized");
  }
  const latitudeRadians = lat * Math.PI / 180;
  const longitudeRadians = lon * Math.PI / 180;
  const rho = 2 * geoReference.radiusM * Math.tan(Math.PI / 4 + latitudeRadians / 2);
  return {
    x: rho * Math.sin(longitudeRadians),
    y: rho * Math.cos(longitudeRadians),
  };
}

function moonXYToLonLat(x, y) {
  if (!geoReference || geoReference.body !== "moon") {
    throw new Error("Moon projection is not initialized");
  }
  const rho = Math.hypot(x, y);
  return {
    lat: (2 * Math.atan(rho / (2 * geoReference.radiusM)) - Math.PI / 2) * 180 / Math.PI,
    lon: Math.atan2(x, y) * 180 / Math.PI,
  };
}

function latLonToMap(lat, lon) {
  if (!geoReference) throw new Error("Map projection is not initialized");
  if (geoReference.body === "moon") {
    const point = moonLonLatToXY(lat, lon);
    return [point.y, point.x];
  }
  const lat0Radians = geoReference.lat0 * Math.PI / 180;
  const metersPerDegree = geoReference.radiusM * Math.PI / 180;
  return [
    (lat - geoReference.lat0) * metersPerDegree,
    (lon - geoReference.lon0) * metersPerDegree * Math.cos(lat0Radians),
  ];
}

function mapToLatLon(y, x) {
  if (!geoReference) throw new Error("Map projection is not initialized");
  if (geoReference.body === "moon") return moonXYToLonLat(x, y);
  const lat0Radians = geoReference.lat0 * Math.PI / 180;
  const metersPerDegree = geoReference.radiusM * Math.PI / 180;
  return {
    lat: geoReference.lat0 + y / metersPerDegree,
    lon: geoReference.lon0 + x / (metersPerDegree * Math.cos(lat0Radians)),
  };
}

function boundsToMap(bounds) {
  if ("min_x" in bounds) {
    return [
      [bounds.min_y, bounds.min_x],
      [bounds.max_y, bounds.max_x],
    ];
  }
  const southWest = latLonToMap(bounds.min_lat, bounds.min_lon);
  const northEast = latLonToMap(bounds.max_lat, bounds.max_lon);
  return [southWest, northEast];
}

function gridToMap(site, row, col) {
  const bounds = site.grid.geo_reference.bounds;
  if ("min_x" in bounds) {
    const transform = site.grid.geo_reference.transform;
    const x = transform[0] * (col + 0.5)
      + transform[1] * (row + 0.5) + transform[2];
    const y = transform[3] * (col + 0.5)
      + transform[4] * (row + 0.5) + transform[5];
    return [y, x];
  }
  const lat = bounds.max_lat
    - (row + 0.5) / site.grid.rows * (bounds.max_lat - bounds.min_lat);
  const lon = bounds.min_lon
    + (col + 0.5) / site.grid.cols * (bounds.max_lon - bounds.min_lon);
  return latLonToMap(lat, lon);
}

function mapToGrid(site, y, x) {
  const latLon = mapToLatLon(y, x);
  const bounds = site.grid.geo_reference.bounds;
  if ("min_x" in bounds) {
    const row = Math.floor(
      (bounds.max_y - y) / (bounds.max_y - bounds.min_y) * site.grid.rows,
    );
    const col = Math.floor(
      (x - bounds.min_x) / (bounds.max_x - bounds.min_x) * site.grid.cols,
    );
    return {
      row: Math.max(0, Math.min(site.grid.rows - 1, row)),
      col: Math.max(0, Math.min(site.grid.cols - 1, col)),
      inside: x >= bounds.min_x && x <= bounds.max_x
        && y >= bounds.min_y && y <= bounds.max_y,
      lat: latLon.lat,
      lon: latLon.lon,
    };
  }
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

function distanceToSouthPoleKm(latitude) {
  if (!geoReference || geoReference.body !== "moon") {
    throw new Error("Moon projection is not initialized");
  }
  return (latitude + 90) * Math.PI / 180 * geoReference.radiusM / 1000;
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
