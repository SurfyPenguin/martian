const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const RoutePlanner = require("../web/route.js");

const root = path.resolve(__dirname, "..");
const margin = 2;

function toArrayBuffer(bytes) {
  return bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
}

function loadSite(site) {
  const processed = path.join(root, "data", "processed", site);
  const directory = path.join(root, "web", "data", site);
  const grid = JSON.parse(fs.readFileSync(path.join(processed, "grid.json"), "utf8"));
  const metadata = JSON.parse(fs.readFileSync(path.join(directory, "cost.json"), "utf8"));
  const routeGrid = RoutePlanner.decodeGrid(
    metadata,
    toArrayBuffer(fs.readFileSync(path.join(directory, "cost.bin"))),
    toArrayBuffer(fs.readFileSync(path.join(directory, metadata.clearance_files.cells))),
    toArrayBuffer(fs.readFileSync(path.join(directory, metadata.clearance_files.meters))),
  );
  assert.equal(routeGrid.site, site);
  assert.deepEqual(
    [routeGrid.rows, routeGrid.cols],
    [grid.rows, grid.cols],
    `${site} route grid dimensions differ from the exported site grid`,
  );
  routeGrid.costs.forEach((cost, index) => {
    assert.equal(
      Number.isFinite(cost),
      Number.isFinite(routeGrid.clearanceCells[index]) && cost !== Infinity,
      `${site} cost and clearance grids disagree at cell ${index}`,
    );
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
    if (row === endRow && col === endCol) break;
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
    const segment = [...bresenham(pathCells[index], pathCells[index + 1])];
    result.push(...segment.slice(0, -1));
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
    assert.equal(
      Math.max(Math.abs(rowDelta), Math.abs(colDelta)),
      1,
      `${site} ${label} has non-adjacent path vertices`,
    );
    if (rowDelta && colDelta) {
      assert.ok(
        RoutePlanner.isWalkable(grid, row + rowDelta, col, margin)
          && RoutePlanner.isWalkable(grid, row, col + colDelta, margin),
        `${site} ${label} cuts a blocked corner`,
      );
    }
  }

  const clearances = cellsOnPath(pathCells).map(([row, col]) => {
    const index = row * grid.cols + col;
    assert.ok(
      RoutePlanner.isWalkable(grid, row, col, margin),
      `${site} ${label} crosses a hazard or safety-margin cell at ${row},${col}`,
    );
    return grid.clearanceMeters[index];
  });
  return Math.min(...clearances);
}

function reachableComponent(grid, start) {
  const count = grid.rows * grid.cols;
  const seen = new Uint8Array(count);
  const queue = new Int32Array(count);
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

function seededRandom(seed) {
  let state = seed >>> 0;
  return () => {
    state = (state * 1664525 + 1013904223) >>> 0;
    return state / 0x100000000;
  };
}

function shuffle(items, random) {
  for (let index = items.length - 1; index > 0; index -= 1) {
    const other = Math.floor(random() * (index + 1));
    [items[index], items[other]] = [items[other], items[index]];
  }
}

function checkSyntheticWall() {
  const costs = new Float32Array(4).fill(Infinity);
  const clearanceCells = new Float32Array(4);
  costs[0] = 1;
  costs[3] = 1;
  clearanceCells[0] = 1;
  clearanceCells[3] = 1;
  const grid = {
    rows: 2,
    cols: 2,
    costs,
    clearanceCells,
    cellSizeM: { x: 1, y: 1 },
    parameters: { safety_margin_cells: 0 },
  };
  assert.throws(() => RoutePlanner.astar(grid, [0, 0], [1, 1], 0), RoutePlanner.NoRouteError);
  console.log("synthetic wall/diagonal gap: corner cutting blocked");
}

function checkSite(site, random) {
  const { grid, routeGrid } = loadSite(site);
  const fastest = RoutePlanner.planRoute(
    routeGrid,
    grid.habitat,
    grid.targets,
    true,
    null,
    null,
    margin,
  );
  const alternatives = RoutePlanner.computeAlternatives(
    routeGrid,
    grid.habitat,
    grid.targets,
    true,
    fastest,
    { safetyMarginCells: margin },
  );
  for (const alternative of alternatives) {
    const clearances = alternative.plan.legs.map((leg, index) => (
      assertSafePath(routeGrid, leg.path, site, `${alternative.name} leg ${index + 1}`)
    ));
    console.log(
      `${site} ${alternative.name} alternative: ${alternative.plan.legs.length} legs, `
      + `minimum clearance ${Math.min(...clearances).toFixed(1)} m`,
    );
  }
  for (const algorithm of ["dijkstra", "weighted"]) {
    const plan = RoutePlanner.planRoute(
      routeGrid,
      grid.habitat,
      grid.targets,
      true,
      null,
      null,
      margin,
      { algorithm, epsilon: 1.5 },
    );
    plan.legs.forEach((leg, index) => {
      assertSafePath(routeGrid, leg.path, site, `${algorithm} leg ${index + 1}`);
    });
    console.log(`${site} ${algorithm} auto plan: all ${plan.legs.length} legs safe`);
  }
  const minimumAutoClearance = Math.min(...grid.route_segments.map((path, index) => (
    assertSafePath(routeGrid, path, site, `auto leg ${index + 1}`)
  )));
  console.log(
    `${site} auto plan: ${grid.route_segments.length} legs, `
    + `minimum clearance ${minimumAutoClearance.toFixed(1)} m`,
  );

  const habitat = [grid.habitat.row, grid.habitat.col];
  const component = reachableComponent(routeGrid, habitat);
  assert.ok(component.length >= 4, `${site} habitat component is too small`);
  for (let setIndex = 0; setIndex < 20; setIndex += 1) {
    shuffle(component, random);
    const stops = [];
    for (let index = 0; index < 3; index += 1) {
      const flat = component[index];
      stops.push([Math.floor(flat / routeGrid.cols), flat % routeGrid.cols]);
    }
    const points = [habitat, ...stops, habitat];
    const clearances = [];
    for (let legIndex = 0; legIndex + 1 < points.length; legIndex += 1) {
      const pathCells = RoutePlanner.astar(
        routeGrid,
        points[legIndex],
        points[legIndex + 1],
        margin,
      );
      clearances.push(
        assertSafePath(routeGrid, pathCells, site, `random ${setIndex + 1} leg ${legIndex + 1}`),
      );
    }
    console.log(
      `${site} random set ${String(setIndex + 1).padStart(2, "0")}: `
      + `4 legs, minimum clearance ${Math.min(...clearances).toFixed(1)} m`,
    );
  }
}

checkSyntheticWall();
const random = seededRandom(20261115);
checkSite("site1", random);
checkSite("site2", random);
console.log("All exported auto and random routes are hazard- and margin-free.");
