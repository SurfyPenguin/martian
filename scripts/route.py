"""Plan a low-risk EVA route over one real site's processed rasters."""

import argparse
import heapq
import json
import math

import numpy as np
import rasterio

from config import (
    DOSE_RATE_MSV_PER_HOUR,
    EVA_HOURS,
    MAX_ROUGHNESS_M,
    MAX_WALKABLE_SLOPE_DEG,
    ROUGHNESS_COST_WEIGHT,
    SLOPE_COST_POWER,
    WALKING_SPEED_KMH,
    SITES,
    site_config,
    site_output_dir,
)
from slope import cell_size_meters


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
    slope: np.ndarray,
    roughness: np.ndarray,
    x_size_m: float,
    y_size_m: float,
) -> list[tuple[int, int]]:
    if not walkable[start] or not walkable[goal]:
        raise ValueError(f"Route endpoint is not walkable: {start} -> {goal}")

    def heuristic(cell: tuple[int, int]) -> float:
        return math.hypot(
            (cell[0] - goal[0]) * y_size_m,
            (cell[1] - goal[1]) * x_size_m,
        )

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
            distance_m = math.hypot(
                (next_cell[0] - current[0]) * y_size_m,
                (next_cell[1] - current[1]) * x_size_m,
            )
            slope_factor = (
                float(slope[next_cell]) / MAX_WALKABLE_SLOPE_DEG
            ) ** SLOPE_COST_POWER
            roughness_factor = (
                float(roughness[next_cell]) / MAX_ROUGHNESS_M
            ) * ROUGHNESS_COST_WEIGHT
            next_cost = current_cost + distance_m * (
                1.0 + slope_factor + roughness_factor
            )
            if next_cost < cost_so_far.get(next_cell, math.inf):
                cost_so_far[next_cell] = next_cost
                came_from[next_cell] = current
                heapq.heappush(
                    queue, (next_cost + heuristic(next_cell), next_cost, next_cell)
                )
    raise ValueError(f"No walkable route exists: {start} -> {goal}")


def latlon_to_pixel(
    point: dict, bounds: dict, rows: int, cols: int
) -> tuple[int, int]:
    row = round((bounds["max_lat"] - point["lat"])
                / (bounds["max_lat"] - bounds["min_lat"]) * (rows - 1))
    col = round((point["lon"] - bounds["min_lon"])
                / (bounds["max_lon"] - bounds["min_lon"]) * (cols - 1))
    if not (0 <= row < rows and 0 <= col < cols):
        raise ValueError(f"Coordinate is outside the configured DEM bounds: {point}")
    return row, col


def pixel_to_latlon(pixel: tuple[int, int], bounds: dict, rows: int, cols: int):
    row, col = pixel
    return {
        "lat": bounds["max_lat"] - row / max(1, rows - 1)
        * (bounds["max_lat"] - bounds["min_lat"]),
        "lon": bounds["min_lon"] + col / max(1, cols - 1)
        * (bounds["max_lon"] - bounds["min_lon"]),
    }


def route_distance_km(route: list[tuple[int, int]], x_size_m: float, y_size_m: float):
    return sum(
        math.hypot(
            (route[index + 1][0] - route[index][0]) * y_size_m,
            (route[index + 1][1] - route[index][1]) * x_size_m,
        )
        for index in range(len(route) - 1)
    ) / 1000


def process_site(site: str) -> None:
    config = site_config(site)
    output = site_output_dir(site)
    dem_path = config["dem_path"]
    with rasterio.open(dem_path) as dem_source:
        rows, cols = dem_source.height, dem_source.width
        x_size_m, y_size_m = cell_size_meters(dem_source)
        dem_bounds = dem_source.bounds
    with rasterio.open(output / "slope.tif") as source:
        slope = source.read(1)
    with rasterio.open(output / "roughness.tif") as source:
        roughness = source.read(1)
    with rasterio.open(output / "hazard.tif") as source:
        hazard = source.read(1)

    slope_valid = np.isfinite(slope) & (slope != -9999)
    roughness_valid = np.isfinite(roughness) & (roughness != -9999)
    walkable = (
        slope_valid
        & roughness_valid
        & (slope <= MAX_WALKABLE_SLOPE_DEG)
        & (roughness <= MAX_ROUGHNESS_M)
    )
    valid_cells = slope_valid.sum()
    above_slope = slope_valid & (slope > MAX_WALKABLE_SLOPE_DEG)
    print(
        f"{site}: cell size x={x_size_m:.3f} m, y={y_size_m:.3f} m; "
        f"slope>{MAX_WALKABLE_SLOPE_DEG:g}° in "
        f"{100 * above_slope.sum() / valid_cells:.2f}% of valid slope cells"
    )

    bounds = config["bounds"]
    points = [config["habitat"], *config["targets"], config["habitat"]]
    pixels = [latlon_to_pixel(point, bounds, rows, cols) for point in points]
    route_segments = []
    try:
        for start, goal in zip(pixels, pixels[1:]):
            route_segments.append(
                astar(start, goal, walkable, slope, roughness, x_size_m, y_size_m)
            )
    except ValueError as error:
        raise RuntimeError(
            f"{site} has no valid route with the configured assumptions: {error}. "
            f"Move the placeholder habitat or targets; do not relax thresholds."
        ) from error

    route_pixels = route_segments[0][:]
    for segment in route_segments[1:]:
        route_pixels.extend(segment[1:])
    distance_km = route_distance_km(route_pixels, x_size_m, y_size_m)
    time_h = distance_km / WALKING_SPEED_KMH
    if time_h > EVA_HOURS:
        raise RuntimeError(
            f"{site} route requires {time_h:.2f} h, over the {EVA_HOURS:.2f} h "
            "EVA assumption; move the placeholder habitat or targets."
        )

    legs = []
    for index, segment in enumerate(route_segments):
        distance = route_distance_km(segment, x_size_m, y_size_m)
        legs.append({
            "name": "return" if index == len(route_segments) - 1 else f"target-{index + 1}",
            "distance_km": round(distance, 3),
            "time_h": round(distance / WALKING_SPEED_KMH, 3),
        })
    stats = {
        "data_status": "REAL - route derived from supplied NASA DEM",
        "distance_km": round(distance_km, 3),
        "time_h": round(time_h, 3),
        "return_margin_h": round(EVA_HOURS - time_h, 3),
        "est_dose_msv": round(time_h * DOSE_RATE_MSV_PER_HOUR, 4),
        "max_walkable_slope_deg": MAX_WALKABLE_SLOPE_DEG,
        "max_roughness_m": MAX_ROUGHNESS_M,
        "slope_over_limit_fraction": round(float(above_slope.sum() / valid_cells), 6),
        "cell_size_m": {"x": round(x_size_m, 3), "y": round(y_size_m, 3)},
    }
    grid = {
        "data_status": "REAL - supplied NASA DEM and CTX imagery",
        "site": site,
        "site_name": config["name"],
        "rows": rows,
        "cols": cols,
        "grid_bounds": [[0, 0], [rows, cols]],
        "geo_reference": {"status": "REAL DEM bounds", "bounds": bounds},
        "cell_size_m": {"x": x_size_m, "y": y_size_m},
        "max_walkable_slope_deg": MAX_WALKABLE_SLOPE_DEG,
        "max_roughness_m": MAX_ROUGHNESS_M,
        "route_pixels": route_pixels,
        "route_segments": route_segments,
        "targets": [
            {"id": f"target-{index + 1}", "row": row, "col": col,
             "lat": point["lat"], "lon": point["lon"]}
            for index, (point, (row, col)) in enumerate(zip(config["targets"], pixels[1:-1]))
        ],
        "legs": legs,
        "habitat": {
            "row": pixels[0][0], "col": pixels[0][1],
            "lat": config["habitat"]["lat"], "lon": config["habitat"]["lon"],
        },
        "coordinate_status": "PLACEHOLDER - replace habitat and target coordinates",
        "layer_paths": {
            "elevation": f"data/processed/{site}/elevation.png",
            "imagery": f"data/processed/{site}/imagery.png",
            "slope": f"data/processed/{site}/slope.png",
            "hazard": f"data/processed/{site}/hazard.png",
        },
    }
    (output / "stats.json").write_text(json.dumps(stats, indent=2) + "\n")
    (output / "grid.json").write_text(json.dumps(grid) + "\n")
    outbound = route_segments[:-1]
    outbound_pixels = outbound[0][:]
    for segment in outbound[1:]:
        outbound_pixels.extend(segment[1:])
    features = []
    for name, pixels_for_leg in (("outbound", outbound_pixels), ("return", route_segments[-1])):
        features.append({
            "type": "Feature",
            "properties": {"data_status": "REAL - derived from supplied NASA DEM", "leg": name},
            "geometry": {"type": "LineString", "coordinates": [list(p) for p in pixels_for_leg]},
        })
    (output / "route.geojson").write_text(json.dumps({
        "type": "FeatureCollection",
        "properties": {"data_status": "REAL - derived from supplied NASA DEM",
                       "coordinate_system": "grid row,col"},
        "features": features,
    }, indent=2) + "\n")
    print(f"{site}: route {distance_km:.3f} km, {time_h:.3f} h")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", choices=sorted(SITES), required=True)
    args = parser.parse_args()
    process_site(args.site)


if __name__ == "__main__":
    main()
