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

  function decodeGrid(metadata, buffer) {
    const { rows, cols } = metadata;
    const count = rows * cols;
    if (!Number.isInteger(rows) || !Number.isInteger(cols) || rows < 1 || cols < 1) {
      throw new Error("Route grid dimensions are invalid");
    }
    if (metadata.dtype !== "float32" || metadata.byte_order !== "little-endian") {
      throw new Error("Unsupported route grid encoding");
    }
    if (buffer.byteLength !== count * Float32Array.BYTES_PER_ELEMENT) {
      throw new Error(`Route grid has ${buffer.byteLength} bytes; expected ${count * 4}`);
    }
    const view = new DataView(buffer);
    const costs = new Float32Array(count);
    for (let index = 0; index < count; index += 1) {
      costs[index] = view.getFloat32(index * 4, true);
    }
    return {
      ...metadata,
      costs,
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
    return Math.hypot(
      (row - goalRow) * grid.cellSizeM.y,
      (col - goalCol) * grid.cellSizeM.x,
    );
  }

  function astar(grid, start, goal) {
    const startIndex = indexOf(grid, start);
    const goalIndex = indexOf(grid, goal);
    if (grid.costs[startIndex] < 0 || grid.costs[goalIndex] < 0) {
      throw new Error(`Route endpoint is not walkable: ${start} -> ${goal}`);
    }
    if (startIndex === goalIndex) return [start];

    const costsSoFar = new Float64Array(grid.costs.length);
    costsSoFar.fill(Infinity);
    costsSoFar[startIndex] = 0;
    const cameFrom = new Int32Array(grid.costs.length);
    cameFrom.fill(-1);
    const queue = new BinaryHeap();
    queue.push({
      index: startIndex,
      cost: 0,
      priority: heuristic(grid, startIndex, goal[0], goal[1]),
    });

    while (queue.length) {
      const current = queue.pop();
      if (current.cost > costsSoFar[current.index]) continue;
      if (current.index === goalIndex) {
        const path = [goal];
        let index = goalIndex;
        while (index !== startIndex) {
          index = cameFrom[index];
          path.push([Math.floor(index / grid.cols), index % grid.cols]);
        }
        return path.reverse();
      }

      const row = Math.floor(current.index / grid.cols);
      const col = current.index % grid.cols;
      for (let rowDelta = -1; rowDelta <= 1; rowDelta += 1) {
        for (let colDelta = -1; colDelta <= 1; colDelta += 1) {
          if (!rowDelta && !colDelta) continue;
          const nextRow = row + rowDelta;
          const nextCol = col + colDelta;
          if (nextRow < 0 || nextRow >= grid.rows
            || nextCol < 0 || nextCol >= grid.cols) continue;
          const nextIndex = nextRow * grid.cols + nextCol;
          const nextCellCost = grid.costs[nextIndex];
          if (nextCellCost < 0 || !Number.isFinite(nextCellCost)) continue;
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
            priority: nextCost + heuristic(grid, nextIndex, goal[0], goal[1]),
          });
        }
      }
    }
    throw new NoRouteError(start, goal);
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
  ) {
    const points = [habitat, ...checkpoints];
    if (returnToHabitat) points.push(habitat);
    const legCount = points.length - 1;
    const canReuse = previousPlan
      && previousPlan.legs.length === legCount
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
        const path = astar(grid, [start.row, start.col], [goal.row, goal.col]);
        const distanceKm = routeDistanceKm(path, grid.cellSizeM);
        legs[index] = {
          path,
          distanceKm,
          timeH: distanceKm / grid.parameters.walking_speed_kmh,
          unreachable: false,
        };
      } catch (error) {
        if (!(error instanceof NoRouteError)) throw error;
        legs[index] = {
          path: [[start.row, start.col], [goal.row, goal.col]],
          distanceKm: null,
          timeH: null,
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
    return {
      points,
      legs,
      distanceKm,
      timeH,
      returnMarginH: timeH === null ? null : grid.parameters.eva_hours - timeH,
      doseMsv: timeH === null
        ? null
        : timeH * grid.parameters.dose_rate_msv_per_hour,
      unreachable,
    };
  }

  const api = { NoRouteError, astar, decodeGrid, planRoute, routeDistanceKm };
  globalScope.RoutePlanner = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
}(typeof window === "undefined" ? globalThis : window));
