"""Verify exported hazard masks and every routed cell on both sites."""

import json
import random
import sys
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image
from rasterio.transform import xy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from config import SAFETY_MARGIN_CELLS, SITES  # noqa: E402
from route import (  # noqa: E402
    astar,
    build_walkable_mask,
    distance_to_hazards,
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
            break
        doubled_error = 2 * error
        if doubled_error > -delta_row:
            error -= delta_row
            col += step_col
        if doubled_error < delta_col:
            error += delta_col
            row += step_row


def cells_along_path(path: list[tuple[int, int]]) -> list[tuple[int, int]]:
    cells = []
    for start, end in zip(path, path[1:]):
        cells.extend(list(bresenham(start, end))[:-1])
    if path:
        cells.append(path[-1])
    return cells


def assert_safe_path(
    path: list[tuple[int, int]],
    hazard: np.ndarray,
    walkable: np.ndarray,
    clearance_meters: np.ndarray,
    safety_margin_cells: int,
) -> float:
    if not path:
        raise AssertionError("A routed path cannot be empty")
    clearance = []
    for start, end in zip(path, path[1:]):
        row_delta = end[0] - start[0]
        col_delta = end[1] - start[1]
        if max(abs(row_delta), abs(col_delta)) != 1:
            raise AssertionError(f"Non-adjacent route vertices: {start} -> {end}")
        if row_delta and col_delta and (
            not walkable[start[0] + row_delta, start[1]]
            or not walkable[start[0], start[1] + col_delta]
        ):
            raise AssertionError(f"Route cuts a blocked corner: {start} -> {end}")

    for row, col in cells_along_path(path):
        if hazard[row, col]:
            raise AssertionError(f"Route crosses hazard cell {(row, col)}")
        if not walkable[row, col]:
            raise AssertionError(f"Route violates {safety_margin_cells}-cell margin at {(row, col)}")
        clearance.append(float(clearance_meters[row, col]))
    return min(clearance)


def reachable_component(walkable: np.ndarray, start: tuple[int, int]) -> np.ndarray:
    rows, cols = walkable.shape
    if not walkable[start]:
        raise AssertionError(f"Test habitat is not walkable: {start}")
    seen = np.zeros(rows * cols, dtype=bool)
    queue = np.empty(rows * cols, dtype="int32")
    start_index = start[0] * cols + start[1]
    queue[0] = start_index
    seen[start_index] = True
    head = 0
    tail = 1
    while head < tail:
        current = int(queue[head])
        head += 1
        row, col = divmod(current, cols)
        for row_delta in (-1, 0, 1):
            for col_delta in (-1, 0, 1):
                if not row_delta and not col_delta:
                    continue
                next_row = row + row_delta
                next_col = col + col_delta
                if not (0 <= next_row < rows and 0 <= next_col < cols):
                    continue
                next_index = next_row * cols + next_col
                if seen[next_index] or not walkable[next_row, next_col]:
                    continue
                if row_delta and col_delta and (
                    not walkable[row + row_delta, col]
                    or not walkable[row, col + col_delta]
                ):
                    continue
                seen[next_index] = True
                queue[tail] = next_index
                tail += 1
    return queue[:tail].copy()


def verify_center_alignment(site: str, grid: dict, metadata: dict) -> None:
    directory = ROOT / "data" / "processed" / site
    with rasterio.open(directory / "hazard.tif") as hazard_source:
        transform = hazard_source.transform
        bounds = hazard_source.bounds
        rows, cols = hazard_source.shape
    exported_transform = tuple(grid["geo_reference"]["transform"])
    if tuple(transform)[:6] != exported_transform:
        raise AssertionError(f"{site} exported grid transform differs from hazard raster")
    if tuple(transform)[:6] != tuple(metadata["raster_transform"]):
        raise AssertionError(f"{site} cost grid transform differs from hazard raster")
    bounds_dict = grid["geo_reference"]["bounds"]
    expected_bounds = (
        bounds.left,
        bounds.bottom,
        bounds.right,
        bounds.top,
    )
    actual_bounds = (
        bounds_dict["min_lon"],
        bounds_dict["min_lat"],
        bounds_dict["max_lon"],
        bounds_dict["max_lat"],
    )
    if not np.allclose(actual_bounds, expected_bounds, rtol=0, atol=1e-12):
        raise AssertionError(f"{site} exported grid bounds differ from hazard raster")

    for row, col in ((0, 0), (rows // 2, cols // 2), (rows - 1, cols - 1)):
        lon, lat = xy(transform, row, col, offset="center")
        grid_lat = bounds_dict["max_lat"] - (row + 0.5) / rows * (
            bounds_dict["max_lat"] - bounds_dict["min_lat"]
        )
        grid_lon = bounds_dict["min_lon"] + (col + 0.5) / cols * (
            bounds_dict["max_lon"] - bounds_dict["min_lon"]
        )
        if not np.allclose((grid_lon, grid_lat), (lon, lat), rtol=0, atol=1e-10):
            raise AssertionError(f"{site} browser grid cell {(row, col)} is not its raster center")
    print(f"{site}: raster, exported grid, overlay bounds, and cell centers align")


def check_synthetic_corner_wall() -> None:
    costs = np.full((2, 2), np.inf, dtype="float32")
    clearance_cells = np.zeros((2, 2), dtype="float32")
    costs[0, 0] = 1
    costs[1, 1] = 1
    clearance_cells[0, 0] = 1
    clearance_cells[1, 1] = 1
    walkable = build_walkable_mask(costs, clearance_cells, 0)
    try:
        astar((0, 0), (1, 1), walkable, costs, 1, 1)
    except ValueError:
        print("synthetic wall/diagonal gap: corner cutting blocked")
        return
    raise AssertionError("Router crossed a diagonal-only gap in the synthetic wall")


def load_site(site: str):
    directory = ROOT / "data" / "processed" / site
    web_directory = ROOT / "web" / "data" / site
    grid = json.loads((directory / "grid.json").read_text())
    metadata = json.loads((web_directory / "cost.json").read_text())
    costs = np.fromfile(web_directory / "cost.bin", dtype="<f4").reshape(
        metadata["rows"], metadata["cols"]
    )
    clearance_cells = np.fromfile(
        web_directory / metadata["clearance_files"]["cells"],
        dtype="<f4",
    ).reshape(metadata["rows"], metadata["cols"])
    clearance_meters = np.fromfile(
        web_directory / metadata["clearance_files"]["meters"],
        dtype="<f4",
    ).reshape(metadata["rows"], metadata["cols"])
    with rasterio.open(directory / "hazard.tif") as source:
        hazard_values = source.read(1)
        if source.nodata is not None:
            raise AssertionError(f"{site} hazard raster must encode NoData as blocked")
        hazard = hazard_values == 1
        if not np.isin(hazard_values, (0, 1)).all():
            raise AssertionError(f"{site} hazard raster has an invalid encoding")
        x_size_m = float(source.tags()["CELL_SIZE_X_M"]) if "CELL_SIZE_X_M" in source.tags() else metadata["cell_size_m"]["x"]
        y_size_m = float(source.tags()["CELL_SIZE_Y_M"]) if "CELL_SIZE_Y_M" in source.tags() else metadata["cell_size_m"]["y"]
    if not np.array_equal(np.isposinf(costs), hazard):
        raise AssertionError(f"{site} browser costs do not use the exported hazard mask")

    with Image.open(directory / "hazard.png") as image:
        rgba = np.asarray(image.convert("RGBA"))
    if rgba.shape[:2] != hazard.shape:
        raise AssertionError(f"{site} hazard PNG is not aligned with the hazard mask")
    if not np.array_equal(rgba[..., 3] == 220, hazard):
        raise AssertionError(f"{site} hazard PNG does not render the exported mask")
    if not np.all(rgba[hazard, :3] == (239, 68, 68)):
        raise AssertionError(f"{site} hazard PNG has unexpected hazard colors")

    expected_cells, expected_meters = distance_to_hazards(hazard, x_size_m, y_size_m)
    if not np.allclose(clearance_cells, expected_cells, rtol=0, atol=1e-4):
        raise AssertionError(f"{site} cell-clearance grid differs from the exported mask")
    if not np.allclose(clearance_meters, expected_meters, rtol=0, atol=1e-3):
        raise AssertionError(f"{site} metric-clearance grid differs from the exported mask")
    walkable = build_walkable_mask(costs, clearance_cells, SAFETY_MARGIN_CELLS)
    verify_center_alignment(site, grid, metadata)
    return grid, costs, clearance_cells, clearance_meters, hazard, walkable, x_size_m, y_size_m


def check_site(site: str, rng: random.Random) -> None:
    (
        grid,
        costs,
        clearance_cells,
        clearance_meters,
        hazard,
        walkable,
        x_size_m,
        y_size_m,
    ) = load_site(site)
    habitat = (grid["habitat"]["row"], grid["habitat"]["col"])
    auto_clearance = []
    for index, path in enumerate(grid["route_segments"], start=1):
        auto_clearance.append(
            assert_safe_path(
                [tuple(cell) for cell in path],
                hazard,
                walkable,
                clearance_meters,
                SAFETY_MARGIN_CELLS,
            )
        )
    print(
        f"{site} auto plan: {len(grid['route_segments'])} legs, "
        f"minimum clearance {min(auto_clearance):.1f} m"
    )

    component = reachable_component(walkable, habitat)
    if component.size < 4:
        raise AssertionError(f"{site} habitat component is too small for random routes")
    rng.shuffle(component)
    cols = costs.shape[1]
    for case_index in range(20):
        stops = [
            tuple(divmod(int(flat), cols))
            for flat in component[:3]
        ]
        points = [habitat, *stops, habitat]
        clearances = []
        for start, goal in zip(points, points[1:]):
            path = astar(start, goal, walkable, costs, x_size_m, y_size_m)
            clearances.append(
                assert_safe_path(
                    path,
                    hazard,
                    walkable,
                    clearance_meters,
                    SAFETY_MARGIN_CELLS,
                )
            )
        print(
            f"{site} random set {case_index + 1:02d}: "
            f"4 legs, minimum clearance {min(clearances):.1f} m"
        )
        rng.shuffle(component)


def main() -> None:
    check_synthetic_corner_wall()
    rng = random.Random(20261115)
    for site in SITES:
        check_site(site, rng)
    print("All exported auto and random routes are hazard- and margin-free.")


if __name__ == "__main__":
    main()
