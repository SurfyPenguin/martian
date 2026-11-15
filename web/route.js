(function attachRoutePlanner(globalScope) {
  class BinaryHeap {
    constructor() {
      this.items = [];
    }

    push(item) {
      this.items.push(item);
      let index = this.items.length - 1;
      while (index > 0) {
        const parent = Math.floor((index - 1) / 2);
        if (compareNodes(this.items[parent], item) <= 0) break;
        this.items[index] = this.items[parent];
        index = parent;
      }
      this.items[index] = item;
    }

    pop() {
      const first = this.items[0];
      const last = this.items.pop();
      if (this.items.length && last) {
        let index = 0;
        while (true) {
          const left = index * 2 + 1;
          const right = left + 1;
          if (left >= this.items.length) break;
          const child = right < this.items.length
            && compareNodes(this.items[right], this.items[left]) < 0
            ? right
            : left;
          if (compareNodes(this.items[child], last) >= 0) break;
          this.items[index] = this.items[child];
          index = child;
        }
        this.items[index] = last;
      }
      return first;
    }

    get length() {
      return this.items.length;
    }
  }

  function compareNodes(left, right) {
    return left.priority - right.priority
      || left.cost - right.cost
      || left.index - right.index;
  }

  class NoRouteError extends Error {
    constructor(start, goal) {
      super(`No walkable route exists: ${start} -> ${goal}`);
      this.name = "NoRouteError";
    }
  }

  function decodeFloatGrid(buffer, rows, cols, name) {
    const count = rows * cols;
    if (!buffer || buffer.byteLength !== count * Float32Array.BYTES_PER_ELEMENT) {
      throw new Error(`${name} has ${buffer?.byteLength ?? 0} bytes; expected ${count * 4}`);
    }
    const view = new DataView(buffer);
    const values = new Float32Array(count);
    for (let index = 0; index < count; index += 1) {
      values[index] = view.getFloat32(index * 4, true);
    }
    return values;
  }

  function decodeGrid(
    metadata,
    costBuffer,
    clearanceCellsBuffer,
    clearanceMetersBuffer,
  ) {
    const { rows, cols } = metadata;
    const count = rows * cols;
    if (!Number.isInteger(rows) || !Number.isInteger(cols) || rows < 1 || cols < 1) {
      throw new Error("Route grid dimensions are invalid");
    }
    if (metadata.dtype !== "float32" || metadata.byte_order !== "little-endian") {
      throw new Error("Unsupported route grid encoding");
    }
    if (metadata.format_version !== 2 || metadata.hazard_cost !== "positive-infinity") {
      throw new Error("Route grid does not use the single-source hazard format");
    }
    const clearanceFiles = metadata.clearance_files;
    if (!clearanceFiles?.cells || !clearanceFiles?.meters) {
      throw new Error("Route grid is missing its clearance arrays");
    }
    return {
      ...metadata,
      costs: decodeFloatGrid(costBuffer, rows, cols, "Route costs"),
      clearanceCells: decodeFloatGrid(
        clearanceCellsBuffer,
        rows,
        cols,
        "Cell clearances",
      ),
      clearanceMeters: decodeFloatGrid(
        clearanceMetersBuffer,
        rows,
        cols,
        "Metric clearances",
      ),
      cellSizeM: metadata.cell_size_m,
    };
  }

  function indexOf(grid, point) {
    const [row, col] = point;
    if (!Number.isInteger(row) || !Number.isInteger(col)
      || row < 0 || row >= grid.rows || col < 0 || col >= grid.cols) {
      throw new RangeError(`Route endpoint is outside the grid: ${point}`);
    }
    return row * grid.cols + col;
  }

  function heuristic(grid, index, goalRow, goalCol) {
    const row = Math.floor(index / grid.cols);
    const col = index % grid.cols;
    const rowDistance = Math.abs(row - goalRow);
    const colDistance = Math.abs(col - goalCol);
    const diagonalSteps = Math.min(rowDistance, colDistance);
    return diagonalSteps * Math.hypot(grid.cellSizeM.y, grid.cellSizeM.x)
      + (rowDistance - diagonalSteps) * grid.cellSizeM.y
      + (colDistance - diagonalSteps) * grid.cellSizeM.x;
  }

  function isWalkable(grid, row, col, safetyMarginCells = grid.parameters.safety_margin_cells) {
    if (row < 0 || row >= grid.rows || col < 0 || col >= grid.cols) return false;
    const index = row * grid.cols + col;
    return Number.isFinite(grid.costs[index])
      && grid.clearanceCells[index] > safetyMarginCells;
  }

  function searchRoute(
    grid,
    start,
    goal,
    {
      algorithm = "astar",
      epsilon = 1.5,
      safetyMarginCells = grid.parameters.safety_margin_cells,
      costs = grid.costs,
    } = {},
  ) {
    if (!["astar", "dijkstra", "weighted"].includes(algorithm)) {
      throw new RangeError(`Unsupported route algorithm: ${algorithm}`);
    }
    if (!Number.isFinite(epsilon) || epsilon < 1) {
      throw new RangeError("Weighted A* epsilon must be at least 1");
    }
    const startIndex = indexOf(grid, start);
    const goalIndex = indexOf(grid, goal);
    if (!isWalkable(grid, start[0], start[1], safetyMarginCells)
      || !isWalkable(grid, goal[0], goal[1], safetyMarginCells)) {
      throw new Error(`Route endpoint is not walkable: ${start} -> ${goal}`);
    }
    if (startIndex === goalIndex) {
      return { path: [start], cost: 0, exploredCells: 0, computationMs: 0 };
    }

    const startedAt = performance.now();
    const costsSoFar = new Float64Array(grid.costs.length);
    costsSoFar.fill(Infinity);
    costsSoFar[startIndex] = 0;
    const cameFrom = new Int32Array(grid.costs.length);
    cameFrom.fill(-1);
    const queue = new BinaryHeap();
    queue.push({
      index: startIndex,
      cost: 0,
      priority: algorithm === "dijkstra"
        ? 0
        : heuristic(grid, startIndex, goal[0], goal[1])
          * (algorithm === "weighted" ? epsilon : 1),
    });
    let exploredCells = 0;

    while (queue.length) {
      const current = queue.pop();
      if (current.cost > costsSoFar[current.index]) continue;
      exploredCells += 1;
      if (current.index === goalIndex) {
        const path = [goal];
        let index = goalIndex;
        while (index !== startIndex) {
          index = cameFrom[index];
          path.push([Math.floor(index / grid.cols), index % grid.cols]);
        }
        return {
          path: path.reverse(),
          cost: current.cost,
          exploredCells,
          computationMs: performance.now() - startedAt,
        };
      }

      const row = Math.floor(current.index / grid.cols);
      const col = current.index % grid.cols;
      for (let rowDelta = -1; rowDelta <= 1; rowDelta += 1) {
        for (let colDelta = -1; colDelta <= 1; colDelta += 1) {
          if (!rowDelta && !colDelta) continue;
          const nextRow = row + rowDelta;
          const nextCol = col + colDelta;
          if (!isWalkable(grid, nextRow, nextCol, safetyMarginCells)) continue;
          if (rowDelta && colDelta
            && (!isWalkable(grid, row + rowDelta, col, safetyMarginCells)
              || !isWalkable(grid, row, col + colDelta, safetyMarginCells))) continue;
          const nextIndex = nextRow * grid.cols + nextCol;
          const nextCellCost = costs[nextIndex];
          const distanceM = Math.hypot(
            rowDelta * grid.cellSizeM.y,
            colDelta * grid.cellSizeM.x,
          );
          const nextCost = current.cost + distanceM * nextCellCost;
          if (nextCost >= costsSoFar[nextIndex]) continue;
          costsSoFar[nextIndex] = nextCost;
          cameFrom[nextIndex] = current.index;
          queue.push({
            index: nextIndex,
            cost: nextCost,
            priority: nextCost + (algorithm === "dijkstra" ? 0 : (
              heuristic(grid, nextIndex, goal[0], goal[1])
                * (algorithm === "weighted" ? epsilon : 1)
            )),
          });
        }
      }
    }
    throw new NoRouteError(start, goal);
  }

  function astar(
    grid,
    start,
    goal,
    safetyMarginCells = grid.parameters.safety_margin_cells,
  ) {
    return searchRoute(grid, start, goal, { safetyMarginCells }).path;
  }

  function routeDistanceKm(path, cellSizeM) {
    let distanceM = 0;
    for (let index = 1; index < path.length; index += 1) {
      distanceM += Math.hypot(
        (path[index][0] - path[index - 1][0]) * cellSizeM.y,
        (path[index][1] - path[index - 1][1]) * cellSizeM.x,
      );
    }
    return distanceM / 1000;
  }

  function planRoute(
    grid,
    habitat,
    checkpoints,
    returnToHabitat,
    previousPlan = null,
    changedCheckpointIndex = null,
    safetyMarginCells = grid.parameters.safety_margin_cells,
    { algorithm = "astar", epsilon = 1.5, costs = grid.costs } = {},
  ) {
    const points = [habitat, ...checkpoints];
    if (returnToHabitat) points.push(habitat);
    const legCount = points.length - 1;
    const canReuse = previousPlan
      && previousPlan.legs.length === legCount
      && previousPlan.algorithm === algorithm
      && previousPlan.epsilon === epsilon
      && previousPlan.safetyMarginCells === safetyMarginCells
      && costs === grid.costs
      && Number.isInteger(changedCheckpointIndex);
    const legs = canReuse ? previousPlan.legs.slice() : new Array(legCount);
    const firstLeg = canReuse ? Math.max(0, changedCheckpointIndex) : 0;
    const lastLeg = canReuse
      ? Math.min(legCount - 1, changedCheckpointIndex + 1)
      : legCount - 1;
    for (let index = firstLeg; index <= lastLeg; index += 1) {
      const start = points[index];
      const goal = points[index + 1];
      try {
        const result = searchRoute(
          grid,
          [start.row, start.col],
          [goal.row, goal.col],
          { algorithm, epsilon, safetyMarginCells, costs },
        );
        const distanceKm = routeDistanceKm(result.path, grid.cellSizeM);
        legs[index] = {
          path: result.path,
          distanceKm,
          timeH: distanceKm / grid.parameters.walking_speed_kmh,
          cost: result.cost,
          exploredCells: result.exploredCells,
          computationMs: result.computationMs,
          unreachable: false,
        };
      } catch (error) {
        if (!(error instanceof NoRouteError)) throw error;
        legs[index] = {
          path: [],
          distanceKm: null,
          timeH: null,
          cost: null,
          exploredCells: 0,
          computationMs: 0,
          unreachable: true,
        };
      }
    }

    const unreachable = legs.some((leg) => leg.unreachable);
    const distanceKm = unreachable
      ? null
      : legs.reduce((total, leg) => total + leg.distanceKm, 0);
    const timeH = distanceKm === null
      ? null
      : distanceKm / grid.parameters.walking_speed_kmh;
    const paths = legs.filter((leg) => !leg.unreachable).flatMap((leg) => leg.path);
    const minimumClearanceM = paths.length
      ? Math.min(...paths.map(([row, col]) => (
        grid.clearanceMeters[row * grid.cols + col]
      )))
      : null;
    return {
      points,
      legs,
      distanceKm,
      timeH,
      cost: unreachable ? null : legs.reduce((total, leg) => total + leg.cost, 0),
      exploredCells: legs.reduce((total, leg) => total + leg.exploredCells, 0),
      computationMs: legs.reduce((total, leg) => total + leg.computationMs, 0),
      minimumClearanceM,
      algorithm,
      epsilon,
      safetyMarginCells,
      returnMarginH: timeH === null ? null : grid.parameters.eva_hours - timeH,
      doseMsv: timeH === null
        ? null
        : timeH * grid.parameters.dose_rate_msv_per_hour,
      unreachable,
    };
  }

  function computeAlternatives(
    grid,
    habitat,
    checkpoints,
    returnToHabitat,
    fastestPlan,
    {
      safetyMarginCells = grid.parameters.safety_margin_cells,
      algorithm = fastestPlan.algorithm,
      epsilon = fastestPlan.epsilon,
    } = {},
  ) {
    const alternatives = [{ key: "fastest", name: "Fastest", plan: fastestPlan }];
    const parameters = grid.parameters;
    const extraClearanceWeight = Math.max(
      0,
      parameters.safer_clearance_cost_weight - parameters.clearance_cost_weight,
    );
    const saferCosts = new Float32Array(grid.costs.length);
    for (let index = 0; index < saferCosts.length; index += 1) {
      const baseCost = grid.costs[index];
      if (!Number.isFinite(baseCost)) {
        saferCosts[index] = Infinity;
        continue;
      }
      const clearancePenalty = Math.max(
        0,
        Math.min(
          1,
          (parameters.clearance_cost_radius_cells - grid.clearanceCells[index])
            / parameters.clearance_cost_radius_cells,
        ),
      );
      saferCosts[index] = baseCost + extraClearanceWeight * clearancePenalty;
    }
    const safer = planRoute(
      grid,
      habitat,
      checkpoints,
      returnToHabitat,
      null,
      null,
      safetyMarginCells,
      { algorithm, epsilon, costs: saferCosts },
    );
    if (!samePlanPaths(fastestPlan, safer)) {
      alternatives.push({ key: "safer", name: "Safer", plan: safer });
    }

    const alternateLegs = fastestPlan.legs.slice();
    let changed = false;
    for (let legIndex = 0; legIndex < fastestPlan.legs.length; legIndex += 1) {
      const fastestLeg = fastestPlan.legs[legIndex];
      if (fastestLeg.unreachable
        || fastestLeg.path.length <= parameters.alternate_route_min_leg_cells) continue;
      const penalizedCosts = new Float32Array(grid.costs);
      const corridor = new Uint8Array(grid.costs.length);
      const radius = parameters.alternate_route_corridor_cells;
      fastestLeg.path.forEach(([row, col]) => {
        for (let rowOffset = -radius; rowOffset <= radius; rowOffset += 1) {
          for (let colOffset = -radius; colOffset <= radius; colOffset += 1) {
            if (rowOffset * rowOffset + colOffset * colOffset > radius * radius) continue;
            const nextRow = row + rowOffset;
            const nextCol = col + colOffset;
            if (nextRow >= 0 && nextRow < grid.rows
              && nextCol >= 0 && nextCol < grid.cols) {
              corridor[nextRow * grid.cols + nextCol] = 1;
            }
          }
        }
      });
      for (let index = 0; index < penalizedCosts.length; index += 1) {
        if (corridor[index] && Number.isFinite(penalizedCosts[index])) {
          penalizedCosts[index] *= parameters.alternate_route_cost_multiplier;
        }
      }
      const start = fastestPlan.points[legIndex];
      const goal = fastestPlan.points[legIndex + 1];
      let candidate;
      try {
        candidate = searchRoute(
          grid,
          [start.row, start.col],
          [goal.row, goal.col],
          { algorithm, epsilon, safetyMarginCells, costs: penalizedCosts },
        );
      } catch (error) {
        if (!(error instanceof NoRouteError)) throw error;
        continue;
      }
      const fastestCells = new Set(fastestLeg.path.map(([row, col]) => (
        row * grid.cols + col
      )));
      const overlap = candidate.path.filter(([row, col]) => (
        fastestCells.has(row * grid.cols + col)
      )).length / candidate.path.length;
      const distanceKm = routeDistanceKm(candidate.path, grid.cellSizeM);
      const timeH = distanceKm / parameters.walking_speed_kmh;
      if (overlap >= parameters.alternate_route_max_overlap
        || timeH > fastestLeg.timeH * parameters.alternate_route_max_time_factor) continue;
      alternateLegs[legIndex] = {
        ...fastestLeg,
        path: candidate.path,
        distanceKm,
        timeH,
        cost: candidate.cost,
        exploredCells: candidate.exploredCells,
        computationMs: candidate.computationMs,
        unreachable: false,
      };
      changed = true;
    }
    if (changed) {
      const alternate = summarizePlan(
        grid,
        fastestPlan.points,
        alternateLegs,
        algorithm,
        epsilon,
        safetyMarginCells,
      );
      const allFastestCells = new Set(fastestPlan.legs.flatMap((leg) => (
        leg.path.map(([row, col]) => row * grid.cols + col)
      )));
      const allAlternateCells = alternate.legs.flatMap((leg) => leg.path);
      const overallOverlap = allAlternateCells.filter(([row, col]) => (
        allFastestCells.has(row * grid.cols + col)
      )).length / allAlternateCells.length;
      const duplicate = alternatives.some(({ plan }) => samePlanPaths(plan, alternate));
      if (!duplicate && overallOverlap < parameters.alternate_route_max_overlap
        && alternate.timeH <= fastestPlan.timeH * parameters.alternate_route_max_time_factor) {
        alternatives.push({ key: "alternate", name: "Alternate", plan: alternate });
      }
    }
    return alternatives;
  }

  function summarizePlan(grid, points, legs, algorithm, epsilon, safetyMarginCells) {
    const unreachable = legs.some((leg) => leg.unreachable);
    const distanceKm = unreachable
      ? null
      : legs.reduce((total, leg) => total + leg.distanceKm, 0);
    const timeH = distanceKm === null
      ? null
      : distanceKm / grid.parameters.walking_speed_kmh;
    const path = legs.filter((leg) => !leg.unreachable).flatMap((leg) => leg.path);
    return {
      points,
      legs,
      distanceKm,
      timeH,
      cost: unreachable ? null : legs.reduce((total, leg) => total + leg.cost, 0),
      exploredCells: legs.reduce((total, leg) => total + leg.exploredCells, 0),
      computationMs: legs.reduce((total, leg) => total + leg.computationMs, 0),
      minimumClearanceM: path.length
        ? Math.min(...path.map(([row, col]) => grid.clearanceMeters[row * grid.cols + col]))
        : null,
      algorithm,
      epsilon,
      safetyMarginCells,
      returnMarginH: timeH === null ? null : grid.parameters.eva_hours - timeH,
      doseMsv: timeH === null ? null : timeH * grid.parameters.dose_rate_msv_per_hour,
      unreachable,
    };
  }

  function samePlanPaths(left, right) {
    return left.legs.length === right.legs.length
      && left.legs.every((leg, index) => {
        const other = right.legs[index];
        return leg.path.length === other.path.length
          && leg.path.every(([row, col], pointIndex) => (
            row === other.path[pointIndex][0] && col === other.path[pointIndex][1]
          ));
      });
  }

  const api = {
    NoRouteError,
    astar,
    computeAlternatives,
    decodeGrid,
    isWalkable,
    planRoute,
    routeDistanceKm,
    searchRoute,
  };
  globalScope.RoutePlanner = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
}(typeof window === "undefined" ? globalThis : window));
