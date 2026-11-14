"""Plan a low-slope EVA route over the processed placeholder rasters."""

import heapq
import json
import math

import numpy as np
import rasterio
from rasterio.transform import xy

if __package__:
    from .config import (
        DEM_PATH,
        EVA_HOURS,
        GRID_PATH,
        HABITAT_PIXEL,
        HAZARD_PATH,
        MAX_WALKABLE_SLOPE_DEG,
        ROUTE_PATH,
        SCIENCE_TARGET_PIXELS,
        SLOPE_PATH,
        STATS_PATH,
        WALKING_SPEED_KMH,
        DOSE_RATE_MSV_PER_HOUR,
    )
    from .slope import cell_size_meters
else:
    from config import (
        DEM_PATH,
        EVA_HOURS,
        GRID_PATH,
        HABITAT_PIXEL,
        HAZARD_PATH,
        MAX_WALKABLE_SLOPE_DEG,
        ROUTE_PATH,
        SCIENCE_TARGET_PIXELS,
        SLOPE_PATH,
        STATS_PATH,
        WALKING_SPEED_KMH,
        DOSE_RATE_MSV_PER_HOUR,
    )
    from slope import cell_size_meters


PLACEHOLDER_STATUS = "PLACEHOLDER - route derived from synthetic DEM"


def neighbours(row: int, col: int, rows: int, cols: int):
    for row_delta in (-1, 0, 1):
        for col_delta in (-1, 0, 1):
            if not row_delta and not col_delta:
                continue
            next_row = row + row_delta
            next_col = col + col_delta
            if 0 <= next_row < rows and 0 <= next_col < cols:
                yield next_row, next_col


def astar(
    start: tuple[int, int],
    goal: tuple[int, int],
    walkable: np.ndarray,
    slope_deg: np.ndarray,
    x_size_m: float,
    y_size_m: float,
) -> list[tuple[int, int]]:
    """Return an 8-neighbor route or raise when no safe route exists."""
    if not walkable[start] or not walkable[goal]:
        raise ValueError(f"Route endpoint is not walkable: {start} -> {goal}")

    def heuristic(cell: tuple[int, int]) -> float:
        row_delta = (cell[0] - goal[0]) * y_size_m
        col_delta = (cell[1] - goal[1]) * x_size_m
        return math.hypot(row_delta, col_delta)

    queue = [(heuristic(start), 0.0, start)]
    came_from: dict[tuple[int, int], tuple[int, int]] = {}
    cost_so_far = {start: 0.0}

    while queue:
        _, current_cost, current = heapq.heappop(queue)
        if current == goal:
            path = [current]
            while current in came_from:
                current = came_from[current]
                path.append(current)
            return list(reversed(path))
        if current_cost > cost_so_far[current]:
            continue

        for next_cell in neighbours(*current, *walkable.shape):
            if not walkable[next_cell]:
                continue
            row_step = (next_cell[0] - current[0]) * y_size_m
            col_step = (next_cell[1] - current[1]) * x_size_m
            distance_m = math.hypot(row_step, col_step)
            terrain_factor = 1.0 + float(slope_deg[next_cell]) / MAX_WALKABLE_SLOPE_DEG
            next_cost = current_cost + distance_m * terrain_factor
            if next_cost < cost_so_far.get(next_cell, math.inf):
                cost_so_far[next_cell] = next_cost
                came_from[next_cell] = current
                heapq.heappush(
                    queue, (next_cost + heuristic(next_cell), next_cost, next_cell)
                )

    raise ValueError(f"No walkable route exists: {start} -> {goal}")


def main() -> None:
    with rasterio.open(DEM_PATH) as dem_source, rasterio.open(
        HAZARD_PATH
    ) as hazard_source:
        with rasterio.open(SLOPE_PATH) as slope_source:
            slope_deg = slope_source.read(1)
        hazard = hazard_source.read(1)
        walkable = (hazard == 0) & np.isfinite(slope_deg)
        x_size_m, y_size_m = cell_size_meters(dem_source)
        transform = dem_source.transform
        dem_bounds = dem_source.bounds
        rows, cols = walkable.shape

    points = [HABITAT_PIXEL, *SCIENCE_TARGET_PIXELS, HABITAT_PIXEL]
    route_pixels: list[tuple[int, int]] = []
    for start, goal in zip(points, points[1:]):
        segment = astar(start, goal, walkable, slope_deg, x_size_m, y_size_m)
        route_pixels.extend(segment if not route_pixels else segment[1:])

    route_coordinates = [
        list(xy(transform, row, col, offset="center"))
        for row, col in route_pixels
    ]
    distance_km = sum(
        math.hypot(
            (route_pixels[index + 1][0] - route_pixels[index][0]) * y_size_m,
            (route_pixels[index + 1][1] - route_pixels[index][1]) * x_size_m,
        )
        for index in range(len(route_pixels) - 1)
    ) / 1000
    time_h = distance_km / WALKING_SPEED_KMH
    if time_h > EVA_HOURS:
        raise ValueError(f"Route requires {time_h:.2f} h, over EVA limit {EVA_HOURS:.2f} h")

    targets = [
        {
            "id": f"target-{index + 1}",
            "row": row,
            "col": col,
            "lon": coordinates[0],
            "lat": coordinates[1],
        }
        for index, (row, col) in enumerate(SCIENCE_TARGET_PIXELS)
        for coordinates in [xy(transform, row, col, offset="center")]
    ]
    stats = {
        "data_status": PLACEHOLDER_STATUS,
        "distance_km": round(distance_km, 3),
        "time_h": round(time_h, 3),
        "return_margin_h": round(EVA_HOURS - time_h, 3),
        "est_dose_msv": round(time_h * DOSE_RATE_MSV_PER_HOUR, 4),
        "max_walkable_slope_deg": MAX_WALKABLE_SLOPE_DEG,
    }
    grid = {
        "data_status": PLACEHOLDER_STATUS,
        "rows": rows,
        "cols": cols,
        "max_walkable_slope_deg": MAX_WALKABLE_SLOPE_DEG,
        "bounds": [
            dem_bounds.left,
            dem_bounds.bottom,
            dem_bounds.right,
            dem_bounds.top,
        ],
        "slope_deg": np.round(slope_deg, 3).tolist(),
        "walkable": walkable.tolist(),
        "targets": targets,
        "habitat": {
            "row": HABITAT_PIXEL[0],
            "col": HABITAT_PIXEL[1],
            "lon": xy(transform, *HABITAT_PIXEL, offset="center")[0],
            "lat": xy(transform, *HABITAT_PIXEL, offset="center")[1],
        },
    }
    geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"data_status": PLACEHOLDER_STATUS},
                "geometry": {"type": "LineString", "coordinates": route_coordinates},
            }
        ],
    }
    ROUTE_PATH.write_text(json.dumps(geojson, indent=2))
    STATS_PATH.write_text(json.dumps(stats, indent=2) + "\n")
    GRID_PATH.write_text(json.dumps(grid) + "\n")
    print(
        f"Route placeholder: {distance_km:.3f} km, {time_h:.3f} h, "
        f"return margin {EVA_HOURS - time_h:.3f} h, dose {stats['est_dose_msv']:.4f} mSv"
    )


if __name__ == "__main__":
    main()
