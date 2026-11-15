const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const RoutePlanner = require("../web/route.js");

const root = path.resolve(__dirname, "..");
const margin = 2;

function toArrayBuffer(bytes) {
  return bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
}

function checkProjection() {
  const body = JSON.parse(fs.readFileSync(
    path.join(root, "web", "data", "moon", "body.json"),
    "utf8",
  ));
  assert.equal(body.projection_checks.length, 3);
  const context = { Math };
  context.globalThis = context;
  vm.runInNewContext(
    `${fs.readFileSync(path.join(root, "web", "geo.js"), "utf8")}`
      + "\nglobalThis.moonGeo = { setGeoReference, latLonToMap, mapToLatLon };",
    context,
  );
  context.moonGeo.setGeoReference(null, "moon", body.radius_m);
  for (const point of body.projection_checks) {
    const [y, x] = context.moonGeo.latLonToMap(point.latitude, point.longitude);
    assert.ok(Math.hypot(x - point.x, y - point.y) <= 1,
      `JavaScript forward projection differs for region ${point.region_id}`);
    const inverse = context.moonGeo.mapToLatLon(y, x);
    const errorMeters = Math.hypot(
      (inverse.lat - point.latitude) * Math.PI / 180 * body.radius_m,
      (inverse.lon - point.longitude) * Math.PI / 180 * body.radius_m
        * Math.cos(point.latitude * Math.PI / 180),
    );
    assert.ok(errorMeters <= 1,
      `JavaScript inverse projection differs by ${errorMeters} m`);
  }
  console.log("projection: 3 GeoJSON points round-trip in JavaScript within 1 m");
}

function checkBackdrop() {
  const directory = path.join(root, "web", "data", "moon");
  const metadata = JSON.parse(fs.readFileSync(
    path.join(directory, "backdrop.json"),
    "utf8",
  ));
  const image = fs.readFileSync(path.join(directory, metadata.image));
  assert.deepEqual(metadata.percentile_clip, [2, 98]);
  assert.ok(image.length < 3 * 1024 * 1024);
  assert.equal(image.readUInt32BE(16), metadata.overview_shape[1]);
  assert.equal(image.readUInt32BE(20), metadata.overview_shape[0]);
  console.log(
    `backdrop: ${metadata.overview_shape[1]}x${metadata.overview_shape[0]} PNG, `
    + `${image.length} bytes, 2-98% clip`,
  );
}

function loadSite(site) {
  const processed = path.join(root, "data", "processed", "moon", site);
  const directory = path.join(root, "web", "data", "moon", site);
  const grid = JSON.parse(fs.readFileSync(path.join(processed, "grid.json"), "utf8"));
  const metadata = JSON.parse(fs.readFileSync(path.join(directory, "cost.json"), "utf8"));
  const routeGrid = RoutePlanner.decodeGrid(
    metadata,
    toArrayBuffer(fs.readFileSync(path.join(directory, metadata.cost_file))),
    toArrayBuffer(fs.readFileSync(path.join(directory, metadata.clearance_files.cells))),
    toArrayBuffer(fs.readFileSync(path.join(directory, metadata.clearance_files.meters))),
  );
  assert.equal(routeGrid.site, site);
  assert.deepEqual([routeGrid.rows, routeGrid.cols], [grid.rows, grid.cols]);
  routeGrid.costs.forEach((cost, index) => {
    if (Number.isFinite(cost)) {
      assert.ok(Number.isFinite(routeGrid.clearanceCells[index]));
    } else {
      assert.equal(cost, Infinity);
    }
  });
  return { grid, routeGrid };
}

function* bresenham(start, end) {
  let [row, col] = start;
  const [endRow, endCol] = end;
  const deltaRow = Math.abs(endRow - row);
  const deltaCol = Math.abs(endCol - col);
  const stepRow = row < endRow ? 1 : -1;
  const stepCol = col < endCol ? 1 : -1;
  let error = deltaCol - deltaRow;
  while (true) {
    yield [row, col];
    if (row === endRow && col === endCol) return;
    const doubled = 2 * error;
    if (doubled > -deltaRow) {
      error -= deltaRow;
      col += stepCol;
    }
    if (doubled < deltaCol) {
      error += deltaCol;
      row += stepRow;
    }
  }
}

function cellsOnPath(pathCells) {
  const result = [];
  for (let index = 0; index + 1 < pathCells.length; index += 1) {
    result.push(...[...bresenham(pathCells[index], pathCells[index + 1])].slice(0, -1));
  }
  if (pathCells.length) result.push(pathCells.at(-1));
  return result;
}

function assertSafePath(grid, pathCells, site, label) {
  assert.ok(pathCells.length, `${site} ${label} has no routed cells`);
  for (let index = 0; index + 1 < pathCells.length; index += 1) {
    const [row, col] = pathCells[index];
    const [nextRow, nextCol] = pathCells[index + 1];
    const rowDelta = nextRow - row;
    const colDelta = nextCol - col;
    assert.equal(Math.max(Math.abs(rowDelta), Math.abs(colDelta)), 1);
    if (rowDelta && colDelta) {
      assert.ok(
        RoutePlanner.isWalkable(grid, row + rowDelta, col, margin)
          && RoutePlanner.isWalkable(grid, row, col + colDelta, margin),
        `${site} ${label} cuts a blocked corner`,
      );
    }
  }
  const clearances = cellsOnPath(pathCells).map(([row, col]) => {
    assert.ok(
      RoutePlanner.isWalkable(grid, row, col, margin),
      `${site} ${label} crosses hazard or margin cell ${row},${col}`,
    );
    return grid.clearanceMeters[row * grid.cols + col];
  });
  return Math.min(...clearances);
}

function checkPlaceholderTargetLines(site, grid, routeGrid) {
  const targets = grid.targets.map((point) => [point.row, point.col]);
  const crossing = [];
  for (let left = 0; left < targets.length; left += 1) {
    for (let right = left + 1; right < targets.length; right += 1) {
      const crossesHazard = [...bresenham(targets[left], targets[right])].some(
        ([row, col]) => !Number.isFinite(
          routeGrid.costs[row * routeGrid.cols + col],
        ),
      );
      if (crossesHazard) crossing.push([targets[left], targets[right]]);
    }
  }
  assert.ok(crossing.length, `${site} placeholder target lines avoid all hazards`);
  console.log(
    `${site} placeholder targets: straight line crosses hazard between `
    + `${crossing[0][0]} and ${crossing[0][1]}`,
  );
}

function reachableComponent(grid, start) {
  const seen = new Uint8Array(grid.rows * grid.cols);
  const queue = new Int32Array(grid.rows * grid.cols);
  let head = 0;
  let tail = 1;
  queue[0] = start[0] * grid.cols + start[1];
  seen[queue[0]] = 1;
  while (head < tail) {
    const current = queue[head++];
    const row = Math.floor(current / grid.cols);
    const col = current % grid.cols;
    for (let rowDelta = -1; rowDelta <= 1; rowDelta += 1) {
      for (let colDelta = -1; colDelta <= 1; colDelta += 1) {
        if (!rowDelta && !colDelta) continue;
        const nextRow = row + rowDelta;
        const nextCol = col + colDelta;
        if (!RoutePlanner.isWalkable(grid, nextRow, nextCol, margin)) continue;
        if (rowDelta && colDelta
          && (!RoutePlanner.isWalkable(grid, row + rowDelta, col, margin)
            || !RoutePlanner.isWalkable(grid, row, col + colDelta, margin))) continue;
        const next = nextRow * grid.cols + nextCol;
        if (seen[next]) continue;
        seen[next] = 1;
        queue[tail++] = next;
      }
    }
  }
  return queue.slice(0, tail);
}

function nearestWalkableCell(grid, row, col) {
  let nearest = null;
  for (let index = 0; index < grid.costs.length; index += 1) {
    const nextRow = Math.floor(index / grid.cols);
    const nextCol = index % grid.cols;
    if (!RoutePlanner.isWalkable(grid, nextRow, nextCol, margin)) continue;
    const distance = Math.hypot(
      (nextRow - row) * grid.cellSizeM.y,
      (nextCol - col) * grid.cellSizeM.x,
    );
    if (!nearest || distance < nearest.distance) {
      nearest = { row: nextRow, col: nextCol, distance };
    }
  }
  return nearest;
}

function checkEndpointAndEvaCases(site, grid, routeGrid) {
  const hazardIndex = routeGrid.costs.findIndex((cost) => !Number.isFinite(cost));
  assert.notEqual(hazardIndex, -1, `${site} has no hazard for snapping test`);
  const hazardRow = Math.floor(hazardIndex / routeGrid.cols);
  const hazardCol = hazardIndex % routeGrid.cols;
  const hazardSnap = nearestWalkableCell(routeGrid, hazardRow, hazardCol);
  assert.ok(hazardSnap && hazardSnap.distance > 0);
  assert.ok(RoutePlanner.isWalkable(routeGrid, hazardSnap.row, hazardSnap.col, margin));
  console.log(
    `${site} hazard checkpoint: snapped ${hazardSnap.distance.toFixed(1)} m `
    + `to ${hazardSnap.row},${hazardSnap.col}`,
  );

  const marginIndex = routeGrid.costs.findIndex((cost, index) => (
    Number.isFinite(cost) && routeGrid.clearanceCells[index] <= margin
  ));
  assert.notEqual(marginIndex, -1, `${site} has no safety-margin cell`);
  const marginRow = Math.floor(marginIndex / routeGrid.cols);
  const marginCol = marginIndex % routeGrid.cols;
  const marginSnap = nearestWalkableCell(routeGrid, marginRow, marginCol);
  assert.ok(marginSnap && marginSnap.distance > 0);
  console.log(
    `${site} safety-margin checkpoint: snapped ${marginSnap.distance.toFixed(1)} m `
    + `to ${marginSnap.row},${marginSnap.col}`,
  );

  const habitat = [grid.habitat.row, grid.habitat.col];
  const connectedCells = reachableComponent(routeGrid, habitat);
  const connected = new Set(connectedCells);
  const pocketIndex = routeGrid.costs.findIndex((cost, index) => (
    Number.isFinite(cost)
      && routeGrid.clearanceCells[index] > margin
      && !connected.has(index)
  ));
  assert.notEqual(pocketIndex, -1, `${site} has no disconnected passable pocket`);
  const pocket = [
    Math.floor(pocketIndex / routeGrid.cols),
    pocketIndex % routeGrid.cols,
  ];
  const disconnected = RoutePlanner.planRoute(
    routeGrid,
    grid.habitat,
    [{ row: pocket[0], col: pocket[1] }],
    false,
    null,
    null,
    margin,
  );
  assert.equal(disconnected.unreachable, true);
  assert.equal(disconnected.legs[0].unreachable, true);
  console.log(
    `${site} actual disconnected pocket ${pocket}: NO SAFE PATH; `
    + "leg marked unreachable",
  );

  const checkpoints = [...grid.targets, ...grid.targets];
  const repeatedRoute = RoutePlanner.planRoute(
    routeGrid,
    grid.habitat,
    checkpoints,
    true,
    null,
    null,
    margin,
  );
  assert.equal(repeatedRoute.unreachable, false);
  assert.ok(repeatedRoute.timeH > routeGrid.parameters.eva_hours);
  repeatedRoute.legs.forEach((leg, index) => {
    assertSafePath(routeGrid, leg.path, site, `over-EVA leg ${index + 1}`);
  });
  console.log(
    `${site} repeated-target round trip: ${repeatedRoute.distanceKm.toFixed(3)} km / `
    + `${repeatedRoute.timeH.toFixed(3)} h; OVER EVA LIMIT`,
  );
}

function seededRandom(seed) {
  let state = seed >>> 0;
  return () => {
    state = (state * 1664525 + 1013904223) >>> 0;
    return state / 0x100000000;
  };
}

function checkSite(site, randomPairs, randomSets) {
  const { grid, routeGrid } = loadSite(site);
  checkPlaceholderTargetLines(site, grid, routeGrid);
  const fastest = RoutePlanner.planRoute(
    routeGrid, grid.habitat, grid.targets, true, null, null, margin,
  );
  for (const [index, leg] of fastest.legs.entries()) {
    const minimum = assertSafePath(routeGrid, leg.path, site, `auto leg ${index + 1}`);
    console.log(`${site} auto leg ${index + 1}: zero hazard cells; minimum clearance ${minimum.toFixed(1)} m`);
  }
  const component = reachableComponent(
    routeGrid, [grid.habitat.row, grid.habitat.col],
  );
  const random = seededRandom(20260615);
  const pick = () => {
    const index = component[Math.floor(random() * component.length)];
    return { row: Math.floor(index / grid.cols), col: index % grid.cols };
  };
  for (let iteration = 0; iteration < randomSets; iteration += 1) {
    const checkpoints = Array.from({ length: 3 }, pick);
    const plan = RoutePlanner.planRoute(
      routeGrid, grid.habitat, checkpoints, true, null, null, margin,
    );
    plan.legs.forEach((leg, index) => {
      assertSafePath(routeGrid, leg.path, site, `random set ${iteration + 1}, leg ${index + 1}`);
    });
    console.log(`${site} random checkpoint set ${iteration + 1}: zero hazard cells`);
  }
  checkEndpointAndEvaCases(site, grid, routeGrid);
  console.log(`${site} A* vs Dijkstra cost parity (${randomPairs} pairs):`);
  console.log("pair | A* cost | Dijkstra cost | A* ms | Dijkstra ms | explored A*/Dijkstra");
  for (let index = 0; index < randomPairs; index += 1) {
    const startPoint = pick();
    const endPoint = pick();
    const start = [startPoint.row, startPoint.col];
    const goal = [endPoint.row, endPoint.col];
    const astar = RoutePlanner.searchRoute(routeGrid, start, goal, {
      algorithm: "astar",
      safetyMarginCells: margin,
    });
    const dijkstra = RoutePlanner.searchRoute(routeGrid, start, goal, {
      algorithm: "dijkstra",
      safetyMarginCells: margin,
    });
    assert.ok(
      Math.abs(astar.cost - dijkstra.cost) <= Math.max(astar.cost, dijkstra.cost) * 0.001,
      `${site} A*/Dijkstra cost mismatch`,
    );
    assertSafePath(routeGrid, astar.path, site, `A* parity pair ${index + 1}`);
    assertSafePath(routeGrid, dijkstra.path, site, `Dijkstra parity pair ${index + 1}`);
    console.log(
      `${index + 1} | ${astar.cost.toFixed(1)} | ${dijkstra.cost.toFixed(1)} | `
      + `${astar.computationMs.toFixed(1)} | ${dijkstra.computationMs.toFixed(1)} | `
      + `${astar.exploredCells}/${dijkstra.exploredCells}`,
    );
  }
}

function main() {
  const site = process.argv[2];
  const randomPairs = Number(process.argv[3] || 20);
  const randomSets = Number(process.argv[4] || 20);
  assert.ok(["site_01", "site_04", "site_07", "sl3"].includes(site), "pass a Moon site id");
  checkProjection();
  checkBackdrop();
  checkSite(site, randomPairs, randomSets);
}

main();
