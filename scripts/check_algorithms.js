const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { performance } = require("node:perf_hooks");
const RoutePlanner = require("../web/route.js");

const root = path.resolve(__dirname, "..");
const safetyMarginCells = 2;
const manifest = JSON.parse(
  fs.readFileSync(path.join(root, "web", "data", "sites.json"), "utf8"),
);

function toArrayBuffer(bytes) {
  return bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
}

function loadGrid(site) {
  const processed = path.join(root, "data", "processed", site);
  const directory = path.join(root, "web", "data", site);
  const metadata = JSON.parse(fs.readFileSync(path.join(directory, "cost.json"), "utf8"));
  const grid = JSON.parse(fs.readFileSync(path.join(processed, "grid.json"), "utf8"));
  return {
    metadata,
    habitat: grid.habitat,
    routeGrid: RoutePlanner.decodeGrid(
      metadata,
      toArrayBuffer(fs.readFileSync(path.join(directory, "cost.bin"))),
      toArrayBuffer(fs.readFileSync(path.join(directory, metadata.clearance_files.cells))),
      toArrayBuffer(fs.readFileSync(path.join(directory, metadata.clearance_files.meters))),
    ),
  };
}

function reachableCells(grid, start) {
  const queue = [start[0] * grid.cols + start[1]];
  const seen = new Uint8Array(grid.costs.length);
  seen[queue[0]] = 1;
  for (let head = 0; head < queue.length; head += 1) {
    const index = queue[head];
    const row = Math.floor(index / grid.cols);
    const col = index % grid.cols;
    for (let rowDelta = -1; rowDelta <= 1; rowDelta += 1) {
      for (let colDelta = -1; colDelta <= 1; colDelta += 1) {
        if (!rowDelta && !colDelta) continue;
        const nextRow = row + rowDelta;
        const nextCol = col + colDelta;
        if (!RoutePlanner.isWalkable(grid, nextRow, nextCol, safetyMarginCells)) continue;
        if (rowDelta && colDelta
          && (!RoutePlanner.isWalkable(grid, row + rowDelta, col, safetyMarginCells)
            || !RoutePlanner.isWalkable(grid, row, col + colDelta, safetyMarginCells))) continue;
        const next = nextRow * grid.cols + nextCol;
        if (seen[next]) continue;
        seen[next] = 1;
        queue.push(next);
      }
    }
  }
  return queue;
}

function seededRandom(seed) {
  let state = seed >>> 0;
  return () => {
    state = (state * 1664525 + 1013904223) >>> 0;
    return state / 0x100000000;
  };
}

function verifySite(site, random) {
  const { metadata, habitat, routeGrid } = loadGrid(site);
  const reachable = reachableCells(routeGrid, [habitat.row, habitat.col]);
  assert.ok(reachable.length >= 2, `${site} has too few reachable cells`);
  let astarMs = 0;
  let dijkstraMs = 0;
  let astarExplored = 0;
  let dijkstraExplored = 0;
  let maximumCostDifference = 0;
  for (let pair = 0; pair < 20; pair += 1) {
    let startIndex = Math.floor(random() * reachable.length);
    let goalIndex = Math.floor(random() * reachable.length);
    while (goalIndex === startIndex) {
      goalIndex = Math.floor(random() * reachable.length);
    }
    const start = [Math.floor(reachable[startIndex] / routeGrid.cols), reachable[startIndex] % routeGrid.cols];
    const goal = [Math.floor(reachable[goalIndex] / routeGrid.cols), reachable[goalIndex] % routeGrid.cols];
    const aStarStart = performance.now();
    const aStar = RoutePlanner.searchRoute(routeGrid, start, goal, {
      algorithm: "astar",
      safetyMarginCells,
    });
    astarMs += performance.now() - aStarStart;
    const dijkstraStart = performance.now();
    const dijkstra = RoutePlanner.searchRoute(routeGrid, start, goal, {
      algorithm: "dijkstra",
      safetyMarginCells,
    });
    dijkstraMs += performance.now() - dijkstraStart;
    const difference = Math.abs(aStar.cost - dijkstra.cost) / dijkstra.cost;
    maximumCostDifference = Math.max(maximumCostDifference, difference);
    assert.ok(
      difference <= 0.001,
      `${site} pair ${pair + 1} cost difference ${(difference * 100).toFixed(4)}%`,
    );
    astarExplored += aStar.exploredCells;
    dijkstraExplored += dijkstra.exploredCells;
  }
  console.log(
    `${site.padEnd(7)} ${String(20).padStart(5)} `
      + `${(astarMs / 20).toFixed(2).padStart(10)} `
      + `${(dijkstraMs / 20).toFixed(2).padStart(13)} `
      + `${(astarExplored / 20).toFixed(0).padStart(12)} `
      + `${(dijkstraExplored / 20).toFixed(0).padStart(16)} `
      + `${(maximumCostDifference * 100).toFixed(4).padStart(12)}%`,
  );
  assert.equal(metadata.site, site);
}

console.log("Site   Pairs   A* avg ms   Dijkstra avg ms   A* explored   Dijkstra explored   Max cost delta");
const random = seededRandom(20261116);
for (const { key } of manifest.sites) verifySite(key, random);
console.log(`A* and Dijkstra costs agree within 0.1% on all ${20 * manifest.sites.length} pairs.`);
