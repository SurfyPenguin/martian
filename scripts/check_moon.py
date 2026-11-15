"""Verify processed lunar routes without reading raw source rasters."""

import argparse
import heapq
import json
import math
import random
import sys
import time
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from config import MOON_RADIUS_M, SAFETY_MARGIN_CELLS  # noqa: E402
from make_moon_site import lon_lat_to_xy, xy_to_lon_lat  # noqa: E402
from route import (  # noqa: E402
    astar,
    astar_with_metrics,
    build_walkable_mask,
    distance_to_hazards,
    nearest_walkable_cell,
    route_distance_km,
)


def bresenham(start: tuple[int, int], end: tuple[int, int]):
    row, col = start
    end_row, end_col = end
    delta_row = abs(end_row - row)
    delta_col = abs(end_col - col)
    step_row = 1 if row < end_row else -1
    step_col = 1 if col < end_col else -1
    error = delta_col - delta_row
    while True:
        yield row, col
        if (row, col) == (end_row, end_col):
            return
        doubled_error = 2 * error
        if doubled_error > -delta_row:
            error -= delta_row
            col += step_col
        if doubled_error < delta_col:
            error += delta_col
            row += step_row


def path_cells(path: list[tuple[int, int]]) -> list[tuple[int, int]]:
    cells = []
    for start, end in zip(path, path[1:]):
        cells.extend(list(bresenham(start, end))[:-1])
    if path:
        cells.append(path[-1])
    return cells


def route_cost(path, costs, cell_size_m) -> float:
    total = 0.0
    for (row, col), (next_row, next_col) in zip(path, path[1:]):
        total += math.hypot(
            (next_row - row) * cell_size_m["y"],
            (next_col - col) * cell_size_m["x"],
        ) * float(costs[next_row, next_col])
    return total


def dijkstra(start, goal, walkable, costs, cell_size_m):
    rows, cols = walkable.shape
    queue = [(0.0, start)]
    previous = {}
    distances = {start: 0.0}
    explored = 0
    while queue:
        current_cost, (row, col) = heapq.heappop(queue)
        if current_cost > distances[(row, col)]:
            continue
        explored += 1
        if (row, col) == goal:
            path = [goal]
            while path[-1] != start:
                path.append(previous[path[-1]])
            return list(reversed(path)), current_cost, explored
        for row_delta in (-1, 0, 1):
            for col_delta in (-1, 0, 1):
                if not row_delta and not col_delta:
                    continue
                next_row, next_col = row + row_delta, col + col_delta
                if not (0 <= next_row < rows and 0 <= next_col < cols):
                    continue
                if not walkable[next_row, next_col]:
                    continue
                if row_delta and col_delta and (
                    not walkable[row + row_delta, col]
                    or not walkable[row, col + col_delta]
                ):
                    continue
                step = math.hypot(
                    row_delta * cell_size_m["y"],
                    col_delta * cell_size_m["x"],
                ) * float(costs[next_row, next_col])
                candidate = current_cost + step
                next_cell = (next_row, next_col)
                if candidate >= distances.get(next_cell, math.inf):
                    continue
                distances[next_cell] = candidate
                previous[next_cell] = (row, col)
                heapq.heappush(queue, (candidate, next_cell))
    raise ValueError(f"No walkable route exists: {start} -> {goal}")


def verify_path(path, hazard, walkable, clearance_meters, name):
    if not path:
        raise AssertionError(f"{name} has no route cells")
    cells = path_cells(path)
    minimum_clearance = math.inf
    for row, col in cells:
        if hazard[row, col]:
            raise AssertionError(f"{name} crosses hazard at {(row, col)}")
        if not walkable[row, col]:
            raise AssertionError(f"{name} violates the safety margin at {(row, col)}")
        minimum_clearance = min(minimum_clearance, float(clearance_meters[row, col]))
    for start, end in zip(path, path[1:]):
        if max(abs(end[0] - start[0]), abs(end[1] - start[1])) != 1:
            raise AssertionError(f"{name} contains non-adjacent route vertices")
        dr, dc = end[0] - start[0], end[1] - start[1]
        if dr and dc and (
            not walkable[start[0] + dr, start[1]]
            or not walkable[start[0], start[1] + dc]
        ):
            raise AssertionError(f"{name} cuts a blocked diagonal corner")
    return minimum_clearance


def verify_projection(body):
    checks = body.get("projection_checks", [])
    if len(checks) != 3:
        raise AssertionError(f"Expected 3 GeoJSON projection checks; found {len(checks)}")
    for point in checks:
        x, y = lon_lat_to_xy(point["latitude"], point["longitude"])
        if math.hypot(x - point["x"], y - point["y"]) > 1:
            raise AssertionError(f"Python forward projection differs for region {point['region_id']}")
        latitude, longitude = xy_to_lon_lat(x, y)
        error = math.hypot(
            math.radians(latitude - point["latitude"]) * MOON_RADIUS_M,
            math.radians(longitude - point["longitude"]) * MOON_RADIUS_M
                * math.cos(math.radians(point["latitude"])),
        )
        if error > 1:
            raise AssertionError(f"Python inverse projection error {error:.3f} m")
    print("projection: 3 GeoJSON points round-trip in Python within 1 m")


def load_site(site_key):
    output = ROOT / "data" / "processed" / "moon" / site_key
    web_output = ROOT / "web" / "data" / "moon" / site_key
    grid = json.loads((output / "grid.json").read_text())
    stats = json.loads((output / "stats.json").read_text())
    metadata = json.loads((web_output / "cost.json").read_text())
    shape = (metadata["rows"], metadata["cols"])
    costs = np.fromfile(web_output / metadata["cost_file"], dtype="<f4").reshape(shape)
    clearance_cells = np.fromfile(
        web_output / metadata["clearance_files"]["cells"], dtype="<f4"
    ).reshape(shape)
    clearance_meters = np.fromfile(
        web_output / metadata["clearance_files"]["meters"], dtype="<f4"
    ).reshape(shape)
    with rasterio.open(output / "hazard.tif") as source:
        hazard = source.read(1) == 1
        if source.nodata is not None or not np.isin(source.read(1), (0, 1)).all():
            raise AssertionError(f"{site_key} hazard mask has invalid encoding")
        transform = list(source.transform)[:6]
    with Image.open(output / "hazard.png") as image:
        hazard_png = np.asarray(image.convert("RGBA"))
    if not np.array_equal(hazard_png[..., 3] == 220, hazard):
        raise AssertionError(f"{site_key} hazard overlay differs from the exported mask")
    if not np.array_equal(np.isposinf(costs), hazard):
        raise AssertionError(f"{site_key} browser costs differ from the exported mask")
    if transform != grid["geo_reference"]["transform"] or transform != metadata["raster_transform"]:
        raise AssertionError(f"{site_key} raster, grid and browser transforms differ")
    expected_cells, expected_meters = distance_to_hazards(
        hazard, metadata["cell_size_m"]["x"], metadata["cell_size_m"]["y"]
    )
    if not np.allclose(clearance_cells, expected_cells, rtol=0, atol=1e-4):
        raise AssertionError(f"{site_key} cell clearances differ from the hazard mask")
    if not np.allclose(clearance_meters, expected_meters, rtol=0, atol=1e-3):
        raise AssertionError(f"{site_key} metric clearances differ from the hazard mask")
    walkable = build_walkable_mask(
        costs, clearance_cells, metadata["parameters"]["safety_margin_cells"]
    )
    return (
        grid, stats, metadata, costs, hazard, walkable,
        clearance_cells, clearance_meters,
    )


def check_synthetic_corner_gap():
    costs = np.array([[1.0, np.inf], [np.inf, 1.0]], dtype="float32")
    clearance = np.array([[1.0, 0.0], [0.0, 1.0]], dtype="float32")
    walkable = build_walkable_mask(costs, clearance, 0)
    try:
        astar((0, 0), (1, 1), walkable, costs, 10, 10)
    except ValueError:
        print("synthetic diagonal gap: corner cutting blocked")
        return
    raise AssertionError("Synthetic diagonal gap allowed corner cutting")


def check_endpoint_and_eva_cases(
    site_key,
    grid,
    metadata,
    costs,
    hazard,
    walkable,
    clearance_cells,
    clearance_meters,
):
    cell_size = metadata["cell_size_m"]
    hazard_cells = np.argwhere(hazard)
    if not hazard_cells.size:
        raise AssertionError(f"{site_key} has no hazard cell for snapping test")
    requested_hazard = tuple(map(int, hazard_cells[0]))
    snapped_hazard, hazard_distance = nearest_walkable_cell(
        requested_hazard, walkable, cell_size["x"], cell_size["y"]
    )
    if hazard_distance <= 0 or not walkable[snapped_hazard] or hazard[snapped_hazard]:
        raise AssertionError(f"{site_key} hazard checkpoint did not snap to free terrain")
    print(
        f"{site_key} hazard checkpoint: snapped {hazard_distance:.1f} m "
        f"to {snapped_hazard}"
    )

    margin_cells = np.argwhere(
        np.isfinite(costs) & (clearance_cells <= SAFETY_MARGIN_CELLS)
    )
    if not margin_cells.size:
        raise AssertionError(f"{site_key} has no cell inside the safety margin")
    requested_margin = tuple(map(int, margin_cells[0]))
    snapped_margin, margin_distance = nearest_walkable_cell(
        requested_margin, walkable, cell_size["x"], cell_size["y"]
    )
    if margin_distance <= 0 or not walkable[snapped_margin]:
        raise AssertionError(f"{site_key} safety-margin checkpoint did not snap")
    print(
        f"{site_key} safety-margin checkpoint: snapped {margin_distance:.1f} m "
        f"to {snapped_margin}"
    )

    synthetic_costs = np.ones((20, 20), dtype="float32")
    synthetic_costs[:, 10] = np.inf
    synthetic_walkable = np.isfinite(synthetic_costs)
    try:
        astar((10, 4), (10, 16), synthetic_walkable, synthetic_costs, 10, 10)
    except ValueError as error:
        if "No walkable route" not in str(error):
            raise
        print(f"{site_key} disconnected checkpoint: no safe path; {error}")
    else:
        raise AssertionError(f"{site_key} disconnected pocket unexpectedly routed")

    habitat = (grid["habitat"]["row"], grid["habitat"]["col"])
    targets = [(point["row"], point["col"]) for point in grid["targets"]]
    points = [habitat, *targets, *targets, habitat]
    route = []
    for start, goal in zip(points, points[1:]):
        segment = astar(start, goal, walkable, costs, cell_size["x"], cell_size["y"])
        verify_path(
            segment,
            hazard,
            walkable,
            clearance_meters,
            f"{site_key} over-EVA leg",
        )
        route.extend(segment if not route else segment[1:])
    distance_km = route_distance_km(route, cell_size["x"], cell_size["y"])
    time_hours = distance_km / metadata["parameters"]["walking_speed_kmh"]
    if time_hours <= metadata["parameters"]["eva_hours"]:
        raise AssertionError(f"{site_key} repeated-target route did not exceed EVA limit")
    print(
        f"{site_key} repeated-target round trip: {distance_km:.3f} km / "
        f"{time_hours:.3f} h; OVER EVA LIMIT"
    )


def check_site(site_key, random_pairs=20, random_sets=20):
    (
        grid, stats, metadata, costs, hazard, walkable,
        clearance_cells, clearance_meters,
    ) = load_site(site_key)
    cell_size = metadata["cell_size_m"]
    rng = random.Random(20260615)
    labels, component_count = ndimage.label(
        walkable, structure=ndimage.generate_binary_structure(2, 1)
    )
    sizes = np.bincount(labels.ravel(), minlength=component_count + 1)
    sizes[0] = 0
    largest_label = int(np.argmax(sizes))
    available = np.flatnonzero(labels.ravel() == largest_label)
    if not available.size:
        raise AssertionError(f"{site_key} has no passable component")

    target_cells = [(point["row"], point["col"]) for point in grid["targets"]]
    hazard_crossing_pairs = [
        (left, right)
        for index, left in enumerate(target_cells)
        for right in target_cells[index + 1:]
        if any(hazard[row, col] for row, col in bresenham(left, right))
    ]
    if not hazard_crossing_pairs:
        raise AssertionError(f"{site_key} placeholder target lines avoid all hazards")
    print(
        f"{site_key} placeholder targets: straight line crosses hazard "
        f"between {hazard_crossing_pairs[0][0]} and {hazard_crossing_pairs[0][1]}"
    )

    for index, segment in enumerate(grid["route_segments"]):
        minimum = verify_path(segment, hazard, walkable, clearance_meters, f"{site_key} auto leg {index + 1}")
        print(f"{site_key} auto leg {index + 1}: zero hazard cells; minimum clearance {minimum:.1f} m")

    for case in range(random_sets):
        endpoints = [
            tuple(divmod(int(rng.choice(available)), walkable.shape[1]))
            for _ in range(3)
        ]
        habitat = (grid["habitat"]["row"], grid["habitat"]["col"])
        points = [habitat, *endpoints, habitat]
        for start, goal in zip(points, points[1:]):
            segment = astar(start, goal, walkable, costs, cell_size["x"], cell_size["y"])
            verify_path(segment, hazard, walkable, clearance_meters, f"{site_key} random set {case + 1}")
        print(f"{site_key} random checkpoint set {case + 1}: zero hazard cells")

    check_endpoint_and_eva_cases(
        site_key,
        grid,
        metadata,
        costs,
        hazard,
        walkable,
        clearance_cells,
        clearance_meters,
    )

    print(f"{site_key} A* vs Dijkstra cost parity ({random_pairs} pairs):")
    print("pair | A* cost | Dijkstra cost | A* ms | Dijkstra ms | explored A*/Dijkstra")
    for index in range(random_pairs):
        start = tuple(divmod(int(rng.choice(available)), walkable.shape[1]))
        goal = tuple(divmod(int(rng.choice(available)), walkable.shape[1]))
        while goal == start:
            goal = tuple(divmod(int(rng.choice(available)), walkable.shape[1]))
        started = time.perf_counter()
        a_path, a_explored = astar_with_metrics(
            start, goal, walkable, costs, cell_size["x"], cell_size["y"]
        )
        a_ms = (time.perf_counter() - started) * 1000
        a_cost = route_cost(a_path, costs, cell_size)
        started = time.perf_counter()
        d_path, d_cost, d_explored = dijkstra(start, goal, walkable, costs, cell_size)
        d_ms = (time.perf_counter() - started) * 1000
        if abs(a_cost - d_cost) > max(a_cost, d_cost) * 0.001:
            raise AssertionError(f"{site_key} A*/Dijkstra cost mismatch: {a_cost} vs {d_cost}")
        verify_path(a_path, hazard, walkable, clearance_meters, f"{site_key} A* parity route {index + 1}")
        verify_path(d_path, hazard, walkable, clearance_meters, f"{site_key} Dijkstra parity route {index + 1}")
        print(
            f"{index + 1:>4} | {a_cost:>8.1f} | {d_cost:>13.1f} | "
            f"{a_ms:>6.1f} | {d_ms:>11.1f} | {a_explored}/{d_explored}"
        )

    print(
        f"{site_key} metrics: hazard {stats['hazard_fraction']:.2%}, "
        f"passable {stats['largest_passable_component_fraction']:.2%}, "
        f"auto route {stats['route_distance_km']} km / {stats['route_time_h']} h, "
        f"return margin {stats['return_margin_h']} h"
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", required=True, choices=("site_01", "site_04", "site_07", "sl3"))
    parser.add_argument("--random-pairs", type=int, default=20)
    parser.add_argument("--random-sets", type=int, default=20)
    args = parser.parse_args()
    body = json.loads((ROOT / "web" / "data" / "moon" / "body.json").read_text())
    verify_projection(body)
    check_synthetic_corner_gap()
    check_site(args.site, args.random_pairs, args.random_sets)


if __name__ == "__main__":
    main()
