"""Plan a low-risk EVA route over one real site's processed rasters."""

import argparse
import heapq
import json
import math

import numpy as np
import rasterio
from scipy import ndimage

from config import (
    CLEARANCE_COST_RADIUS_CELLS,
    CLEARANCE_COST_WEIGHT,
    ALTERNATE_ROUTE_COST_MULTIPLIER,
    ALTERNATE_ROUTE_CORRIDOR_CELLS,
    ALTERNATE_ROUTE_MAX_OVERLAP,
    ALTERNATE_ROUTE_MAX_TIME_FACTOR,
    ALTERNATE_ROUTE_MIN_LEG_CELLS,
    DOSE_RATE_MSV_PER_HOUR,
    EVA_HOURS,
    MAX_ROUGHNESS_M,
    MAX_WALKABLE_SLOPE_DEG,
    PROJECT_ROOT,
    ROUGHNESS_COST_WEIGHT,
    SAFER_CLEARANCE_COST_WEIGHT,
    SAFETY_MARGIN_CELLS,
    SLOPE_COST_POWER,
    WEIGHTED_ASTAR_EPSILON,
    WALKING_SPEED_KMH,
    SITES,
    site_config,
    site_output_dir,
)
from slope import cell_size_meters
from rasterio.transform import rowcol, xy


def neighbours(row: int, col: int, rows: int, cols: int):
    for row_delta in (-1, 0, 1):
        for col_delta in (-1, 0, 1):
            if not row_delta and not col_delta:
                continue
            next_row = row + row_delta
            next_col = col + col_delta
            if 0 <= next_row < rows and 0 <= next_col < cols:
                yield next_row, next_col


def _distance_transform_1d(costs: np.ndarray, spacing: float) -> np.ndarray:
    """Return exact squared distances to finite sites along one axis."""
    finite_sites = np.flatnonzero(np.isfinite(costs))
    result = np.full(costs.shape, np.inf, dtype="float64")
    if finite_sites.size == 0:
        return result

    spacing_squared = spacing * spacing
    sites = np.empty(finite_sites.size, dtype="int32")
    boundaries = np.empty(finite_sites.size + 1, dtype="float64")
    envelope = 0
    sites[0] = finite_sites[0]
    boundaries[0] = -np.inf
    boundaries[1] = np.inf
    for candidate in finite_sites[1:]:
        intersection = (
            costs[candidate] + spacing_squared * candidate * candidate
            - costs[sites[envelope]]
            - spacing_squared * sites[envelope] * sites[envelope]
        ) / (2 * spacing_squared * (candidate - sites[envelope]))
        while intersection <= boundaries[envelope]:
            envelope -= 1
            intersection = (
                costs[candidate] + spacing_squared * candidate * candidate
                - costs[sites[envelope]]
                - spacing_squared * sites[envelope] * sites[envelope]
            ) / (2 * spacing_squared * (candidate - sites[envelope]))
        envelope += 1
        sites[envelope] = candidate
        boundaries[envelope] = intersection
        boundaries[envelope + 1] = np.inf

    envelope = 0
    for coordinate in range(costs.size):
        while boundaries[envelope + 1] < coordinate:
            envelope += 1
        offset = (coordinate - sites[envelope]) * spacing
        result[coordinate] = offset * offset + costs[sites[envelope]]
    return result


def distance_to_hazards(
    hazard_mask: np.ndarray,
    x_size_m: float,
    y_size_m: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Compute Euclidean clearance in cells and meters from the hazard mask."""
    if hazard_mask.ndim != 2:
        raise ValueError("Hazard mask must be a two-dimensional array")
    if not np.any(hazard_mask):
        shape = hazard_mask.shape
        return (
            np.full(shape, np.inf, dtype="float32"),
            np.full(shape, np.inf, dtype="float32"),
        )

    def transform(x_spacing: float, y_spacing: float) -> np.ndarray:
        horizontal_squared = np.empty(hazard_mask.shape, dtype="float64")
        for row in range(hazard_mask.shape[0]):
            horizontal_squared[row] = _distance_transform_1d(
                np.where(hazard_mask[row], 0.0, np.inf),
                x_spacing,
            )
        squared = np.empty(hazard_mask.shape, dtype="float64")
        for col in range(hazard_mask.shape[1]):
            squared[:, col] = _distance_transform_1d(
                horizontal_squared[:, col],
                y_spacing,
            )
        return np.sqrt(squared).astype("float32")

    return transform(1.0, 1.0), transform(x_size_m, y_size_m)


def make_route_cost_grid(
    slope_deg: np.ndarray,
    roughness: np.ndarray,
    hazard_mask: np.ndarray,
    clearance_cells: np.ndarray,
) -> np.ndarray:
    """Build finite terrain costs from the exported mask; hazards stay infinite."""
    shapes = {slope_deg.shape, roughness.shape, hazard_mask.shape, clearance_cells.shape}
    if len(shapes) != 1:
        raise ValueError("Slope, roughness, hazard, and clearance grids must align")
    walkable = ~hazard_mask
    if np.any(~np.isfinite(slope_deg[walkable])) or np.any(
        ~np.isfinite(roughness[walkable])
    ):
        raise ValueError("The hazard mask leaves invalid terrain cells walkable")

    costs = np.full(hazard_mask.shape, np.inf, dtype="float32")
    slope_factor = (
        slope_deg[walkable].astype("float64") / MAX_WALKABLE_SLOPE_DEG
    ) ** SLOPE_COST_POWER
    roughness_factor = (
        roughness[walkable].astype("float64") / MAX_ROUGHNESS_M
    ) * ROUGHNESS_COST_WEIGHT
    clearance_penalty = CLEARANCE_COST_WEIGHT * np.clip(
        (CLEARANCE_COST_RADIUS_CELLS - clearance_cells[walkable])
        / CLEARANCE_COST_RADIUS_CELLS,
        0,
        1,
    )
    costs[walkable] = (
        1 + slope_factor + roughness_factor + clearance_penalty
    ).astype("float32")
    return costs


def build_walkable_mask(
    costs: np.ndarray,
    clearance_cells: np.ndarray,
    safety_margin_cells: int,
) -> np.ndarray:
    if safety_margin_cells < 0:
        raise ValueError("Safety margin must be non-negative")
    return np.isfinite(costs) & (clearance_cells > safety_margin_cells)


def passability_metrics(walkable: np.ndarray) -> tuple[float, int]:
    """Measure the largest passable component and narrow links between large regions."""
    structure = ndimage.generate_binary_structure(2, 1)
    labels, component_count = ndimage.label(walkable, structure=structure)
    if component_count == 0:
        return 0.0, 0
    sizes = np.bincount(labels.ravel(), minlength=component_count + 1)
    sizes[0] = 0
    largest_fraction = float(sizes.max() / walkable.size)

    core = walkable & (ndimage.distance_transform_edt(walkable) > 2)
    core_labels, core_count = ndimage.label(core, structure=structure)
    if core_count < 2:
        return largest_fraction, 0
    core_sizes = np.bincount(core_labels.ravel(), minlength=core_count + 1)
    large_core = core_sizes >= max(100, math.ceil(walkable.size * 0.01))
    narrow_labels, narrow_count = ndimage.label(walkable & ~core, structure=structure)
    connected_pairs = []
    rows, cols = walkable.shape
    for row_delta, col_delta in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        row_start = max(0, -row_delta)
        row_end = min(rows, rows - row_delta)
        col_start = max(0, -col_delta)
        col_end = min(cols, cols - col_delta)
        narrow_side = narrow_labels[row_start:row_end, col_start:col_end]
        core_side = core_labels[
            row_start + row_delta:row_end + row_delta,
            col_start + col_delta:col_end + col_delta,
        ]
        touching = (
            (narrow_side > 0)
            & (core_side > 0)
            & large_core[core_side]
        )
        if np.any(touching):
            connected_pairs.append(
                np.column_stack((narrow_side[touching], core_side[touching]))
            )
    if not connected_pairs:
        return largest_fraction, 0
    pairs = np.unique(np.concatenate(connected_pairs), axis=0)
    corridor_core_count = np.zeros(narrow_count + 1, dtype="uint32")
    np.add.at(corridor_core_count, pairs[:, 0], 1)
    return largest_fraction, int(np.count_nonzero(corridor_core_count[1:] >= 2))


def write_site_manifest() -> None:
    sites = []
    for key, config in SITES.items():
        output = PROJECT_ROOT / "data" / "processed" / key
        stats_path = output / "stats.json"
        grid_path = output / "grid.json"
        stats = json.loads(stats_path.read_text()) if stats_path.is_file() else {}
        grid = json.loads(grid_path.read_text()) if grid_path.is_file() else {}
        hazard_fraction = stats.get("hazard_fraction")
        chokepoints = stats.get("chokepoints")
        largest_fraction = stats.get("largest_passable_component_fraction")
        descriptor = "Processed NASA terrain data"
        if hazard_fraction is not None and chokepoints is not None:
            chokepoint_label = "chokepoint" if chokepoints == 1 else "chokepoints"
            descriptor = (
                f"{hazard_fraction:.0%} hazard, "
                f"{chokepoints} {chokepoint_label}"
            )
            if largest_fraction is not None:
                descriptor += f", {largest_fraction:.0%} largest passable component"
        sites.append(
            {
                "key": key,
                "name": config["name"],
                "bounds": grid.get("geo_reference", {}).get(
                    "bounds", config["bounds"]
                ),
                "descriptor": descriptor,
                "limitations_note": config.get("limitations_note", ""),
            }
        )
    path = PROJECT_ROOT / "web" / "data" / "sites.json"
    manifest = {"default_site": next(iter(SITES)), "sites": sites}
    path.write_text(json.dumps(manifest, indent=2) + "\n")


def astar(
    start: tuple[int, int],
    goal: tuple[int, int],
    walkable: np.ndarray,
    costs: np.ndarray,
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
            row_delta = next_cell[0] - current[0]
            col_delta = next_cell[1] - current[1]
            if row_delta and col_delta and (
                not walkable[current[0] + row_delta, current[1]]
                or not walkable[current[0], current[1] + col_delta]
            ):
                continue
            distance_m = math.hypot(
                row_delta * y_size_m,
                col_delta * x_size_m,
            )
            next_cost = current_cost + distance_m * float(costs[next_cell])
            if next_cost < cost_so_far.get(next_cell, math.inf):
                cost_so_far[next_cell] = next_cost
                came_from[next_cell] = current
                heapq.heappush(
                    queue, (next_cost + heuristic(next_cell), next_cost, next_cell)
                )
    raise ValueError(f"No walkable route exists: {start} -> {goal}")


def latlon_to_pixel(point: dict, transform, rows: int, cols: int) -> tuple[int, int]:
    row, col = rowcol(transform, point["lon"], point["lat"])
    if not (0 <= row < rows and 0 <= col < cols):
        raise ValueError(f"Coordinate is outside the configured DEM bounds: {point}")
    return int(row), int(col)


def pixel_to_latlon(pixel: tuple[int, int], transform):
    row, col = pixel
    lon, lat = xy(transform, row, col, offset="center")
    return {"lat": lat, "lon": lon}


def route_distance_km(route: list[tuple[int, int]], x_size_m: float, y_size_m: float):
    return sum(
        math.hypot(
            (route[index + 1][0] - route[index][0]) * y_size_m,
            (route[index + 1][1] - route[index][1]) * x_size_m,
        )
        for index in range(len(route) - 1)
    ) / 1000


def export_route_cost_grid(
    site: str,
    costs: np.ndarray,
    clearance_cells: np.ndarray,
    clearance_meters: np.ndarray,
    bounds: dict,
    transform,
    x_size_m: float,
    y_size_m: float,
) -> None:
    """Export costs and clearances derived from the exported hazard mask."""
    output = PROJECT_ROOT / "web" / "data" / site
    output.mkdir(parents=True, exist_ok=True)

    for filename, values in (
        ("cost.bin", costs),
        ("clearance-cells.bin", clearance_cells),
        ("clearance-meters.bin", clearance_meters),
    ):
        (output / filename).write_bytes(
            np.asarray(values, dtype="<f4").tobytes(order="C")
        )

    metadata = {
        "format_version": 2,
        "data_status": "REAL - derived from supplied NASA DEM",
        "site": site,
        "rows": int(costs.shape[0]),
        "cols": int(costs.shape[1]),
        "bounds": bounds,
        "raster_transform": list(transform)[:6],
        "cell_size_m": {"x": x_size_m, "y": y_size_m},
        "dtype": "float32",
        "byte_order": "little-endian",
        "layout": "row-major",
        "hazard_cost": "positive-infinity",
        "clearance_files": {
            "cells": "clearance-cells.bin",
            "meters": "clearance-meters.bin",
        },
        "parameters": {
            "max_walkable_slope_deg": MAX_WALKABLE_SLOPE_DEG,
            "max_roughness_m": MAX_ROUGHNESS_M,
            "slope_cost_power": SLOPE_COST_POWER,
            "roughness_cost_weight": ROUGHNESS_COST_WEIGHT,
            "safety_margin_cells": SAFETY_MARGIN_CELLS,
            "clearance_cost_radius_cells": CLEARANCE_COST_RADIUS_CELLS,
            "clearance_cost_weight": CLEARANCE_COST_WEIGHT,
            "safer_clearance_cost_weight": SAFER_CLEARANCE_COST_WEIGHT,
            "weighted_astar_epsilon": WEIGHTED_ASTAR_EPSILON,
            "alternate_route_cost_multiplier": ALTERNATE_ROUTE_COST_MULTIPLIER,
            "alternate_route_corridor_cells": ALTERNATE_ROUTE_CORRIDOR_CELLS,
            "alternate_route_min_leg_cells": ALTERNATE_ROUTE_MIN_LEG_CELLS,
            "alternate_route_max_overlap": ALTERNATE_ROUTE_MAX_OVERLAP,
            "alternate_route_max_time_factor": ALTERNATE_ROUTE_MAX_TIME_FACTOR,
            "walking_speed_kmh": WALKING_SPEED_KMH,
            "eva_hours": EVA_HOURS,
            "dose_rate_msv_per_hour": DOSE_RATE_MSV_PER_HOUR,
        },
    }
    (output / "cost.json").write_text(json.dumps(metadata, indent=2) + "\n")


def nearest_walkable_cell(
    cell: tuple[int, int],
    walkable: np.ndarray,
    x_size_m: float,
    y_size_m: float,
) -> tuple[tuple[int, int], float]:
    if walkable[cell]:
        return cell, 0.0
    rows, cols = np.nonzero(walkable)
    if rows.size == 0:
        raise ValueError("No cells remain walkable with the configured safety margin")
    distances_squared = (
        ((rows - cell[0]) * y_size_m) ** 2
        + ((cols - cell[1]) * x_size_m) ** 2
    )
    nearest = int(np.argmin(distances_squared))
    return (
        (int(rows[nearest]), int(cols[nearest])),
        math.sqrt(float(distances_squared[nearest])),
    )


def process_site(site: str) -> None:
    config = site_config(site)
    output = site_output_dir(site)
    dem_path = config["dem_path"]
    with rasterio.open(dem_path) as dem_source:
        rows, cols = dem_source.height, dem_source.width
        x_size_m, y_size_m = cell_size_meters(dem_source)
        transform = dem_source.transform
        bounds = {
            "min_lon": dem_source.bounds.left,
            "min_lat": dem_source.bounds.bottom,
            "max_lon": dem_source.bounds.right,
            "max_lat": dem_source.bounds.top,
        }
    with rasterio.open(output / "slope.tif") as source:
        slope_deg = source.read(1)
        if source.shape != (rows, cols) or source.transform != transform:
            raise ValueError(f"{site} slope grid is not aligned with its DEM")
    with rasterio.open(output / "roughness.tif") as source:
        roughness = source.read(1)
        if source.shape != (rows, cols) or source.transform != transform:
            raise ValueError(f"{site} roughness grid is not aligned with its DEM")
    with rasterio.open(output / "hazard.tif") as source:
        hazard_values = source.read(1)
        if source.shape != (rows, cols) or source.transform != transform:
            raise ValueError(f"{site} hazard mask is not aligned with its DEM")
        if not np.isin(hazard_values, (0, 1)).all():
            raise ValueError(f"{site} hazard mask must encode only 0=clear and 1=blocked")
        hazard_mask = hazard_values == 1

    clearance_cells, clearance_meters = distance_to_hazards(
        hazard_mask,
        x_size_m,
        y_size_m,
    )
    costs = make_route_cost_grid(
        slope_deg,
        roughness,
        hazard_mask,
        clearance_cells,
    )
    walkable = build_walkable_mask(costs, clearance_cells, SAFETY_MARGIN_CELLS)
    export_route_cost_grid(
        site,
        costs,
        clearance_cells,
        clearance_meters,
        bounds,
        transform,
        x_size_m,
        y_size_m,
    )
    print(
        f"{site}: cell size x={x_size_m:.3f} m, y={y_size_m:.3f} m; "
        f"hazards={int(hazard_mask.sum())}, "
        f"routing margin={SAFETY_MARGIN_CELLS} cells"
    )

    requested_points = [
        ("habitat", config["habitat"]),
        *[(f"target-{index + 1}", point) for index, point in enumerate(config["targets"])],
    ]
    endpoint_records = []
    for name, point in requested_points:
        original_cell = latlon_to_pixel(point, transform, rows, cols)
        snapped_cell, snap_distance_m = nearest_walkable_cell(
            original_cell,
            walkable,
            x_size_m,
            y_size_m,
        )
        center = pixel_to_latlon(snapped_cell, transform)
        endpoint_records.append({
            "id": name,
            "row": snapped_cell[0],
            "col": snapped_cell[1],
            "lat": center["lat"],
            "lon": center["lon"],
            "snapped": snap_distance_m > 0,
            "snap_distance_m": round(snap_distance_m, 3),
            "requested_cell": {"row": original_cell[0], "col": original_cell[1]},
        })
        if snap_distance_m > 0:
            print(
                f"{site}: {name} snapped from {original_cell} to {snapped_cell} "
                f"({snap_distance_m:.1f} m)"
            )

    points = [*endpoint_records, endpoint_records[0]]
    pixels = [(point["row"], point["col"]) for point in points]
    route_segments = []
    try:
        for start, goal in zip(pixels, pixels[1:]):
            route_segments.append(
                astar(start, goal, walkable, costs, x_size_m, y_size_m)
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
    legs = []
    for index, segment in enumerate(route_segments):
        distance = route_distance_km(segment, x_size_m, y_size_m)
        legs.append({
            "name": "return" if index == len(route_segments) - 1 else f"target-{index + 1}",
            "distance_km": round(distance, 3),
            "time_h": round(distance / WALKING_SPEED_KMH, 3),
        })
    largest_component_fraction, chokepoints = passability_metrics(walkable)
    stats = {
        "data_status": "REAL - route derived from supplied NASA DEM",
        "distance_km": round(distance_km, 3),
        "time_h": round(time_h, 3),
        "return_margin_h": round(EVA_HOURS - time_h, 3),
        "within_eva_limit": time_h <= EVA_HOURS,
        "est_dose_msv": round(time_h * DOSE_RATE_MSV_PER_HOUR, 4),
        "max_walkable_slope_deg": MAX_WALKABLE_SLOPE_DEG,
        "max_roughness_m": MAX_ROUGHNESS_M,
        "hazard_cells": int(hazard_mask.sum()),
        "hazard_fraction": round(float(hazard_mask.mean()), 6),
        "largest_passable_component_fraction": round(largest_component_fraction, 6),
        "chokepoints": chokepoints,
        "safety_margin_cells": SAFETY_MARGIN_CELLS,
        "minimum_clearance_m": round(
            min(float(clearance_meters[row, col]) for row, col in route_pixels),
            3,
        ),
        "cell_size_m": {"x": round(x_size_m, 3), "y": round(y_size_m, 3)},
    }
    grid = {
        "data_status": "REAL - supplied NASA DEM and CTX imagery",
        "site": site,
        "site_name": config["name"],
        "rows": rows,
        "cols": cols,
        "grid_bounds": [[0, 0], [rows, cols]],
        "geo_reference": {
            "status": "REAL DEM bounds",
            "bounds": bounds,
            "transform": list(transform)[:6],
            "cell_centers": True,
        },
        "cell_size_m": {"x": x_size_m, "y": y_size_m},
        "max_walkable_slope_deg": MAX_WALKABLE_SLOPE_DEG,
        "max_roughness_m": MAX_ROUGHNESS_M,
        "safety_margin_cells": SAFETY_MARGIN_CELLS,
        "route_pixels": route_pixels,
        "route_segments": route_segments,
        "targets": endpoint_records[1:],
        "legs": legs,
        "habitat": endpoint_records[0],
        "coordinate_status": (
            "PLACEHOLDER - route coordinates are DEM cell centers snapped outside "
            "the configured hazard margin"
        ),
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
                       "coordinate_system": "grid row,col cell centers"},
        "features": features,
    }, indent=2) + "\n")
    write_site_manifest()
    eva_status = "within" if time_h <= EVA_HOURS else "over"
    print(
        f"{site}: route {distance_km:.3f} km, {time_h:.3f} h "
        f"({eva_status} {EVA_HOURS:g} h EVA limit)"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", choices=sorted(SITES), required=True)
    args = parser.parse_args()
    process_site(args.site)


if __name__ == "__main__":
    main()
