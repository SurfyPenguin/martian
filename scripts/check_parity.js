const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const RoutePlanner = require("../web/route.js");

const root = path.resolve(__dirname, "..");

function readRouteGrid(site) {
  const directory = path.join(root, "web", "data", site);
  const metadata = JSON.parse(fs.readFileSync(path.join(directory, "cost.json"), "utf8"));
  const binary = fs.readFileSync(path.join(directory, "cost.bin"));
  const clearanceCells = fs.readFileSync(
    path.join(directory, metadata.clearance_files.cells),
  );
  const clearanceMeters = fs.readFileSync(
    path.join(directory, metadata.clearance_files.meters),
  );
  const toArrayBuffer = (bytes) => bytes.buffer.slice(
    bytes.byteOffset,
    bytes.byteOffset + bytes.byteLength,
  );
  return RoutePlanner.decodeGrid(
    metadata,
    toArrayBuffer(binary),
    toArrayBuffer(clearanceCells),
    toArrayBuffer(clearanceMeters),
  );
}

function checkSite(siteKey) {
  const grid = JSON.parse(fs.readFileSync(
    path.join(root, "data", "processed", siteKey, "grid.json"),
    "utf8",
  ));
  const costGrid = readRouteGrid(siteKey);
  const expectedLegs = grid.route_segments;
  const targets = grid.targets.map(({ row, col }) => ({ row, col }));
  const points = [
    { row: grid.habitat.row, col: grid.habitat.col },
    ...targets,
    { row: grid.habitat.row, col: grid.habitat.col },
  ];

  expectedLegs.forEach((expectedPath, index) => {
    const pathCells = RoutePlanner.astar(
      costGrid,
      [points[index].row, points[index].col],
      [points[index + 1].row, points[index + 1].col],
    );
    const actualDistance = RoutePlanner.routeDistanceKm(pathCells, costGrid.cellSizeM);
    const expectedDistance = RoutePlanner.routeDistanceKm(
      expectedPath,
      costGrid.cellSizeM,
    );
    const difference = Math.abs(actualDistance - expectedDistance) / expectedDistance;
    assert.ok(
      difference <= 0.01,
      `${siteKey} leg ${index + 1} differs by ${(difference * 100).toFixed(2)}%`,
    );
    assert.ok(
      pathCells.every(([row, col]) => RoutePlanner.isWalkable(
        costGrid,
        row,
        col,
        costGrid.parameters.safety_margin_cells,
      )),
      `${siteKey} leg ${index + 1} crosses an impassable cell`,
    );
    console.log(
      `${siteKey} leg ${index + 1}: Python=${expectedDistance.toFixed(3)} km, `
      + `JavaScript=${actualDistance.toFixed(3)} km, `
      + `difference=${(difference * 100).toFixed(3)}%`,
    );
  });
}

function checkAStarEdges() {
  const makeGrid = () => ({
    rows: 5,
    cols: 5,
    costs: new Float32Array(25).fill(1),
    clearanceCells: new Float32Array(25).fill(10),
    clearanceMeters: new Float32Array(25).fill(10),
    cellSizeM: { x: 1, y: 1 },
    parameters: {
      safety_margin_cells: 2,
      walking_speed_kmh: 1,
      eva_hours: 4,
      dose_rate_msv_per_hour: 0.02,
    },
  });
  const grid = makeGrid();
  for (let row = 0; row < 4; row += 1) {
    grid.costs[row * 5 + 2] = Infinity;
    grid.clearanceCells[row * 5 + 2] = 0;
  }
  const detour = RoutePlanner.astar(grid, [0, 0], [0, 4]);
  assert.ok(detour.some(([row, col]) => row === 4 && col === 2));
  assert.ok(detour.every(([row, col]) => RoutePlanner.isWalkable(grid, row, col)));

  for (let row = 0; row < 5; row += 1) grid.costs[row * 5 + 2] = Infinity;
  assert.throws(
    () => RoutePlanner.astar(grid, [0, 0], [0, 4]),
    RoutePlanner.NoRouteError,
  );
  assert.throws(() => RoutePlanner.astar(grid, [0, 0], [0, 2]), /not walkable/);

  const plan = RoutePlanner.planRoute(
    makeGrid(),
    { row: 0, col: 0 },
    [{ row: 0, col: 2 }],
    true,
  );
  assert.equal(plan.legs.length, 2);
  assert.equal(plan.unreachable, false);
}

checkAStarEdges();
checkSite("site1");
checkSite("site2");
console.log("A* edge cases and Python parity passed.");
